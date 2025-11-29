"""MCP client connection manager."""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class MCPClient:
    """Manages MCP client connections and sessions."""

    def __init__(self, mcp_url: str = "http://localhost:8001/mcp/"):
        """
        Initialize MCP client.

        Args:
            mcp_url: URL of the MCP server endpoint
        """
        self.mcp_url = mcp_url
        self._session: ClientSession | None = None

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[ClientSession]:
        """
        Connect to MCP server and yield session.

        Yields:
            Initialized MCP client session
        """
        async with streamablehttp_client(self.mcp_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def add_episode(
        self,
        session: ClientSession,
        name: str,
        episode_body: str,
        source: str,
        source_description: str,
        source_url: str,
        reference_time: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Add an episode to Graphiti.

        Args:
            session: Active MCP client session
            name: Episode name/identifier
            episode_body: Episode content
            source: Source type (e.g., "text", "message")
            source_description: Description of the source
            source_url: URL to the original source
            reference_time: Optional timestamp when the episode occurred

        Returns:
            Response from add_memory tool
        """
        arguments = {
            "name": name,
            "episode_body": episode_body,
            "source": source,
            "source_description": source_description,
            "source_url": source_url,
        }

        # Add reference_time if provided
        if reference_time:
            arguments["reference_time"] = reference_time.isoformat()

        result = await session.call_tool("add_memory", arguments=arguments)
        return result

    async def clear_graph(self, session: ClientSession) -> dict[str, Any]:
        """
        Clear all graph data.

        Args:
            session: Active MCP client session

        Returns:
            Response from clear_graph tool
        """
        result = await session.call_tool("clear_graph", arguments={})
        return result
