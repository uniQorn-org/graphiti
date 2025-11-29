"""Configuration classes for data ingestion."""

from pathlib import Path

from pydantic import BaseModel, Field


class IngestionConfig(BaseModel):
    """Base configuration for all ingesters."""

    translate_to_english: bool = Field(
        default=False, description="Whether to translate content to English"
    )
    enable_deduplication: bool = Field(
        default=True, description="Whether to enable deduplication"
    )
    chunk_size: int = Field(default=1000, description="Chunk size for processing")

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True


class SlackIngestionConfig(IngestionConfig):
    """Configuration for Slack ingestion."""

    api_token: str = Field(..., description="Slack API token")
    channel_id: str = Field(..., description="Slack channel ID")
    oldest_timestamp: str | None = Field(
        default=None, description="Oldest message timestamp to fetch"
    )
    time_window: str = Field(
        default="1H", description="Time window for grouping messages"
    )


class GitHubIngestionConfig(IngestionConfig):
    """Configuration for GitHub ingestion."""

    access_token: str = Field(..., description="GitHub access token")
    repo_owner: str = Field(..., description="Repository owner")
    repo_name: str = Field(..., description="Repository name")
    issue_number: int | None = Field(
        default=None, description="Specific issue number to fetch"
    )


class ZoomIngestionConfig(IngestionConfig):
    """Configuration for Zoom transcript ingestion."""

    data_dir: str | Path = Field(..., description="Directory containing VTT files")
    minio_endpoint: str = Field(
        default="localhost:20734", description="MinIO endpoint"
    )
    minio_public_endpoint: str | None = Field(
        default=None, description="MinIO public endpoint for browser access"
    )
    minio_access_key: str = Field(default="minio", description="MinIO access key")
    minio_secret_key: str = Field(
        default="miniosecret", description="MinIO secret key"
    )
    bucket_name: str = Field(
        default="zoom-transcripts", description="MinIO bucket name"
    )
