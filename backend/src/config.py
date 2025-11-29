"""
Configuration and Dependency Injection
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from .services import LangChainService
from .services.mcp_client_service import MCPClientService


class Settings(BaseSettings):
    """Environment variable settings"""

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
    """Get settings instance"""
    return Settings()


# Global service instances
_mcp_client_service: MCPClientService | None = None
_langchain_service: LangChainService | None = None


async def init_services():
    """Initialize services"""
    global _mcp_client_service, _langchain_service

    settings = get_settings()

    # Initialize MCP client service
    _mcp_client_service = MCPClientService(
        mcp_url=settings.graphiti_mcp_url,
    )

    # Initialize LangChain service
    _langchain_service = LangChainService(
        graphiti_service=_mcp_client_service,
        openai_api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


async def shutdown_services():
    """Shutdown services"""
    global _mcp_client_service, _langchain_service

    if _mcp_client_service:
        await _mcp_client_service.close()


def get_graphiti_service() -> MCPClientService:
    """Get Graphiti service instance (for DI)"""
    if _mcp_client_service is None:
        raise RuntimeError("MCP client service has not been initialized")
    return _mcp_client_service


def get_langchain_service() -> LangChainService:
    """Get LangChain service instance (for DI)"""
    if _langchain_service is None:
        raise RuntimeError("LangChain service has not been initialized")
    return _langchain_service
