"""Data classes for episode management."""

from datetime import datetime

from graphiti_core.nodes import EpisodeType
from pydantic import BaseModel, Field


class EpisodeData(BaseModel):
    """Data class for episode information."""

    name: str = Field(..., description="Name of the episode")
    episode_body: str = Field(..., description="The content of the episode")
    group_id: str | None = Field(default=None, description="Group ID for the episode")
    source: str = Field(default="text", description="Source type (text, json, message)")
    source_description: str = Field(default="", description="Description of the source")
    source_url: str | None = Field(default=None, description="URL of the source")
    uuid: str | None = Field(default=None, description="Optional UUID for the episode")
    reference_time: str | None = Field(
        default=None,
        description="ISO 8601 timestamp when the episode occurred",
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "name": "Company News",
                "episode_body": "Acme Corp announced a new product line today.",
                "source": "text",
                "source_description": "news article",
                "group_id": "main",
            }
        }


class EpisodeProcessingConfig(BaseModel):
    """Configuration for episode processing."""

    group_id: str = Field(..., description="The group ID for the episode")
    name: str = Field(..., description="Name of the episode")
    content: str = Field(..., description="Episode content")
    source_description: str = Field(..., description="Description of the episode source")
    source_url: str | None = Field(default=None, description="URL of the source")
    episode_type: EpisodeType = Field(..., description="Type of the episode")
    entity_types: list[dict[str, str]] = Field(..., description="Entity types for extraction")
    uuid: str | None = Field(default=None, description="Episode UUID")
    reference_time: datetime | None = Field(
        default=None,
        description="Timestamp when the episode occurred",
    )

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True
