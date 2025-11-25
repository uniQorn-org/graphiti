"""
LangChainサービス - RAG & チャット
"""
import logging
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from ..models.schemas import ChatMessage, ChatResponse, SearchResult
from .graphiti_service import GraphitiService
from ..utils.proxy_utils import get_proxy_config, log_proxy_status

logger = logging.getLogger(__name__)


class LangChainService:
    """LangChainを使ったRAGチャットサービス"""

    def __init__(
        self, graphiti_service: GraphitiService, openai_api_key: str, model: str
    ):
        """
        初期化

        Args:
            graphiti_service: Graphitiサービス
            openai_api_key: OpenAI APIキー
            model: 使用するモデル名
        """
        self.graphiti = graphiti_service

        # Log proxy configuration status
        log_proxy_status()

        # Set proxy environment variables if PROXY_USE is enabled
        # LangChain's ChatOpenAI will automatically use HTTP_PROXY/HTTPS_PROXY env vars
        import os
        proxy_config = get_proxy_config()
        if proxy_config:
            proxy_url = proxy_config.get("https://", proxy_config.get("http://"))
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
            logger.info(f"Set HTTP_PROXY/HTTPS_PROXY for ChatOpenAI: {proxy_url.split('@')[-1]}")

        # ChatOpenAI will automatically use:
        # 1. HTTP_PROXY/HTTPS_PROXY environment variables (set above)
        # 2. NO_PROXY environment variable (from .env)
        # No need to pass http_client parameter
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model=model,
            temperature=0.7,
            streaming=False
        )

        # プロンプトテンプレート
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """あなたは社内の知識ベースを使って質問に答えるアシスタントです。

以下のナレッジグラフから取得した情報を使って、ユーザーの質問に答えてください。

## 検索結果

{search_results}

## 指示

1. 上記の「関連する事実」に記載されている情報を必ず活用して回答してください
2. 検索結果に「関連する情報が見つかりませんでした。」と表示されている場合のみ、「情報が見つかりませんでした」と答えてください
3. それ以外の場合は、検索結果の事実を使って具体的に答えてください
4. 回答は日本語で、わかりやすく説明してください
5. 検索結果の事実を引用する際は、内容をそのまま使用してください""",
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),
            ]
        )

        self.chain = self.prompt | self.llm | StrOutputParser()
        logger.info("LangChainサービスを初期化しました")

    def _format_search_results(self, search_results: SearchResult) -> str:
        """
        検索結果をテキスト形式に変換

        Args:
            search_results: 検索結果

        Returns:
            フォーマットされたテキスト
        """
        if search_results.total_count == 0:
            return "関連する情報が見つかりませんでした。"

        text_parts = []

        # エッジ（関係性）を表示
        if search_results.edges:
            text_parts.append("### 関連する事実:")
            for i, edge in enumerate(search_results.edges[:10], 1):
                text_parts.append(f"{i}. {edge.fact}")
                if edge.valid_at:
                    text_parts.append(f"   - 有効期間: {edge.valid_at}")

        # ノード（エンティティ）を表示
        if search_results.nodes:
            text_parts.append("\n### 関連するエンティティ:")
            for i, node in enumerate(search_results.nodes[:5], 1):
                text_parts.append(f"{i}. {node.name}")
                if node.summary:
                    text_parts.append(f"   - 概要: {node.summary}")

        return "\n".join(text_parts)

    def _convert_chat_history(self, history: List[ChatMessage]) -> List:
        """
        チャット履歴をLangChain形式に変換

        Args:
            history: チャット履歴

        Returns:
            LangChain形式のメッセージリスト
        """
        messages = []
        for msg in history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
        return messages

    async def chat(
        self,
        message: str,
        history: List[ChatMessage],
        include_search_results: bool = True,
    ) -> ChatResponse:
        """
        チャット処理

        Args:
            message: ユーザーメッセージ
            history: チャット履歴
            include_search_results: 検索結果を含めるか

        Returns:
            チャット応答
        """
        try:
            # Graphitiで検索
            search_results = await self.graphiti.search(message, limit=10)

            # 検索結果をフォーマット
            formatted_results = self._format_search_results(search_results)
            logger.info(f"検索結果フォーマット: {formatted_results}")
            logger.info(f"検索結果件数: edges={len(search_results.edges)}, nodes={len(search_results.nodes)}")

            # チャット履歴を変換
            langchain_history = self._convert_chat_history(history)

            # LLMに問い合わせ
            response = await self.chain.ainvoke(
                {
                    "question": message,
                    "search_results": formatted_results,
                    "history": langchain_history,
                }
            )

            # ソースを抽出
            sources = []
            for edge in search_results.edges[:5]:
                sources.append(f"{edge.name}: {edge.fact[:100]}...")

            return ChatResponse(
                answer=response,
                search_results=search_results if include_search_results else None,
                sources=sources,
            )

        except Exception as e:
            logger.error(f"チャットエラー: {e}")
            return ChatResponse(
                answer=f"エラーが発生しました: {str(e)}", search_results=None, sources=[]
            )