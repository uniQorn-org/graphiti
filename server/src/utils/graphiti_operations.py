"""Common operations for Graphiti graph management.

This module contains shared utility functions used by both MCP tools and REST API endpoints
to avoid code duplication and ensure consistent behavior across different interfaces.
"""

import logging
from typing import Any

from config.schema import GraphitiConfig
from graphiti_core.nodes import EpisodeType
from graphiti_core.search.search_filters import SearchFilters

logger = logging.getLogger(__name__)


def normalize_episode_type(source: str | None) -> EpisodeType:
    """Convert a source string to an EpisodeType enum with safe fallback.

    Args:
        source: Source type string (e.g., "text", "json", "message")

    Returns:
        EpisodeType enum value. Defaults to EpisodeType.text if source is invalid.

    Examples:
        >>> normalize_episode_type("json")
        EpisodeType.json
        >>> normalize_episode_type("invalid")
        EpisodeType.text
        >>> normalize_episode_type(None)
        EpisodeType.text
    """
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

    return episode_type


def resolve_group_ids(
    provided_group_ids: list[str] | None,
    config: GraphitiConfig,
) -> list[str]:
    """Resolve group IDs with fallback to config default.

    Args:
        provided_group_ids: List of group IDs provided by the caller
        config: Graphiti configuration containing default group_id

    Returns:
        List of group IDs to use. Falls back to config default or empty list.

    Examples:
        >>> resolve_group_ids(["group1", "group2"], config)
        ["group1", "group2"]
        >>> resolve_group_ids(None, config)  # config.graphiti.group_id = "default"
        ["default"]
        >>> resolve_group_ids([], config)
        []
    """
    effective_group_ids = (
        provided_group_ids
        if provided_group_ids is not None
        else [config.graphiti.group_id]
        if config.graphiti.group_id
        else []
    )
    return effective_group_ids


def create_node_search_filters(
    entity_types: list[str] | None = None,
) -> SearchFilters:
    """Create SearchFilters for node search operations.

    Args:
        entity_types: Optional list of entity type labels to filter by

    Returns:
        SearchFilters object configured for node search

    Examples:
        >>> create_node_search_filters(["Person", "Organization"])
        SearchFilters(node_labels=["Person", "Organization"])
        >>> create_node_search_filters(None)
        SearchFilters(node_labels=None)
    """
    return SearchFilters(node_labels=entity_types)
