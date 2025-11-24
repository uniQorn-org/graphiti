"""REST API endpoints for Graphiti graph operations."""

import logging
from datetime import datetime
from typing import Optional

from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EpisodeType, EpisodicNode
from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF
from graphiti_core.search.search_filters import SearchFilters
from models.api_types import (APIErrorResponse, EpisodeCreateRequest,
                              EpisodeCreateResponse, FactDeleteResponse,
                              FactUpdateRequest, FactUpdateResponse,
                              GraphSearchRequest, GraphSearchResponse)
from starlette.requests import Request
from starlette.responses import JSONResponse
from utils.formatting import format_fact_result

logger = logging.getLogger(__name__)


# ============================================================================
# Episode Management API
# ============================================================================


async def create_episode_api(
    request: Request, graphiti_service, queue_service, config
) -> JSONResponse:
    """
    Create a new episode (add to memory).

    POST /graph/episodes
    Body: EpisodeCreateRequest
    """
    if graphiti_service is None or queue_service is None:
        return JSONResponse(
            APIErrorResponse(
                error="Services not initialized", status_code=500
            ).model_dump(),
            status_code=500,
        )

    try:
        # Parse request body
        body = await request.json()
        episode_request = EpisodeCreateRequest(**body)

        # Use provided group_id or fall back to default
        effective_group_id = episode_request.group_id or config.graphiti.group_id

        # Convert source string to EpisodeType enum
        episode_type = EpisodeType.text  # Default
        if episode_request.source:
            try:
                episode_type = EpisodeType[episode_request.source.lower()]
            except (KeyError, AttributeError):
                logger.warning(
                    f"Unknown source type '{episode_request.source}', using 'text' as default"
                )
                episode_type = EpisodeType.text

        # Submit to queue service for async processing
        await queue_service.add_episode(
            group_id=effective_group_id,
            name=episode_request.name,
            content=episode_request.content,
            source_description=episode_request.source_description or "",
            episode_type=episode_type,
            entity_types=graphiti_service.entity_types,
            uuid=episode_request.uuid or None,
        )

        response = EpisodeCreateResponse(
            status="success",
            message=f"Episode '{episode_request.name}' queued for processing in group '{effective_group_id}'",
            episode_name=episode_request.name,
            group_id=effective_group_id,
        )

        return JSONResponse(response.model_dump())

    except Exception as e:
        logger.error(f"Error creating episode: {e}")
        return JSONResponse(
            APIErrorResponse(error=str(e), status_code=500).model_dump(),
            status_code=500,
        )


# ============================================================================
# Graph Search API
# ============================================================================


async def search_graph_api(request: Request, graphiti_service, config) -> JSONResponse:
    """
    Search the graph for nodes, facts, or episodes.

    POST /graph/search
    Body: GraphSearchRequest
    """
    if graphiti_service is None:
        return JSONResponse(
            APIErrorResponse(
                error="Graphiti service not initialized", status_code=500
            ).model_dump(),
            status_code=500,
        )

    try:
        # Parse request body
        body = await request.json()
        search_request = GraphSearchRequest(**body)

        client = await graphiti_service.get_client()

        # Use provided group_ids or fall back to default
        effective_group_ids = (
            search_request.group_ids
            if search_request.group_ids is not None
            else [config.graphiti.group_id]
            if config.graphiti.group_id
            else []
        )

        results = []

        if search_request.search_type == "facts":
            # Search for facts (EntityEdges)
            relevant_edges = await client.search(
                group_ids=effective_group_ids,
                query=search_request.query,
                num_results=search_request.max_results,
                center_node_uuid=search_request.center_node_uuid,
            )

            results = [format_fact_result(edge) for edge in relevant_edges]

        elif search_request.search_type == "nodes":
            # Search for nodes (EntityNodes)
            search_filters = SearchFilters(
                node_labels=search_request.entity_types,
            )

            search_results = await client.search_(
                query=search_request.query,
                config=NODE_HYBRID_SEARCH_RRF,
                group_ids=effective_group_ids,
                search_filter=search_filters,
            )

            nodes = (
                search_results.nodes[: search_request.max_results]
                if search_results.nodes
                else []
            )

            for node in nodes:
                attrs = node.attributes if hasattr(node, "attributes") else {}
                attrs = {k: v for k, v in attrs.items() if "embedding" not in k.lower()}

                results.append(
                    {
                        "uuid": node.uuid,
                        "name": node.name,
                        "labels": node.labels if node.labels else [],
                        "created_at": node.created_at.isoformat()
                        if node.created_at
                        else None,
                        "summary": node.summary,
                        "group_id": node.group_id,
                        "attributes": attrs,
                    }
                )

        elif search_request.search_type == "episodes":
            # Get episodes
            if effective_group_ids:
                episodes = await EpisodicNode.get_by_group_ids(
                    client.driver, effective_group_ids, limit=search_request.max_results
                )
            else:
                episodes = []

            for episode in episodes:
                results.append(
                    {
                        "uuid": episode.uuid,
                        "name": episode.name,
                        "content": episode.content,
                        "created_at": episode.created_at.isoformat()
                        if episode.created_at
                        else None,
                        "source": episode.source.value
                        if hasattr(episode.source, "value")
                        else str(episode.source),
                        "source_description": episode.source_description,
                        "group_id": episode.group_id,
                    }
                )

        else:
            return JSONResponse(
                APIErrorResponse(
                    error=f"Invalid search_type: {search_request.search_type}",
                    status_code=400,
                ).model_dump(),
                status_code=400,
            )

        response = GraphSearchResponse(
            message=f"Found {len(results)} {search_request.search_type}",
            search_type=search_request.search_type,
            results=results,
            count=len(results),
        )

        return JSONResponse(response.model_dump())

    except Exception as e:
        logger.error(f"Error searching graph: {e}")
        return JSONResponse(
            APIErrorResponse(error=str(e), status_code=500).model_dump(),
            status_code=500,
        )


