"""
Data model definitions
"""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class CitationInfo(BaseModel):
    """Citation information for an entity"""
    episode_uuid: str
    episode_name: str
    source: str
    source_description: str
    created_at: str | None = None
    source_url: str | None = None


class EntityNode(BaseModel):
    """Entity node"""
    uuid: str
    name: str
    summary: str | None = None
    created_at: datetime
    labels: list[str] = []
    attributes: dict[str, Any] = {}


class EntityEdge(BaseModel):
    """Relationship between entities"""
    uuid: str
    source_node_uuid: str
    target_node_uuid: str
    name: str
    fact: str
    created_at: datetime
    valid_at: datetime | None = None
    invalid_at: datetime | None = None
    expired_at: datetime | None = None
    episodes: list[str] = []
    citations: list[CitationInfo] = []
    # Fact update history fields
    updated_at: datetime | None = None
    original_fact: str | None = None
    update_reason: str | None = None


class SearchResult(BaseModel):
    """Search result"""
    nodes: list[EntityNode] = []
    edges: list[EntityEdge] = []
    total_count: int = 0


class ChatMessage(BaseModel):
    """Chat message"""
    role: str = Field(..., description="user or assistant")
    content: str


class ChatRequest(BaseModel):
    """Chat request"""
    message: str
    history: list[ChatMessage] = []
    include_search_results: bool = True


class ChatResponse(BaseModel):
    """Chat response"""
    answer: str
    search_results: SearchResult | None = None
    sources: list[str] = []


class ManualSearchRequest(BaseModel):
    """Manual search request"""
    query: str
    limit: int = 10


class UpdateFactRequest(BaseModel):
    """Fact update request"""
    edge_uuid: str
    new_fact: str
    reason: str | None = None


class UpdateFactResponse(BaseModel):
    """Fact update response"""
    success: bool
    message: str
    updated_edge: EntityEdge | None = None


class AddEpisodeRequest(BaseModel):
    """Episode addition request"""
    name: str
    content: str
    source: str = "user_input"
    source_description: str | None = None


class AddEpisodeResponse(BaseModel):
    """Episode addition response"""
    success: bool
    message: str
    episode_uuid: str | None = None