"""
設定とDI
"""
import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from .services import LangChainService
from .services.mcp_client_service import MCPClientService


class Settings(BaseSettings):
    """環境変数設定"""

    # Graphiti MCP Server
    graphiti_mcp_url: str = os.getenv("GRAPHITI_MCP_URL", "http://graphiti-mcp:8001")

    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Server
    backend_port: int = int(os.getenv("BACKEND_PORT", "20001"))
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:20002")

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """設定取得"""
    return Settings()


# グローバルサービスインスタンス
_mcp_client_service: Optional[MCPClientService] = None
_langchain_service: Optional[LangChainService] = None


async def init_services():
    """サービス初期化"""
    global _mcp_client_service, _langchain_service

    settings = get_settings()

    # MCPクライアントサービス初期化
    _mcp_client_service = MCPClientService(
        mcp_url=settings.graphiti_mcp_url,
    )

    # LangChainサービス初期化
    _langchain_service = LangChainService(
        graphiti_service=_mcp_client_service,
        openai_api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


async def shutdown_services():
    """サービスシャットダウン"""
    global _mcp_client_service, _langchain_service

    if _mcp_client_service:
        await _mcp_client_service.close()


def get_graphiti_service() -> MCPClientService:
    """Graphitiサービス取得（DI用）"""
    if _mcp_client_service is None:
        raise RuntimeError("MCPクライアントサービスが初期化されていません")
    return _mcp_client_service


def get_langchain_service() -> LangChainService:
    """LangChainサービス取得（DI用）"""
    if _langchain_service is None:
        raise RuntimeError("LangChainサービスが初期化されていません")
    return _langchain_service
