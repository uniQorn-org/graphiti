"""REST API endpoints for Graphiti graph operations."""

import logging
from datetime import datetime
from typing import Optional, Any, Dict

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


def create_cors_response(content: Dict[str, Any], status_code: int = 200) -> JSONResponse:
    """Create a JSONResponse with CORS headers."""
    response = JSONResponse(content, status_code=status_code)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response


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
            source_url=episode_request.source_url,
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

            # Format results with citations (use asyncio.gather for parallel fetching)
            import asyncio
            results = await asyncio.gather(*[
                format_fact_result(edge, client.driver) for edge in relevant_edges
            ])

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

        return create_cors_response(response.model_dump())

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
    logger.info("=" * 80)
    logger.info("🔧 update_fact_api: Function called")
    logger.info("=" * 80)

    if graphiti_service is None:
        logger.error("❌ Graphiti service is None")
        return JSONResponse(
            APIErrorResponse(
                error="Graphiti service not initialized", status_code=500
            ).model_dump(),
            status_code=500,
        )

    try:
        old_uuid = request.path_params["uuid"]
        logger.info(f"📋 Request parameters:")
        logger.info(f"   - UUID: {old_uuid}")

        body = await request.json()
        logger.info(f"   - Request body keys: {list(body.keys())}")

        update_request = FactUpdateRequest(**body)
        logger.info(f"   - New fact text: {update_request.fact[:100]}...")
        logger.info(f"   - New fact length: {len(update_request.fact)}")

        logger.info(f"🔌 Getting Graphiti client...")
        client = await graphiti_service.get_client()
        logger.info(f"   ✅ Graphiti client obtained")
        logger.info(f"   - client.embedder: {client.embedder}")
        logger.info(f"   - client.embedder type: {type(client.embedder)}")

        # Get the old fact
        logger.info(f"📥 Fetching old edge by UUID: {old_uuid}")
        old_edge = await EntityEdge.get_by_uuid(client.driver, old_uuid)
        logger.info(f"   ✅ Old edge fetched successfully")
        logger.info(f"   - old_edge.uuid: {old_edge.uuid}")
        logger.info(f"   - old_edge.fact: {old_edge.fact[:100] if old_edge.fact else 'None'}...")
        logger.info(f"   - old_edge.fact_embedding is None: {old_edge.fact_embedding is None}")
        if old_edge.fact_embedding is not None:
            logger.info(f"   - old_edge.fact_embedding type: {type(old_edge.fact_embedding)}")
            logger.info(f"   - old_edge.fact_embedding length: {len(old_edge.fact_embedding)}")
            logger.info(f"   - old_edge.fact_embedding first 3: {old_edge.fact_embedding[:3]}")
        else:
            logger.warning(f"   ⚠️  old_edge.fact_embedding is None!")

        # Mark old fact as expired
        logger.info(f"⏰ Marking old edge as expired...")
        expired_at = datetime.now()
        logger.info(f"   - expired_at to set: {expired_at}")
        logger.info(f"   - old_edge.fact_embedding is None: {old_edge.fact_embedding is None}")

        # Update expired_at directly with Cypher query to avoid fact_embedding issue
        logger.info(f"💾 Updating expired_at directly in Neo4j (bypassing save())...")
        try:
            query = """
            MATCH ()-[e:RELATES_TO {uuid: $uuid}]->()
            SET e.expired_at = $expired_at
            RETURN e.uuid AS uuid
            """
            # Use Neo4j driver session directly to avoid parameter issues
            async with client.driver.session() as session:
                result = await session.run(query, uuid=old_uuid, expired_at=expired_at)
                records = [record async for record in result]
                logger.info(f"   ✅ Old edge expired_at updated successfully via direct Cypher query")
                logger.info(f"      - Updated {len(records)} record(s)")
        except Exception as update_error:
            logger.error(f"   ❌ Failed to update old edge expired_at")
            logger.error(f"      - Exception type: {type(update_error).__name__}")
            logger.error(f"      - Exception message: {str(update_error)}")
            logger.exception("      - Full traceback:")
            raise

        # Determine source and target nodes
        logger.info(f"🔗 Determining source and target nodes...")
        source_uuid = update_request.source_node_uuid or old_edge.source_node_uuid
        target_uuid = update_request.target_node_uuid or old_edge.target_node_uuid
        logger.info(f"   - source_uuid: {source_uuid}")
        logger.info(f"   - target_uuid: {target_uuid}")

        # Generate embedding for the new fact
        logger.info("=" * 80)
        logger.info("Starting embedding generation for fact update")
        logger.info(f"Fact text (first 100 chars): {update_request.fact[:100]}...")
        logger.info(f"Fact text length: {len(update_request.fact)}")

        try:
            # Check embedder availability
            logger.info(f"Checking embedder: {client.embedder}")
            logger.info(f"Embedder type: {type(client.embedder)}")

            if client.embedder is None:
                raise ValueError("Embedder is not initialized (client.embedder is None)")

            # Attempt to generate embedding
            logger.info("Calling client.embedder.create()...")
            embedding_vector = await client.embedder.create(input_data=update_request.fact)

            # Detailed logging of the result
            logger.info(f"✅ Embedding generation completed successfully")
            logger.info(f"   - Type: {type(embedding_vector)}")
            logger.info(f"   - Is None: {embedding_vector is None}")
            logger.info(f"   - Is list: {isinstance(embedding_vector, list)}")

            if embedding_vector is not None:
                logger.info(f"   - Length: {len(embedding_vector)}")
                if len(embedding_vector) > 0:
                    logger.info(f"   - First 3 values: {embedding_vector[:3]}")
                    logger.info(f"   - Sample value type: {type(embedding_vector[0])}")
            else:
                logger.warning(f"   - Value is None!")

            logger.info(f"   - String representation (first 200 chars): {str(embedding_vector)[:200]}")

        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"❌ Failed to generate embedding for new fact")
            logger.error(f"   - Exception type: {type(e).__name__}")
            logger.error(f"   - Exception message: {str(e)}")
            logger.exception("   - Full traceback:")
            logger.error("=" * 80)
            return JSONResponse(
                APIErrorResponse(
                    error=f"Failed to generate embedding for new fact: {e}",
                    status_code=500,
                ).model_dump(),
                status_code=500,
            )

        # Validation checks
        logger.info("Validating embedding vector...")

        if embedding_vector is None:
            logger.error("❌ Validation failed: embedding_vector is None")
            return JSONResponse(
                APIErrorResponse(
                    error="Embedding vector is None after generation",
                    status_code=500,
                ).model_dump(),
                status_code=500,
            )

        if not isinstance(embedding_vector, list):
            logger.error(f"❌ Validation failed: embedding_vector is not a list, got {type(embedding_vector)}")
            return JSONResponse(
                APIErrorResponse(
                    error=f"Embedding vector must be a list, got {type(embedding_vector)}",
                    status_code=500,
                ).model_dump(),
                status_code=500,
            )

        if len(embedding_vector) == 0:
            logger.error("❌ Validation failed: embedding_vector is empty list")
            return JSONResponse(
                APIErrorResponse(
                    error="Embedding vector is empty",
                    status_code=500,
                ).model_dump(),
                status_code=500,
            )

        logger.info(f"✅ Validation passed: embedding_vector is valid list with {len(embedding_vector)} elements")
        logger.info("=" * 80)

        # Create new fact
        logger.info("=" * 80)
        logger.info("Creating new EntityEdge object...")
        logger.info(f"   - source_node_uuid: {source_uuid}")
        logger.info(f"   - target_node_uuid: {target_uuid}")
        logger.info(f"   - group_id: {old_edge.group_id}")
        logger.info(f"   - fact: {update_request.fact[:100]}...")
        logger.info(f"   - fact_embedding type: {type(embedding_vector)}")
        logger.info(f"   - fact_embedding length: {len(embedding_vector)}")

        # Generate new UUID for the new edge
        import uuid as uuid_lib
        new_uuid = str(uuid_lib.uuid4())
        logger.info(f"   - Generated new UUID: {new_uuid}")

        # Prepare attributes dictionary
        edge_attributes = update_request.attributes.copy() if update_request.attributes else {}

        new_edge = EntityEdge(
            uuid=new_uuid,
            name=update_request.fact,
            fact=update_request.fact,
            fact_embedding=embedding_vector,
            episodes=old_edge.episodes,  # Inherit episodes from old edge to preserve citations
            created_at=datetime.now(),
            expired_at=None,
            invalid_at=None,
            group_id=old_edge.group_id,
            source_node_uuid=source_uuid,
            target_node_uuid=target_uuid,
        )

        logger.info(f"✅ EntityEdge object created successfully")
        logger.info(f"   - new_edge.uuid: {new_edge.uuid}")
        logger.info(f"   - new_edge.fact_embedding is None: {new_edge.fact_embedding is None}")
        logger.info(f"   - new_edge.fact_embedding type: {type(new_edge.fact_embedding)}")
        if new_edge.fact_embedding is not None:
            logger.info(f"   - new_edge.fact_embedding length: {len(new_edge.fact_embedding)}")
            logger.info(f"   - new_edge.fact_embedding first 3: {new_edge.fact_embedding[:3]}")

        # Store custom attributes (like update_reason) in Neo4j properties
        if edge_attributes:
            logger.info(f"Custom attributes to store: {list(edge_attributes.keys())}")

        # Save new edge
        logger.info("Attempting to save new EntityEdge to Neo4j...")
        try:
            await new_edge.save(client.driver)
            logger.info(f"✅ EntityEdge saved successfully")
            logger.info(f"   - Saved UUID: {new_edge.uuid}")

            # Add custom attributes to Neo4j after saving
            if edge_attributes:
                logger.info(f"Adding custom attributes to Neo4j edge...")
                async with client.driver.session() as session:
                    set_clauses = ", ".join([f"e.{key} = ${key}" for key in edge_attributes.keys()])
                    query = f"""
                    MATCH ()-[e:RELATES_TO {{uuid: $uuid}}]->()
                    SET {set_clauses}
                    RETURN e.uuid AS uuid
                    """
                    await session.run(query, uuid=new_uuid, **edge_attributes)
                    logger.info(f"   ✅ Custom attributes added: {list(edge_attributes.keys())}")

            logger.info("=" * 80)
        except Exception as save_error:
            logger.error("=" * 80)
            logger.error(f"❌ Failed to save EntityEdge to Neo4j")
            logger.error(f"   - Exception type: {type(save_error).__name__}")
            logger.error(f"   - Exception message: {str(save_error)}")
            logger.error(f"   - new_edge.fact_embedding at save time: {new_edge.fact_embedding is not None}")
            if new_edge.fact_embedding is not None:
                logger.error(f"   - new_edge.fact_embedding length: {len(new_edge.fact_embedding)}")
            logger.exception("   - Full traceback:")
            logger.error("=" * 80)
            raise

        # Fetch the new edge with citations for response
        logger.info("📚 Fetching citations for new edge...")
        new_edge_with_citations = await format_fact_result(new_edge, client.driver)
        logger.info(f"   ✅ Citations fetched: {len(new_edge_with_citations.get('citations', []))} citation(s)")

        response = FactUpdateResponse(
            status="updated",
            old_uuid=old_uuid,
            new_uuid=new_edge.uuid,
            message=f"Fact updated successfully. Old fact {old_uuid} expired, new fact {new_edge.uuid} created",
            new_edge=new_edge_with_citations,
        )

        return create_cors_response(response.model_dump())

    except Exception as e:
        logger.error(f"Error updating fact: {e}")
        return create_cors_response(
            APIErrorResponse(error=str(e), status_code=500).model_dump(),
            status_code=500,
        )
