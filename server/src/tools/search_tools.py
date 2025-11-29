"""Search tools for querying nodes, facts, and episodes in the graph."""

import logging

from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF
from graphiti_core.search.search_filters import SearchFilters
from models.response_types import (ErrorResponse, FactSearchResponse,
                                   NodeResult, NodeSearchResponse)
from services.service_container import ServiceContainer
from utils.formatting import format_fact_result
from utils.graphiti_operations import resolve_group_ids, create_node_search_filters

logger = logging.getLogger(__name__)


async def search_nodes(
    query: str,
    group_ids: list[str] | None = None,
    max_nodes: int = 10,
    entity_types: list[str] | None = None,
) -> NodeSearchResponse | ErrorResponse:
    """Search for nodes in the graph memory.

    Args:
        query: The search query
        group_ids: Optional list of group IDs to filter results
        max_nodes: Maximum number of nodes to return (default: 10)
        entity_types: Optional list of entity type names to filter by
    """
    try:
        graphiti_service = ServiceContainer.get_graphiti_service()
        config = ServiceContainer.get_config()
    except RuntimeError as e:
        return ErrorResponse(error=str(e))

    try:
        client = await graphiti_service.get_client()

        # Resolve group IDs using shared utility
        effective_group_ids = resolve_group_ids(group_ids, config)

        # Create search filters using shared utility
        search_filters = create_node_search_filters(entity_types)

        # Use the search_ method with node search config
        results = await client.search_(
            query=query,
            config=NODE_HYBRID_SEARCH_RRF,
            group_ids=effective_group_ids,
            search_filter=search_filters,
        )

        # Extract nodes from results
        nodes = results.nodes[:max_nodes] if results.nodes else []

        if not nodes:
            return NodeSearchResponse(message="No relevant nodes found", nodes=[])

        # Format the results
        node_results = []
        for node in nodes:
            # Get attributes and ensure no embeddings are included
            attrs = node.attributes if hasattr(node, "attributes") else {}
            # Remove any embedding keys that might be in attributes
            attrs = {k: v for k, v in attrs.items() if "embedding" not in k.lower()}

            node_results.append(
                NodeResult(
                    uuid=node.uuid,
                    name=node.name,
                    labels=node.labels if node.labels else [],
                    created_at=node.created_at.isoformat() if node.created_at else None,
                    summary=node.summary,
                    group_id=node.group_id,
                    attributes=attrs,
                )
            )

        return NodeSearchResponse(
            message="Nodes retrieved successfully", nodes=node_results
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error searching nodes: {error_msg}")
        return ErrorResponse(error=f"Error searching nodes: {error_msg}")


async def search_memory_facts(
    query: str,
    group_ids: list[str] | None = None,
    max_facts: int = 10,
    center_node_uuid: str | None = None,
) -> FactSearchResponse | ErrorResponse:
    """Search the graph memory for relevant facts.

    Args:
        query: The search query
        group_ids: Optional list of group IDs to filter results
        max_facts: Maximum number of facts to return (default: 10)
        center_node_uuid: Optional UUID of a node to center the search around
    """
    try:
        graphiti_service = ServiceContainer.get_graphiti_service()
        config = ServiceContainer.get_config()
    except RuntimeError as e:
        return ErrorResponse(error=str(e))

    try:
        # Validate max_facts parameter
        if max_facts <= 0:
            return ErrorResponse(error="max_facts must be a positive integer")

        client = await graphiti_service.get_client()

        # Resolve group IDs using shared utility
        effective_group_ids = resolve_group_ids(group_ids, config)

        relevant_edges = await client.search(
            group_ids=effective_group_ids,
            query=query,
            num_results=max_facts,
            center_node_uuid=center_node_uuid,
        )

        if not relevant_edges:
            return FactSearchResponse(message="No relevant facts found", facts=[])

        facts = [format_fact_result(edge) for edge in relevant_edges]
        return FactSearchResponse(message="Facts retrieved successfully", facts=facts)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error searching facts: {error_msg}")
        return ErrorResponse(error=f"Error searching facts: {error_msg}")
