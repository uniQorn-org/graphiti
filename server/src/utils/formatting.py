"""Formatting utilities for Graphiti MCP Server."""

from typing import Any

from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode
from services.citation_service import get_episode_citations


def format_node_result(node: EntityNode) -> dict[str, Any]:
    """Format an entity node into a readable result.

    Since EntityNode is a Pydantic BaseModel, we can use its built-in serialization capabilities.
    Excludes embedding vectors to reduce payload size and avoid exposing internal representations.

    Args:
        node: The EntityNode to format

    Returns:
        A dictionary representation of the node with serialized dates and excluded embeddings
    """
    result = node.model_dump(
        mode="json",
        exclude={
            "name_embedding",
        },
    )
    # Remove any embedding that might be in attributes
    result.get("attributes", {}).pop("name_embedding", None)
    return result


async def format_fact_result(edge: EntityEdge, driver: Any = None) -> dict[str, Any]:
    """Format an entity edge into a readable result with citations.

    Since EntityEdge is a Pydantic BaseModel, we can use its built-in serialization capabilities.

    Args:
        edge: The EntityEdge to format
        driver: Neo4j driver for fetching citations

    Returns:
        A dictionary representation of the edge with serialized dates, excluded embeddings, and citations
    """
    result = edge.model_dump(
        mode="json",
        exclude={
            "fact_embedding",
        },
    )
    result.get("attributes", {}).pop("fact_embedding", None)

    # Add citations if driver is provided
    if driver:
        try:
            citations = await get_episode_citations(driver, edge.uuid, "edge")
            result["citations"] = citations
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error fetching citations for edge {edge.uuid}: {e}")
            result["citations"] = []
    else:
        result["citations"] = []

    return result
