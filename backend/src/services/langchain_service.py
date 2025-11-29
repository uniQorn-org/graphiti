"""
LangChain service - RAG & Chat
"""
import logging
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

# Use shared proxy configuration
import sys
from pathlib import Path
server_src_path = Path(__file__).parent.parent.parent.parent / "server" / "src"
if str(server_src_path) not in sys.path:
    sys.path.insert(0, str(server_src_path))

from shared.utils.proxy_config import setup_proxy_environment, log_proxy_status
from shared.constants import DEFAULT_LLM_TEMPERATURE

from ..models.schemas import ChatMessage, ChatResponse, SearchResult
from .graphiti_service import GraphitiService

logger = logging.getLogger(__name__)


class LangChainService:
    """RAG chat service using LangChain"""

    def __init__(
        self, graphiti_service: GraphitiService, openai_api_key: str, model: str
    ):
        """
        Initialize LangChain service.

        Args:
            graphiti_service: Graphiti service instance
            openai_api_key: OpenAI API key
            model: Model name to use
        """
        self.graphiti = graphiti_service

        # Log and setup proxy configuration
        log_proxy_status()
        setup_proxy_environment()

        # ChatOpenAI will automatically use:
        # 1. HTTP_PROXY/HTTPS_PROXY environment variables (set by setup_proxy_environment)
        # 2. NO_PROXY environment variable (from .env)

        # Check if custom base_url is set (for cc-throttle or corporate proxy)
        base_url = os.getenv("OPENAI_BASE_URL")
        if base_url:
            logger.info(f"Using custom OpenAI base URL: {base_url}")
            self.llm = ChatOpenAI(
                api_key=openai_api_key,
                base_url=base_url,
                model=model,
                temperature=DEFAULT_LLM_TEMPERATURE,
                streaming=False
            )
        else:
            self.llm = ChatOpenAI(
                api_key=openai_api_key,
                model=model,
                temperature=DEFAULT_LLM_TEMPERATURE,
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
        logger.info("LangChain service initialized successfully")

    def _format_search_results(self, search_results: SearchResult) -> str:
        """
        Format search results as text.

        Args:
            search_results: Search results from Graphiti

        Returns:
            Formatted text string
        """
        if search_results.total_count == 0:
            return "No relevant information found."

        text_parts = []

        # Display edges (relationships)
        if search_results.edges:
            text_parts.append("### Related Facts:")
            for i, edge in enumerate(search_results.edges[:10], 1):
                text_parts.append(f"{i}. {edge.fact}")
                if edge.valid_at:
                    text_parts.append(f"   - Valid from: {edge.valid_at}")

        # Display nodes (entities)
        if search_results.nodes:
            text_parts.append("\n### Related Entities:")
            for i, node in enumerate(search_results.nodes[:5], 1):
                text_parts.append(f"{i}. {node.name}")
                if node.summary:
                    text_parts.append(f"   - Summary: {node.summary}")

        return "\n".join(text_parts)

    def _convert_chat_history(self, history: list[ChatMessage]) -> list:
        """
        Convert chat history to LangChain format

        Args:
            history: Chat history

        Returns:
            Message list in LangChain format
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
        history: list[ChatMessage],
        include_search_results: bool = True,
    ) -> ChatResponse:
        """
        Chat processing

        Args:
            message: User message
            history: Chat history
            include_search_results: Whether to include search results

        Returns:
            Chat response
        """
        try:
            # Search with Graphiti
            search_results = await self.graphiti.search(message, limit=10)

            # Format search results
            formatted_results = self._format_search_results(search_results)
            logger.info(f"Formatted search results: {formatted_results}")
            logger.info(f"Search result counts: edges={len(search_results.edges)}, nodes={len(search_results.nodes)}")

            # Convert chat history
            langchain_history = self._convert_chat_history(history)

            # Query LLM
            response = await self.chain.ainvoke(
                {
                    "question": message,
                    "search_results": formatted_results,
                    "history": langchain_history,
                }
            )

            # Extract sources
            sources = []
            for edge in search_results.edges[:5]:
                sources.append(f"{edge.name}: {edge.fact[:100]}...")

            return ChatResponse(
                answer=response,
                search_results=search_results if include_search_results else None,
                sources=sources,
            )

        except Exception as e:
            logger.error(f"Chat error: {e}")
            return ChatResponse(
                answer=f"An error occurred: {str(e)}", search_results=None, sources=[]
            )