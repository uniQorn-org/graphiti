"""
Graphiti service - Knowledge graph management
"""
import logging
import sys
from pathlib import Path
from typing import List
from datetime import datetime

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

from ..models.schemas import (
    EntityNode,
    EntityEdge,
    SearchResult,
    UpdateFactResponse,
    AddEpisodeResponse,
    CitationInfo,
)

# Import shared utilities from MCP server
# Add the server/src directory to the path
server_src_path = Path(__file__).parent.parent.parent.parent / "server" / "src"
if str(server_src_path) not in sys.path:
    sys.path.insert(0, str(server_src_path))

# Import shared datetime utilities
from shared.utils.datetime_utils import convert_neo4j_datetime

try:
    from services.citation_service import get_episode_citations
except ImportError:
    # Fallback if import fails
    async def get_episode_citations(driver, entity_uuid, entity_type="edge"):
        return []

logger = logging.getLogger(__name__)


class GraphitiService:
    """Graphitiクライアントのラッパー"""

    def __init__(self, uri: str, user: str, password: str):
        """
        初期化

        Args:
            uri: Neo4j URI
            user: Neo4j ユーザー名
            password: Neo4j パスワード
        """
        self.client = Graphiti(uri=uri, user=user, password=password)
        logger.info(f"Graphitiサービスを初期化しました: {uri}")

    async def search(self, query: str, limit: int = 10) -> SearchResult:
        """
        ナレッジグラフを検索

        Args:
            query: 検索クエリ
            limit: 結果の最大数

        Returns:
            検索結果
        """
        try:
            # Graphitiで検索 (limitパラメータは使用しない)
            results = await self.client.search(query)

            # Convert results
            nodes = []
            edges = []
            edge_uuids = []

            if isinstance(results, list):
                # エッジのリスト
                for edge in results:
                    edge_uuids.append(edge.uuid)
                    edges.append(
                        EntityEdge(
                            uuid=edge.uuid,
                            source_node_uuid=edge.source_node_uuid,
                            target_node_uuid=edge.target_node_uuid,
                            name=edge.name,
                            fact=edge.fact,
                            created_at=edge.created_at,
                            valid_at=edge.valid_at,
                            invalid_at=edge.invalid_at,
                            expired_at=edge.expired_at,
                            episodes=edge.episodes or [],
                        )
                    )
            else:
                # SearchResultsオブジェクト
                if hasattr(results, "edges"):
                    for edge in results.edges:
                        edge_uuids.append(edge.uuid)
                        edges.append(
                            EntityEdge(
                                uuid=edge.uuid,
                                source_node_uuid=edge.source_node_uuid,
                                target_node_uuid=edge.target_node_uuid,
                                name=edge.name,
                                fact=edge.fact,
                                created_at=edge.created_at,
                                valid_at=edge.valid_at,
                                invalid_at=edge.invalid_at,
                                expired_at=edge.expired_at,
                                episodes=edge.episodes or [],
                            )
                        )
                if hasattr(results, "nodes"):
                    for node in results.nodes:
                        nodes.append(
                            EntityNode(
                                uuid=node.uuid,
                                name=node.name,
                                summary=node.summary,
                                created_at=node.created_at,
                                labels=node.labels or [],
                                attributes=node.attributes or {},
                            )
                        )

            # カスタムフィールド（updated_at, original_fact, update_reason）とcitationsをNeo4jから取得
            if edge_uuids:
                query = """
                UNWIND $uuids AS uuid
                MATCH ()-[e:RELATES_TO]->()
                WHERE e.uuid = uuid
                RETURN e.uuid AS uuid, e.updated_at AS updated_at,
                       e.original_fact AS original_fact, e.update_reason AS update_reason
                """
                async with self.client.driver.session() as session:
                    result = await session.run(query, uuids=edge_uuids)
                    records = [record async for record in result]

                    # UUIDでマッピング
                    custom_fields = {
                        record["uuid"]: {
                            "updated_at": convert_neo4j_datetime(record.get("updated_at")),
                            "original_fact": record.get("original_fact"),
                            "update_reason": record.get("update_reason"),
                        }
                        for record in records
                    }

                    # 各エッジのcitationsを取得
                    citations_map = {}
                    for edge_uuid in edge_uuids:
                        try:
                            raw_citations = await get_episode_citations(
                                self.client.driver, edge_uuid, "edge"
                            )
                            # Convert dict citations to CitationInfo objects
                            citations_map[edge_uuid] = [
                                CitationInfo(**citation) for citation in raw_citations
                            ]
                        except Exception as e:
                            logger.error(f"Error fetching citations for edge {edge_uuid}: {e}")
                            citations_map[edge_uuid] = []

                    # エッジにカスタムフィールドとcitationsを追加
                    for i, edge in enumerate(edges):
                        fields = custom_fields.get(edge.uuid, {})
                        edge_citations = citations_map.get(edge.uuid, [])

                        # model_dump()からカスタムフィールドを除外して再構築
                        edge_dict = edge.model_dump(exclude={'updated_at', 'original_fact', 'update_reason', 'citations'})
                        edges[i] = EntityEdge(
                            **edge_dict,
                            updated_at=fields.get("updated_at"),
                            original_fact=fields.get("original_fact"),
                            update_reason=fields.get("update_reason"),
                            citations=edge_citations,
                        )

            return SearchResult(
                nodes=nodes, edges=edges, total_count=len(nodes) + len(edges)
            )

        except Exception as e:
            logger.error(f"検索エラー: {e}")
            raise

    async def update_fact(
        self, edge_uuid: str, new_fact: str, reason: Optional[str] = None
    ) -> UpdateFactResponse:
        """
        Factを更新

        Args:
            edge_uuid: 更新するエッジのUUID
            new_fact: 新しいfact
            reason: 更新理由

        Returns:
            更新結果
        """
        try:
            # Neo4jに直接クエリを実行してfactを更新
            # original_factは初回修正時のみ保存（COALESCEで既存値を優先）
            query = """
            MATCH ()-[e:RELATES_TO]->()
            WHERE e.uuid = $edge_uuid
            SET e.fact = $new_fact,
                e.updated_at = datetime(),
                e.update_reason = $reason,
                e.original_fact = COALESCE(e.original_fact, e.fact)
            RETURN e
            """

            async with self.client.driver.session() as session:
                result = await session.run(
                    query,
                    edge_uuid=edge_uuid,
                    new_fact=new_fact,
                    reason=reason or "User correction",
                )
                records = [record async for record in result]

            if records:
                record = records[0]
                edge_data = dict(record["e"])

                # Convert Neo4j DateTime to Python datetime (using shared utility)
                updated_edge = EntityEdge(
                    uuid=edge_data.get("uuid"),
                    source_node_uuid=edge_data.get("source_node_uuid", ""),
                    target_node_uuid=edge_data.get("target_node_uuid", ""),
                    name=edge_data.get("name", ""),
                    fact=edge_data.get("fact", ""),
                    created_at=convert_neo4j_datetime(edge_data.get("created_at")) or datetime.now(),
                    valid_at=convert_neo4j_datetime(edge_data.get("valid_at")),
                    invalid_at=convert_neo4j_datetime(edge_data.get("invalid_at")),
                    expired_at=convert_neo4j_datetime(edge_data.get("expired_at")),
                    episodes=edge_data.get("episodes", []),
                    # 修正履歴フィールド
                    updated_at=convert_neo4j_datetime(edge_data.get("updated_at")),
                    original_fact=edge_data.get("original_fact"),
                    update_reason=edge_data.get("update_reason"),
                )

                return UpdateFactResponse(
                    success=True,
                    message="Factを更新しました",
                    updated_edge=updated_edge,
                )
            else:
                return UpdateFactResponse(
                    success=False, message="エッジが見つかりませんでした"
                )

        except Exception as e:
            logger.error(f"Fact更新エラー: {e}")
            return UpdateFactResponse(success=False, message=f"エラー: {str(e)}")

    async def add_episode(
        self,
        name: str,
        content: str,
        source: str = "user_input",
        source_description: Optional[str] = None,
    ) -> AddEpisodeResponse:
        """
        新しいエピソードを追加

        Args:
            name: エピソード名
            content: エピソード内容
            source: ソース（episode_type_strとして使用）
            source_description: ソースの説明

        Returns:
            追加結果
        """
        try:
            # sourceをEpisodeTypeに変換
            episode_type = EpisodeType.text  # デフォルト
            if source.lower() in ['message', 'text', 'json']:
                episode_type = EpisodeType(source.lower())

            # Graphitiにエピソードを追加
            await self.client.add_episode(
                name=name,
                episode_body=content,
                source=episode_type,
                source_description=source_description or "User input",
                reference_time=datetime.now(),
            )

            return AddEpisodeResponse(
                success=True, message="エピソードを追加しました", episode_uuid=name
            )

        except Exception as e:
            logger.error(f"エピソード追加エラー: {e}")
            return AddEpisodeResponse(success=False, message=f"エラー: {str(e)}")

    async def close(self):
        """クライアントを閉じる"""
        await self.client.close()