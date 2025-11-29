"""API type definitions for REST endpoints."""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ============================================================================
# Search Request/Response Types
# ============================================================================


class GraphSearchRequest(BaseModel):
    """Request model for graph search."""

    query: str = Field(..., description="Search query string")
    search_type: Literal["facts", "nodes", "episodes"] = Field(
        "facts", description="Type of search to perform"
    )
    max_results: int = Field(10, ge=1, le=100, description="Maximum number of results")
    group_ids: list[str] | None = Field(
        None, description="Optional list of group IDs to filter"
    )
    entity_types: list[str] | None = Field(
        None, description="Optional entity type filters for node search"
    )
    center_node_uuid: str | None = Field(
        None, description="Optional center node UUID for fact search"
    )


class GraphSearchResponse(BaseModel):
    """Response model for graph search."""

    message: str
    search_type: str
    results: list[dict[str, Any]]
    count: int


# ============================================================================
# Fact Management Request/Response Types
# ============================================================================


class FactUpdateRequest(BaseModel):
    """Request model for updating a fact."""

    fact: str = Field(..., description="New fact text/description")
    source_node_uuid: str | None = Field(
        None, description="UUID of source node (if changing)"
    )
    target_node_uuid: str | None = Field(
        None, description="UUID of target node (if changing)"
    )
    attributes: dict[str, Any] | None = Field(
        None, description="Optional attributes to add to the new fact"
    )


class FactUpdateResponse(BaseModel):
    """Response model for fact update."""

    status: str
    old_uuid: str
    new_uuid: str
    message: str
    new_edge: dict[str, Any] | None = Field(
        None, description="The newly created edge with citations"
    )


class FactDeleteResponse(BaseModel):
    """Response model for fact deletion."""

    status: str
    uuid: str
    message: str


# ============================================================================
# Episode Request/Response Types
# ============================================================================


class EpisodeCreateRequest(BaseModel):
    """Request model for creating an episode."""

    name: str = Field(..., description="Name of the episode")
    content: str = Field(..., description="Episode content/body")
    group_id: str | None = Field(
        None, description="Group ID (defaults to server default)"
    )
    source: Literal["text", "json", "message"] = Field(
        "text", description="Source type: text, json, or message"
    )
    source_description: str | None = Field(
        "", description="Description of the source"
    )
    source_url: str | None = Field(
        None, description="URL of the source (Slack message, GitHub issue, etc.)"
    )
    uuid: str | None = Field(None, description="Optional custom UUID")


class EpisodeCreateResponse(BaseModel):
    """Response model for episode creation."""

    status: str
    message: str
    episode_name: str
    group_id: str


class EpisodeListRequest(BaseModel):
    """Request model for episode list."""

    group_ids: list[str] | None = Field(
        None, description="Optional list of group IDs to filter"
    )
    max_episodes: int = Field(
        10, ge=1, le=100, description="Maximum number of episodes"
    )


# ============================================================================
# Generic Response Types
# ============================================================================


class APIErrorResponse(BaseModel):
    """Generic error response."""

    error: str
    details: str | None = None
    status_code: int = 500


class APISuccessResponse(BaseModel):
    """Generic success response."""

    message: str
    data: dict[str, Any] | None = None
