"""
MCPクライアントサービス - Graphiti MCPサーバーとHTTP通信
"""
import logging
from typing import List, Optional
from datetime import datetime
import httpx
from graphiti_core.edges import EntityEdge as GraphitiEntityEdge
from ..models.schemas import (
    EntityNode,
    EntityEdge,
    SearchResult,
    UpdateFactResponse,
    AddEpisodeResponse,
)

logger = logging.getLogger(__name__)


class MCPClientService:
    """Graphiti MCPサーバーとHTTP通信するクライアント"""

    def __init__(self, mcp_url: str, neo4j_uri: str = None, neo4j_user: str = None, neo4j_password: str = None):
        """
        初期化

        Args:
            mcp_url: MCPサーバーのベースURL (例: http://graphiti-mcp:8001)
            neo4j_uri: Neo4j URI (Fact更新用)
            neo4j_user: Neo4jユーザー名
            neo4j_password: Neo4jパスワード
        """
        self.mcp_url = mcp_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=60.0)

        # Neo4jドライバー (Fact更新用)
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.driver = None
        if neo4j_uri:
            from neo4j import AsyncGraphDatabase
            self.driver = AsyncGraphDatabase.driver(
                neo4j_uri,
                auth=(neo4j_user, neo4j_password)
            )

        logger.info(f"MCPクライアント初期化: {self.mcp_url}")

    async def search(
        self,
        query: str,
        limit: int = 10,
        group_ids: Optional[List[str]] = None,
    ) -> SearchResult:
        """
        ナレッジグラフを検索

        Args:
            query: 検索クエリ
            limit: 最大結果数
            group_ids: グループIDリスト

        Returns:
            検索結果
        """
        try:
            url = f"{self.mcp_url}/graph/search"
            payload = {
                "query": query,
                "search_type": "facts",
                "max_results": limit,
            }
            if group_ids:
                payload["group_ids"] = group_ids

            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            logger.info(f"MCP検索レスポンス: {data}")

            # MCPサーバーのレスポンス形式をSearchResultに変換
            edges = []
            results = data.get("results", data.get("facts", []))
            logger.info(f"検索結果数: {len(results)}")
            if results:
                for fact in results:
                    edge = EntityEdge(
                        uuid=fact.get("uuid", ""),
                        source_node_uuid=fact.get("source_node_uuid", ""),
                        target_node_uuid=fact.get("target_node_uuid", ""),
                        name=fact.get("name", ""),
                        fact=fact.get("fact", ""),
                        created_at=fact.get("created_at"),
                        valid_at=fact.get("valid_at"),
                        invalid_at=fact.get("invalid_at"),
                        expired_at=fact.get("expired_at"),
                        episodes=fact.get("episodes", []),
                        updated_at=fact.get("updated_at"),
                        original_fact=fact.get("original_fact"),
                        update_reason=fact.get("update_reason"),
                    )
                    edges.append(edge)

            return SearchResult(nodes=[], edges=edges, total_count=len(edges))

        except httpx.HTTPStatusError as e:
            logger.error(f"MCP検索HTTPエラー: {e}")
            return SearchResult(nodes=[], edges=[], total_count=0)
        except Exception as e:
            logger.error(f"MCP検索エラー: {e}")
            return SearchResult(nodes=[], edges=[], total_count=0)

    async def update_fact(
        self,
        edge_uuid: str,
        new_fact: str,
        reason: Optional[str] = None,
    ) -> UpdateFactResponse:
        """
        Factを更新

        Args:
            edge_uuid: エッジのUUID
            new_fact: 新しいFact
            reason: 更新理由

        Returns:
            更新結果
        """
        try:
            url = f"{self.mcp_url}/graph/facts/{edge_uuid}"
            payload = {
                "fact": new_fact,
            }
            if reason:
                payload["reason"] = reason

            response = await self.client.patch(url, json=payload)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                # 更新されたエッジ情報を取得
                fact_data = data.get("fact", {})
                updated_edge = EntityEdge(
                    uuid=fact_data.get("uuid", edge_uuid),
                    source_node_uuid=fact_data.get("source_node_uuid", ""),
                    target_node_uuid=fact_data.get("target_node_uuid", ""),
                    name=fact_data.get("name", ""),
                    fact=fact_data.get("fact", new_fact),
                    created_at=fact_data.get("created_at"),
                    valid_at=fact_data.get("valid_at"),
                    invalid_at=fact_data.get("invalid_at"),
                    expired_at=fact_data.get("expired_at"),
                    episodes=fact_data.get("episodes", []),
                    updated_at=fact_data.get("updated_at"),
                    original_fact=fact_data.get("original_fact"),
                    update_reason=fact_data.get("update_reason", reason),
                )

                return UpdateFactResponse(
                    success=True,
                    message=data.get("message", "Factを更新しました"),
                    updated_edge=updated_edge,
                )
            else:
                return UpdateFactResponse(
                    success=False,
                    message=data.get("error", "更新に失敗しました"),
                )

        except httpx.HTTPStatusError as e:
            logger.error(f"MCP Fact更新HTTPエラー: {e}")
            return UpdateFactResponse(
                success=False, message=f"HTTPエラー: {e.response.status_code}"
            )
        except Exception as e:
            logger.error(f"MCP Fact更新エラー: {e}")
            return UpdateFactResponse(success=False, message=f"エラー: {str(e)}")

    async def add_episode(
        self,
        name: str,
        content: str,
        source: str = "text",
        source_description: Optional[str] = None,
    ) -> AddEpisodeResponse:
        """
        新しいエピソードを追加

        Args:
            name: エピソード名
            content: エピソード内容
            source: ソース（text/json/message）
            source_description: ソースの説明

        Returns:
            追加結果
        """
        try:
            url = f"{self.mcp_url}/graph/episodes"
            payload = {
                "name": name,
                "content": content,
                "source": source,
                "source_description": source_description or "User input",
            }

            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                return AddEpisodeResponse(
                    success=True,
                    message=data.get("message", "エピソードを追加しました"),
                    episode_uuid=name,
                )
            else:
                return AddEpisodeResponse(
                    success=False, message=data.get("error", "追加に失敗しました")
                )

        except httpx.HTTPStatusError as e:
            logger.error(f"MCPエピソード追加HTTPエラー: {e}")
            return AddEpisodeResponse(
                success=False, message=f"HTTPエラー: {e.response.status_code}"
            )
        except Exception as e:
            logger.error(f"MCPエピソード追加エラー: {e}")
            return AddEpisodeResponse(success=False, message=f"エラー: {str(e)}")

    async def close(self):
        """クライアントを閉じる"""
        await self.client.aclose()
        logger.info("MCPクライアントを閉じました")