# ============================================================================
# Episode Delete API
# ============================================================================


async def delete_episode_api(request: Request, graphiti_service) -> JSONResponse:
    """
    Delete an episode and all related nodes/facts by UUID.

    DELETE /graph/episodes/{uuid}

    This will delete:
    - The episode itself
    - All nodes (entities) extracted from this episode
    - All facts (relationships) related to those nodes
    """
    if graphiti_service is None:
        return JSONResponse(
            APIErrorResponse(
                error="Graphiti service not initialized", status_code=500
            ).model_dump(),
            status_code=500,
        )

    try:
        uuid = request.path_params["uuid"]
        client = await graphiti_service.get_client()

        # Get and delete the episode
        episode = await EpisodicNode.get_by_uuid(client.driver, uuid)
        await episode.delete(client.driver)

        response = FactDeleteResponse(
            status="deleted",
            uuid=uuid,
            message=f"Episode {uuid} and related entities deleted successfully",
        )

        return JSONResponse(response.model_dump())

    except Exception as e:
        logger.error(f"Error deleting episode: {e}")
        return JSONResponse(
            APIErrorResponse(error=str(e), status_code=500).model_dump(),
            status_code=500,
        )


# ============================================================================
# Fact Management APIs
# ============================================================================


async def update_fact_api(request: Request, graphiti_service) -> JSONResponse:
    """
    Update a fact by creating a new version and expiring the old one.

    PATCH /graph/facts/{uuid}
    Body: FactUpdateRequest

    This implements a "soft update" pattern:
    1. Get the old fact
    2. Set expired_at on the old fact
    3. Create a new fact with updated content
    """
    if graphiti_service is None:
        return JSONResponse(
            APIErrorResponse(
                error="Graphiti service not initialized", status_code=500
            ).model_dump(),
            status_code=500,
        )

    try:
        old_uuid = request.path_params["uuid"]
        body = await request.json()
        update_request = FactUpdateRequest(**body)

        client = await graphiti_service.get_client()

        # Get the old fact
        old_edge = await EntityEdge.get_by_uuid(client.driver, old_uuid)

        # Mark old fact as expired
        old_edge.expired_at = datetime.now()
        await old_edge.save(client.driver)

        # Determine source and target nodes
        source_uuid = update_request.source_node_uuid or old_edge.source_node_uuid
        target_uuid = update_request.target_node_uuid or old_edge.target_node_uuid

        # Generate embedding for the new fact
        embedding_response = await client.embedder.create(input=[update_request.fact])
        embedding_vector = embedding_response.data[0].embedding

        # Create new fact
        new_edge = EntityEdge(
            uuid=None,  # Will be auto-generated
            name=update_request.fact,
            fact=update_request.fact,
            fact_embedding=embedding_vector,
            episodes=[],
            created_at=datetime.now(),
            expired_at=None,
            invalid_at=None,
            group_id=old_edge.group_id,
            source_node_uuid=source_uuid,
            target_node_uuid=target_uuid,
        )

        # Add custom attributes if provided
        if update_request.attributes:
            for key, value in update_request.attributes.items():
                setattr(new_edge, key, value)

        # Save new edge
        await new_edge.save(client.driver)

        response = FactUpdateResponse(
            status="updated",
            old_uuid=old_uuid,
            new_uuid=new_edge.uuid,
            message=f"Fact updated successfully. Old fact {old_uuid} expired, new fact {new_edge.uuid} created",
        )

        return JSONResponse(response.model_dump())

    except Exception as e:
        logger.error(f"Error updating fact: {e}")
        return JSONResponse(
            APIErrorResponse(error=str(e), status_code=500).model_dump(),
            status_code=500,
        )
