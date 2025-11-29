"""Memory management tools for adding, deleting, and clearing episodes."""

import logging
from datetime import datetime, timezone
from typing import Any

from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EpisodeType, EpisodicNode
from graphiti_core.utils.maintenance.graph_data_operations import clear_data
from models.episode_types import EpisodeProcessingConfig
from models.response_types import (EpisodeSearchResponse, ErrorResponse,
                                   SuccessResponse)
from services.service_container import ServiceContainer
from utils.formatting import format_fact_result

logger = logging.getLogger(__name__)


async def add_memory(
    name: str,
    episode_body: str,
    group_id: str | None = None,
    source: str = "text",
    source_description: str = "",
    source_url: str | None = None,
    uuid: str | None = None,
    reference_time: str | None = None,
) -> SuccessResponse | ErrorResponse:
    """Add an episode to memory. This is the primary way to add information to the graph.

    This function returns immediately and processes the episode addition in the background.
    Episodes for the same group_id are processed sequentially to avoid race conditions.

    Args:
        name (str): Name of the episode
        episode_body (str): The content of the episode to persist to memory. When source='json', this must be a
                           properly escaped JSON string, not a raw Python dictionary. The JSON data will be
                           automatically processed to extract entities and relationships.
        group_id (str, optional): A unique ID for this graph. If not provided, uses the default group_id from CLI
                                 or a generated one.
        source (str, optional): Source type, must be one of:
                               - 'text': For plain text content (default)
                               - 'json': For structured data
                               - 'message': For conversation-style content
        source_description (str, optional): Description of the source
        source_url (str, optional): URL of the source (e.g., Slack message link, GitHub issue URL)
        uuid (str, optional): Optional UUID for the episode
        reference_time (str, optional): ISO 8601 timestamp when the episode occurred (e.g., "2024-11-20T10:30:00Z").
                                       If not provided, current time will be used.

    Examples:
        # Adding plain text content
        add_memory(
            name="Company News",
            episode_body="Acme Corp announced a new product line today.",
            source="text",
            source_description="news article",
            group_id="some_arbitrary_string"
        )

        # Adding structured JSON data
        # NOTE: episode_body should be a JSON string (standard JSON escaping)
        add_memory(
            name="Customer Profile",
            episode_body='{"company": {"name": "Acme Technologies"}, "products": [{"id": "P001", "name": "CloudSync"}, {"id": "P002", "name": "DataMiner"}]}',
            source="json",
            source_description="CRM data"
        )
    """
    try:
        graphiti_service = ServiceContainer.get_graphiti_service()
        queue_service = ServiceContainer.get_queue_service()
        config = ServiceContainer.get_config()
    except RuntimeError as e:
        return ErrorResponse(error=str(e))

    try:
        # Use the provided group_id or fall back to the default from config
        effective_group_id = group_id or config.graphiti.group_id

        # Try to parse the source as an EpisodeType enum, with fallback to text
        episode_type = EpisodeType.text  # Default
        if source:
            try:
                episode_type = EpisodeType[source.lower()]
            except (KeyError, AttributeError):
                # If the source doesn't match any enum value, use text as default
                logger.warning(
                    f"Unknown source type '{source}', using 'text' as default"
                )
                episode_type = EpisodeType.text

        # Parse reference_time if provided
        parsed_reference_time = None
        if reference_time:
            try:
                parsed_reference_time = datetime.fromisoformat(
                    reference_time.replace("Z", "+00:00")
                )
                # Ensure it's in UTC
                if parsed_reference_time.tzinfo is None:
                    parsed_reference_time = parsed_reference_time.replace(
                        tzinfo=timezone.utc
                    )
            except (ValueError, AttributeError) as e:
                logger.warning(
                    f"Invalid reference_time format '{reference_time}': {e}. Using current time."
                )
                parsed_reference_time = None

        # Create episode processing configuration
        episode_config = EpisodeProcessingConfig(
            group_id=effective_group_id,
            name=name,
            content=episode_body,
            source_description=source_description,
            source_url=source_url,
            episode_type=episode_type,
            entity_types=graphiti_service.entity_types or [],
            uuid=uuid or None,
            reference_time=parsed_reference_time,
        )

        await queue_service.add_episode(episode_config)

        return SuccessResponse(
            message=f"Episode '{name}' queued for processing in group '{effective_group_id}'"
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error queuing episode: {error_msg}")
        return ErrorResponse(error=f"Error queuing episode: {error_msg}")


async def clear_graph(
    group_ids: list[str] | None = None,
) -> SuccessResponse | ErrorResponse:
    """Clear all data from the graph for specified group IDs.

    Args:
        group_ids: Optional list of group IDs to clear. If not provided, clears the default group.
    """
    try:
        graphiti_service = ServiceContainer.get_graphiti_service()
        config = ServiceContainer.get_config()
    except RuntimeError as e:
        return ErrorResponse(error=str(e))

    try:
        client = await graphiti_service.get_client()

        # Use the provided group_ids or fall back to the default from config if none provided
        effective_group_ids = (
            group_ids or [config.graphiti.group_id] if config.graphiti.group_id else []
        )

        if not effective_group_ids:
            return ErrorResponse(error="No group IDs specified for clearing")

        # Clear data for the specified group IDs
        await clear_data(client.driver, group_ids=effective_group_ids)

        return SuccessResponse(
            message=f"Graph data cleared successfully for group IDs: {', '.join(effective_group_ids)}"
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error clearing graph: {error_msg}")
        return ErrorResponse(error=f"Error clearing graph: {error_msg}")


async def delete_episode(uuid: str) -> SuccessResponse | ErrorResponse:
    """Delete an episode from the graph memory.

    Args:
        uuid: UUID of the episode to delete
    """
    try:
        graphiti_service = ServiceContainer.get_graphiti_service()
    except RuntimeError as e:
        return ErrorResponse(error=str(e))

    try:
        client = await graphiti_service.get_client()

        # Get the episodic node by UUID
        episodic_node = await EpisodicNode.get_by_uuid(client.driver, uuid)
        # Delete the node using its delete method
        await episodic_node.delete(client.driver)
        return SuccessResponse(message=f"Episode with UUID {uuid} deleted successfully")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error deleting episode: {error_msg}")
        return ErrorResponse(error=f"Error deleting episode: {error_msg}")


async def delete_entity_edge(uuid: str) -> SuccessResponse | ErrorResponse:
    """Delete an entity edge from the graph memory.

    Args:
        uuid: UUID of the entity edge to delete
    """
    try:
        graphiti_service = ServiceContainer.get_graphiti_service()
    except RuntimeError as e:
        return ErrorResponse(error=str(e))

    try:
        client = await graphiti_service.get_client()

        # Get the entity edge by UUID
        entity_edge = await EntityEdge.get_by_uuid(client.driver, uuid)
        # Delete the edge using its delete method
        await entity_edge.delete(client.driver)
        return SuccessResponse(
            message=f"Entity edge with UUID {uuid} deleted successfully"
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error deleting entity edge: {error_msg}")
        return ErrorResponse(error=f"Error deleting entity edge: {error_msg}")


async def get_entity_edge(uuid: str) -> dict[str, Any] | ErrorResponse:
    """Get an entity edge from the graph memory by its UUID.

    Args:
        uuid: UUID of the entity edge to retrieve
    """
    try:
        graphiti_service = ServiceContainer.get_graphiti_service()
    except RuntimeError as e:
        return ErrorResponse(error=str(e))

    try:
        client = await graphiti_service.get_client()

        # Get the entity edge directly using the EntityEdge class method
        entity_edge = await EntityEdge.get_by_uuid(client.driver, uuid)

        # Use the format_fact_result function to serialize the edge
        # Return the Python dict directly - MCP will handle serialization
        return format_fact_result(entity_edge)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error getting entity edge: {error_msg}")
        return ErrorResponse(error=f"Error getting entity edge: {error_msg}")


async def get_episodes(
    group_ids: list[str] | None = None,
    max_episodes: int = 10,
) -> EpisodeSearchResponse | ErrorResponse:
    """Get episodes from the graph memory.

    Args:
        group_ids: Optional list of group IDs to filter results
        max_episodes: Maximum number of episodes to return (default: 10)
    """
    try:
        graphiti_service = ServiceContainer.get_graphiti_service()
        config = ServiceContainer.get_config()
    except RuntimeError as e:
        return ErrorResponse(error=str(e))

    try:
        client = await graphiti_service.get_client()

        # Use the provided group_ids or fall back to the default from config if none provided
        effective_group_ids = (
            group_ids
            if group_ids is not None
            else [config.graphiti.group_id]
            if config.graphiti.group_id
            else []
        )

        # Get episodes from the driver directly
        if effective_group_ids:
            episodes = await EpisodicNode.get_by_group_ids(
                client.driver, effective_group_ids, limit=max_episodes
            )
        else:
            # If no group IDs, we need to use a different approach
            # For now, return empty list when no group IDs specified
            episodes = []

        if not episodes:
            return EpisodeSearchResponse(message="No episodes found", episodes=[])

        # Format the results
        episode_results = []
        for episode in episodes:
            episode_dict = {
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
            episode_results.append(episode_dict)

        return EpisodeSearchResponse(
            message="Episodes retrieved successfully", episodes=episode_results
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error getting episodes: {error_msg}")
        return ErrorResponse(error=f"Error getting episodes: {error_msg}")
