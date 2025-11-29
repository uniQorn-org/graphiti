"""Citation tools for retrieving provenance information about facts and nodes."""

import logging

from models.citation_types import (CitationChainResponse,
                                   FactSearchWithCitationsResponse,
                                   FactWithCitations)
from models.response_types import ErrorResponse
from services.citation_service import get_citation_chain, get_episode_citations
from services.service_container import ServiceContainer
from utils.formatting import format_fact_result

logger = logging.getLogger(__name__)


async def search_with_citations(
    query: str,
    group_ids: list[str] | None = None,
    max_facts: int = 10,
    center_node_uuid: str | None = None,
) -> FactSearchWithCitationsResponse | ErrorResponse:
    """Search the graph memory for relevant facts with citation information.

    This is an enhanced version of search_memory_facts that includes information
    about which episodes (sources) each fact was derived from.

    Args:
        query: The search query
        group_ids: Optional list of group IDs to filter results
        max_facts: Maximum number of facts to return (default: 10)
        center_node_uuid: Optional UUID of a node to center the search around

    Returns:
        Facts with citation information showing source episodes
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

        # Use the provided group_ids or fall back to the default from config
        effective_group_ids = (
            group_ids
            if group_ids is not None
            else [config.graphiti.group_id]
            if config.graphiti.group_id
            else []
        )

        # Search for relevant edges
        relevant_edges = await client.search(
            group_ids=effective_group_ids,
            query=query,
            num_results=max_facts,
            center_node_uuid=center_node_uuid,
        )

        if not relevant_edges:
            return FactSearchWithCitationsResponse(
                message="No relevant facts found", facts=[]
            )

        # For each edge, get its citations
        facts_with_citations = []
        for edge in relevant_edges:
            # Format the basic fact information
            fact_dict = format_fact_result(edge)

            # Get citation information
            citations = await get_episode_citations(
                client.driver, edge.uuid, entity_type="edge"
            )

            # Combine into FactWithCitations
            # EntityEdge model_dump() returns keys that match the Pydantic model fields
            fact_with_cit = FactWithCitations(
                uuid=fact_dict.get("uuid", ""),
                # Try multiple possible key names for node references
                from_node=fact_dict.get("source_node_name")
                or fact_dict.get("source_node_uuid", ""),
                to_node=fact_dict.get("target_node_name")
                or fact_dict.get("target_node_uuid", ""),
                fact=fact_dict.get("fact", ""),
                created_at=fact_dict.get("created_at"),
                updated_at=fact_dict.get("updated_at"),
                attributes=fact_dict.get("attributes", {}),
                citations=citations,
            )
            facts_with_citations.append(fact_with_cit)

        return FactSearchWithCitationsResponse(
            message=f"Found {len(facts_with_citations)} facts with citations",
            facts=facts_with_citations,
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error searching facts with citations: {error_msg}")
        return ErrorResponse(error=f"Error searching facts with citations: {error_msg}")


async def get_citation_chain_tool(
    uuid: str, entity_type: str = "edge", max_depth: int = 10
) -> CitationChainResponse | ErrorResponse:
    """Get the citation chain for an entity (edge or node).

    This shows the full history of episodes that created, updated, or referenced
    this entity, helping to trace the provenance of information.

    Args:
        uuid: UUID of the entity (edge or node)
        entity_type: Type of entity ("edge" or "node")
        max_depth: Maximum depth to traverse (default: 10)

    Returns:
        Citation chain showing the history of episodes related to this entity
    """
    try:
        graphiti_service = ServiceContainer.get_graphiti_service()
    except RuntimeError as e:
        return ErrorResponse(error=str(e))

    try:
        if entity_type not in ["edge", "node"]:
            return ErrorResponse(error="entity_type must be either 'edge' or 'node'")

        client = await graphiti_service.get_client()

        # Get the citation chain
        chain = await get_citation_chain(
            client.driver, uuid, entity_type=entity_type, max_depth=max_depth
        )

        if not chain:
            return CitationChainResponse(
                message="No citation chain found for this entity",
                target_uuid=uuid,
                target_type=entity_type,
                chain=[],
            )

        return CitationChainResponse(
            message=f"Found {len(chain)} entries in citation chain",
            target_uuid=uuid,
            target_type=entity_type,
            chain=chain,
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error getting citation chain: {error_msg}")
        return ErrorResponse(error=f"Error getting citation chain: {error_msg}")
