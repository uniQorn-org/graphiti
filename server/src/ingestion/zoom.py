"""Zoom transcript ingestion."""

from pathlib import Path
from typing import Any

import boto3

from .base import BaseIngester
from .config import ZoomIngestionConfig
from .utils import build_minio_url


class ZoomIngester(BaseIngester):
    """Ingester for Zoom VTT transcripts."""

    def __init__(self, config: ZoomIngestionConfig, **kwargs):
        """
        Initialize Zoom ingester.

        Args:
            config: Zoom ingestion configuration
            **kwargs: Additional arguments for BaseIngester
        """
        super().__init__(**kwargs)
        self.vtt_dir = Path(config.data_dir)
        self.minio_endpoint = config.minio_endpoint
        self.minio_public_endpoint = (
            config.minio_public_endpoint or config.minio_endpoint
        )
        self.bucket_name = config.bucket_name

        # Initialize MinIO client
        self.minio_client = boto3.client(
            "s3",
            endpoint_url=f"http://{config.minio_endpoint}",
            aws_access_key_id=config.minio_access_key,
            aws_secret_access_key=config.minio_secret_key,
        )

        # Create bucket if not exists
        try:
            self.minio_client.head_bucket(Bucket=self.bucket_name)
        except Exception:
            # Bucket doesn't exist or other error - try to create it
            self.minio_client.create_bucket(Bucket=self.bucket_name)
            print(f"Created MinIO bucket: {self.bucket_name}")

    def get_source_type(self) -> str:
        """Get source type identifier."""
        return "zoom"

    def _should_skip_line(self, line: str) -> bool:
        """Check if line should be skipped (WEBVTT header or empty)."""
        return line.startswith("WEBVTT") or not line

    def _is_timestamp_line(self, line: str) -> bool:
        """Check if line is a timestamp (format: timestamp --> timestamp)."""
        return "-->" in line

    def _process_vtt_line(
        self, line: str, current_message: dict, messages: list[dict]
    ) -> dict:
        """
        Process a single VTT line and update current message.

        Args:
            line: Line to process
            current_message: Current message being built
            messages: List of completed messages

        Returns:
            Updated current message
        """
        # Skip header and empty lines
        if self._should_skip_line(line):
            return current_message

        # New timestamp starts a new message
        if self._is_timestamp_line(line):
            if current_message.get("text"):
                messages.append(current_message)
            return {"timestamp": line}

        # Speaker name follows timestamp
        if current_message.get("timestamp") and not current_message.get("speaker"):
            current_message["speaker"] = line
            return current_message

        # Message text follows speaker
        if current_message.get("speaker"):
            if "text" not in current_message:
                current_message["text"] = line
            else:
                current_message["text"] += " " + line

        return current_message

    def _parse_vtt(self, vtt_content: str) -> list[dict]:
        """
        Parse VTT file and extract messages.

        Args:
            vtt_content: VTT file content

        Returns:
            List of message dictionaries with speaker and text
        """
        lines = vtt_content.split("\n")
        messages = []
        current_message = {}

        for line in lines:
            current_message = self._process_vtt_line(
                line.strip(), current_message, messages
            )

        # Add final message if exists
        if current_message.get("text"):
            messages.append(current_message)

        return messages

    async def fetch_data(self) -> list[dict[str, Any]]:
        """
        Fetch Zoom VTT files.

        Returns:
            List of transcript data dictionaries
        """
        # Find VTT files
        vtt_files = list(self.vtt_dir.glob("*.vtt"))

        if not vtt_files:
            print(f"No VTT files found in {self.vtt_dir}")
            return []

        print(f"Found {len(vtt_files)} VTT file(s)")

        # Process each file
        transcripts_data = []

        for vtt_file in vtt_files:
            # Read VTT file
            with open(vtt_file, "r", encoding="utf-8") as f:
                vtt_content = f.read()

            # Parse VTT
            messages = self._parse_vtt(vtt_content)

            # Upload to MinIO
            object_key = vtt_file.name
            self.minio_client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=vtt_content.encode("utf-8"),
                ContentType="text/vtt",
            )

            # Build source URL
            source_url = build_minio_url(self.minio_public_endpoint, self.bucket_name, object_key)

            # Extract meeting ID
            meeting_id = vtt_file.stem.replace("_transcript", "")

            transcripts_data.append(
                {
                    "meeting_id": meeting_id,
                    "filename": vtt_file.name,
                    "messages": messages,
                    "source_url": source_url,
                }
            )

        return transcripts_data

    def build_episode(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Convert transcript data into episode format.

        Args:
            data: Transcript data dictionary

        Returns:
            Episode dictionary
        """
        # Build conversation from messages
        conversation_lines = []
        for msg in data["messages"]:
            speaker = msg.get("speaker", "Unknown")
            text = msg.get("text", "")

            # Translate if enabled
            if text:
                text = self.translate_text(text, max_chars=500)

            conversation_lines.append(f"{speaker}: {text}")

        conversation = "\n".join(conversation_lines)

        # Create episode
        episode_name = f"zoom:meeting:{data['meeting_id']}"
        source_description = (
            f"Zoom meeting transcript, "
            f"file: {data['filename']}, "
            f"messages: {len(data['messages'])}"
        )

        return {
            "name": episode_name,
            "episode_body": conversation,
            "source": "message",
            "source_description": source_description,
            "source_url": data["source_url"],
        }
