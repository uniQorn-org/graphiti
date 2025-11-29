"""
MCP Client Service - HTTP communication with Graphiti MCP Server
"""
import logging
from datetime import datetime
import httpx
from graphiti_core.edges import EntityEdge as GraphitiEntityEdge
from ..models.schemas import (
    EntityNode,
    EntityEdge,
    SearchResult,
    UpdateFactResponse,
    AddEpisodeResponse,
    CitationInfo,
)

logger = logging.getLogger(__name__)


class MCPClientService:
    """HTTP client for communicating with Graphiti MCP Server"""

    def __init__(self, mcp_url: str, neo4j_uri: str = None, neo4j_user: str = None, neo4j_password: str = None):
        """
        Initialize MCP client service

        Args:
            mcp_url: Base URL of MCP server (e.g., http://graphiti-mcp:8001)
            neo4j_uri: Neo4j URI (for fact updates)
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
        """
        self.mcp_url = mcp_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=60.0)

        # Neo4j driver (for fact updates)
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

        logger.info(f"MCP client initialized: {self.mcp_url}")

    async def search(
        self,
        query: str,
        limit: int = 10,
        group_ids: list[str] | None = None,
    ) -> SearchResult:
        """
        Search the knowledge graph

        Args:
            query: Search query
            limit: Maximum number of results
            group_ids: List of group IDs

        Returns:
            Search results
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

            logger.info(f"MCP search response: {data}")

            # Convert MCP server response format to SearchResult
            edges = []
            results = data.get("results", data.get("facts", []))
            logger.info(f"Number of search results: {len(results)}")
            if results:
                for fact in results:
                    # Extract citations from the MCP response
                    citations_data = fact.get("citations", [])
                    citations = [CitationInfo(**c) for c in citations_data] if citations_data else []

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
                        citations=citations,
                        updated_at=fact.get("updated_at"),
                        original_fact=fact.get("original_fact"),
                        update_reason=fact.get("update_reason"),
                    )
                    edges.append(edge)

            return SearchResult(nodes=[], edges=edges, total_count=len(edges))

        except httpx.HTTPStatusError as e:
            logger.error(f"MCP search HTTP error: {e}")
            return SearchResult(nodes=[], edges=[], total_count=0)
        except Exception as e:
            logger.error(f"MCP search error: {e}")
            return SearchResult(nodes=[], edges=[], total_count=0)

    async def update_fact(
        self,
        edge_uuid: str,
        new_fact: str,
        reason: str | None = None,
    ) -> UpdateFactResponse:
        """
        Update a fact

        Args:
            edge_uuid: UUID of the edge
            new_fact: New fact text
            reason: Update reason

        Returns:
            Update result
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
                # Get updated edge information
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
                    message=data.get("message", "Fact updated successfully"),
                    updated_edge=updated_edge,
                )
            else:
                return UpdateFactResponse(
                    success=False,
                    message=data.get("error", "Update failed"),
                )

        except httpx.HTTPStatusError as e:
            logger.error(f"MCP fact update HTTP error: {e}")
            return UpdateFactResponse(
                success=False, message=f"HTTP error: {e.response.status_code}"
            )
        except Exception as e:
            logger.error(f"MCP fact update error: {e}")
            return UpdateFactResponse(success=False, message=f"Error: {str(e)}")

    async def add_episode(
        self,
        name: str,
        content: str,
        source: str = "text",
        source_description: str | None = None,
    ) -> AddEpisodeResponse:
        """
        Add a new episode

        Args:
            name: Episode name
            content: Episode content
            source: Source type (text/json/message)
            source_description: Source description

        Returns:
            Addition result
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
                    message=data.get("message", "Episode added successfully"),
                    episode_uuid=name,
                )
            else:
                return AddEpisodeResponse(
                    success=False, message=data.get("error", "Addition failed")
                )

        except httpx.HTTPStatusError as e:
            logger.error(f"MCP episode addition HTTP error: {e}")
            return AddEpisodeResponse(
                success=False, message=f"HTTP error: {e.response.status_code}"
            )
        except Exception as e:
            logger.error(f"MCP episode addition error: {e}")
            return AddEpisodeResponse(success=False, message=f"Error: {str(e)}")

    async def close(self):
        """Close the client"""
        await self.client.aclose()
        logger.info("MCP client closed")
