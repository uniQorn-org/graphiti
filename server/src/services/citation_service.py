"""Citation service for Graphiti - provides citation tracking functionality."""

import logging
import re

from neo4j import AsyncDriver
from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode, EpisodicNode
from models.citation_types import CitationChainEntry, CitationInfo

logger = logging.getLogger(__name__)


def extract_source_url(source_description: str) -> str | None:
    """Extract source_url from source_description string.

    Args:
        source_description: Source description that may contain "source_url: {url}"

    Returns:
        Extracted URL or None if not found
    """
    if not source_description:
        return None

    # Match "source_url: " followed by URL (http/https)
    match = re.search(r'source_url:\s*(https?://[^\s,]+)', source_description)
    if match:
        return match.group(1)
    return None


async def get_episode_citations(
    driver: AsyncDriver, entity_uuid: str, entity_type: str = "edge"
) -> list[CitationInfo]:
    """Get citations (source episodes) for an entity (edge or node).

    Args:
        driver: Neo4j driver instance
        entity_uuid: UUID of the entity (edge or node)
        entity_type: Type of entity ("edge" or "node")

    Returns:
        List of citation information
    """
    citations = []

    try:
        # For edges (facts), get episodes from the episodes array property
        # For nodes, query MENTIONS relationship
        if entity_type == "edge":
            # Get the edge and its episodes array
            query = """
            MATCH ()-[r:RELATES_TO {uuid: $uuid}]->()
            RETURN r.episodes as episode_uuids
            """
            result = await driver.execute_query(query, uuid=entity_uuid)

            episode_uuids = []
            for record in result.records:
                uuids = record.get("episode_uuids", [])
                if uuids:
                    episode_uuids.extend(uuids)

            # Now fetch the actual episode nodes
            if episode_uuids:
                episode_query = """
                MATCH (episode:Episodic)
                WHERE episode.uuid IN $uuids
                RETURN episode
                ORDER BY episode.created_at DESC
                """
                episode_result = await driver.execute_query(episode_query, uuids=episode_uuids)

                for record in episode_result.records:
                    episode_data = record["episode"]
                    source_desc = episode_data.get("source_description", "")
                    citation = CitationInfo(
                        episode_uuid=episode_data.get("uuid", ""),
                        episode_name=episode_data.get("name", ""),
                        source=episode_data.get("source", "unknown"),
                        source_description=source_desc,
                        created_at=episode_data.get("created_at").isoformat()
                        if episode_data.get("created_at")
                        else None,
                        source_url=extract_source_url(source_desc),
                    )
                    citations.append(citation)
        else:  # node
            query = """
            MATCH (episode:Episodic)-[:MENTIONS]->(node {uuid: $uuid})
            RETURN episode
            ORDER BY episode.created_at DESC
            """
            result = await driver.execute_query(query, uuid=entity_uuid)

            for record in result.records:
                episode_data = record["episode"]
                source_desc = episode_data.get("source_description", "")
                citation = CitationInfo(
                    episode_uuid=episode_data.get("uuid", ""),
                    episode_name=episode_data.get("name", ""),
                    source=episode_data.get("source", "unknown"),
                    source_description=source_desc,
                    created_at=episode_data.get("created_at").isoformat()
                    if episode_data.get("created_at")
                    else None,
                    source_url=extract_source_url(source_desc),
                )
                citations.append(citation)

    except Exception as e:
        logger.error(f"Error getting citations for {entity_type} {entity_uuid}: {e}")

    return citations


async def get_citation_chain(
    driver: AsyncDriver, entity_uuid: str, entity_type: str = "edge", max_depth: int = 10
) -> list[CitationChainEntry]:
    """Get the full citation chain for an entity, tracking creation and updates.

    Args:
        driver: Neo4j driver instance
        entity_uuid: UUID of the entity
        entity_type: Type of entity ("edge" or "node")
        max_depth: Maximum depth to traverse

    Returns:
        List of citation chain entries in chronological order
    """
    chain = []

    try:
        # Query to get all episodes that mention this entity, with temporal info
        if entity_type == "edge":
            query = """
            MATCH (episode:Episodic)-[r:MENTIONS]->(edge {uuid: $uuid})
            RETURN episode, edge.created_at as entity_created_at,
                   edge.updated_at as entity_updated_at
            ORDER BY episode.created_at ASC
            """
        else:  # node
            query = """
            MATCH (episode:Episodic)-[r:MENTIONS]->(node {uuid: $uuid})
            RETURN episode, node.created_at as entity_created_at
            ORDER BY episode.created_at ASC
            """

        result = await driver.execute_query(query, uuid=entity_uuid)

        entity_created_at = None
        entity_updated_at = None

        for idx, record in enumerate(result.records):
            episode_data = record["episode"]
            if idx == 0:
                entity_created_at = record.get("entity_created_at")
                entity_updated_at = record.get("entity_updated_at")

            episode_created = episode_data.get("created_at")

            # Determine operation type based on temporal data
            operation = "created"
            if entity_created_at and episode_created:
                if episode_created == entity_created_at:
                    operation = "created"
                elif (
                    entity_type == "edge"
                    and entity_updated_at
                    and episode_created == entity_updated_at
                ):
                    operation = "updated"
                else:
                    operation = "referenced"

            source_desc = episode_data.get("source_description", "")
            entry = CitationChainEntry(
                episode_uuid=episode_data.get("uuid", ""),
                episode_name=episode_data.get("name", ""),
                source=episode_data.get("source", "unknown"),
                source_description=source_desc,
                created_at=episode_created.isoformat() if episode_created else None,
                operation=operation,
                source_url=extract_source_url(source_desc),
            )
            chain.append(entry)

            if len(chain) >= max_depth:
                break

    except Exception as e:
        logger.error(
            f"Error getting citation chain for {entity_type} {entity_uuid}: {e}"
        )

    return chain
