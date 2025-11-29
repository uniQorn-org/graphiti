"""Group ID utility functions."""

from typing import Any


def get_effective_group_ids(
    group_ids: list[str] | None, config: Any
) -> list[str]:
    """
    Get effective group IDs for a request.

    Args:
        group_ids: Requested group IDs (None means use default)
        config: Configuration object with graphiti.group_id attribute

    Returns:
        List of effective group IDs to use
    """
    return (
        group_ids
        if group_ids is not None
        else [config.graphiti.group_id]
        if config.graphiti.group_id
        else []
    )
