#!/usr/bin/env python3
"""
Zoom transcript ingestion script for Graphiti MCP.

Reads VTT files from data/zoom/, parses them, uploads to MinIO,
and adds episodes to Graphiti with source URLs.
"""

import argparse
import asyncio
import os
import re
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from tqdm import tqdm


def parse_vtt_file(vtt_path: Path) -> list[dict[str, str]]:
    """Parse a VTT file and extract speaker and text.

    Args:
        vtt_path: Path to VTT file

    Returns:
        List of dicts with 'speaker' and 'text' keys
    """
    with open(vtt_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by double newlines to get cue blocks
    blocks = re.split(r"\n\n+", content)

    messages = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        # Skip WEBVTT header
        if "WEBVTT" in block:
            continue

        # Find the timestamp line and text line
        timestamp_idx = -1
        for i, line in enumerate(lines):
            if "-->" in line:
                timestamp_idx = i
                break

        if timestamp_idx == -1:
            continue

        # Text is everything after the timestamp line
        text_lines = lines[timestamp_idx + 1:]
        text = " ".join(text_lines).strip()

        if not text:
            continue

        # Extract speaker (format: "speaker: text")
        if ":" in text:
            parts = text.split(":", 1)
            if len(parts) == 2:
                speaker, message = parts
                messages.append({"speaker": speaker.strip(), "text": message.strip()})
            else:
                messages.append({"speaker": "Unknown", "text": text})
        else:
            # No speaker identified, use generic
            messages.append({"speaker": "Unknown", "text": text})

    return messages


def format_conversation(messages: list[dict[str, str]]) -> str:
    """Format messages into Graphiti EpisodeType.message format.

    Args:
        messages: List of message dicts

    Returns:
        Formatted conversation string
    """
    lines = []
    for msg in messages:
        lines.append(f"{msg['speaker']}: {msg['text']}")
    return "\n".join(lines)


def upload_to_minio(
    file_path: Path,
    bucket: str,
    object_name: str,
    minio_endpoint: str,
    access_key: str,
    secret_key: str,
    public_endpoint: str | None = None,
) -> str:
    """Upload file to MinIO.

    Args:
        file_path: Local file path
        bucket: MinIO bucket name
        object_name: Object key in MinIO
        minio_endpoint: MinIO endpoint (e.g., localhost:9002)
        access_key: MinIO access key
        secret_key: MinIO secret key
        public_endpoint: Public MinIO endpoint for URL generation (default: same as minio_endpoint)

    Returns:
        Public URL to the uploaded file
    """
    s3_client = boto3.client(
        "s3",
        endpoint_url=f"http://{minio_endpoint}",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )

    # Upload file
    s3_client.upload_file(str(file_path), bucket, object_name)

    # Return public URL
    endpoint_for_url = public_endpoint or minio_endpoint
    return f"http://{endpoint_for_url}/{bucket}/{object_name}"


async def ingest_zoom_transcripts(
    session: ClientSession,
    zoom_dir: Path,
    minio_endpoint: str = "localhost:9002",
    minio_access_key: str = "minio",
    minio_secret_key: str = "miniosecret",
    minio_bucket: str = "zoom-transcripts",
    minio_public_endpoint: str | None = None,
) -> None:
    """Ingest Zoom transcripts into Graphiti.

    Args:
        session: MCP client session
        zoom_dir: Directory containing VTT files
        minio_endpoint: MinIO endpoint
        minio_access_key: MinIO access key
        minio_secret_key: MinIO secret key
        minio_bucket: MinIO bucket name
        minio_public_endpoint: Public MinIO endpoint for URL generation
    """
    vtt_files = list(zoom_dir.glob("*.vtt"))
    print(f"Found {len(vtt_files)} VTT files in {zoom_dir}")

    for vtt_file in tqdm(vtt_files, desc="Ingesting Zoom transcripts"):
        try:
            # Parse VTT file
            messages = parse_vtt_file(vtt_file)
            if not messages:
                print(f"⚠️  No messages found in {vtt_file.name}")
                continue

            # Upload to MinIO
            object_name = vtt_file.name
            source_url = upload_to_minio(
                vtt_file,
                minio_bucket,
                object_name,
                minio_endpoint,
                minio_access_key,
                minio_secret_key,
                minio_public_endpoint,
            )

            # Format conversation
            conversation = format_conversation(messages)

            # Extract UUID from filename (e.g., "3e2a9613-e2e9-4be9-bde1-7011c151c968_transcript.vtt")
            file_uuid = vtt_file.stem.replace("_transcript", "")

            # Create episode name
            episode_name = f"zoom:meeting:{file_uuid}"

            # Create source description
            source_description = f"Zoom meeting transcript, file: {vtt_file.name}, messages: {len(messages)}"

            # Add to Graphiti
            arguments = {
                "name": episode_name,
                "episode_body": conversation,
                "source": "message",
                "source_description": source_description,
                "source_url": source_url,
            }

            await session.call_tool("add_memory", arguments=arguments)
            print(f"✓ Ingested {vtt_file.name} -> {source_url}")

        except Exception as e:
            print(f"✗ Error processing {vtt_file.name}: {e}")


async def main():
    parser = argparse.ArgumentParser(
        description="Ingest Zoom transcripts into Graphiti MCP"
    )
    parser.add_argument(
        "--zoom-dir",
        type=str,
        default="data/zoom",
        help="Directory containing VTT files (default: data/zoom)",
    )
    parser.add_argument(
        "--minio-endpoint",
        type=str,
        default="localhost:20734",
        help="MinIO endpoint (default: localhost:20734)",
    )
    parser.add_argument(
        "--minio-access-key",
        type=str,
        default="minio",
        help="MinIO access key (default: minio)",
    )
    parser.add_argument(
        "--minio-secret-key",
        type=str,
        default="miniosecret",
        help="MinIO secret key (default: miniosecret)",
    )
    parser.add_argument(
        "--minio-bucket",
        type=str,
        default="zoom-transcripts",
        help="MinIO bucket name (default: zoom-transcripts)",
    )
    parser.add_argument(
        "--minio-public-endpoint",
        type=str,
        default=None,
        help="Public MinIO endpoint for URL generation (default: same as minio-endpoint)",
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Clear existing graph data before ingestion",
    )
    args = parser.parse_args()

    zoom_dir = Path(args.zoom_dir)
    if not zoom_dir.exists():
        print(f"Error: Directory {zoom_dir} does not exist")
        return

    async with streamablehttp_client("http://localhost:8001/mcp/") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            if args.clear_existing:
                print("Clearing existing graph data...")
                await session.call_tool("clear_graph", arguments={})

            await ingest_zoom_transcripts(
                session,
                zoom_dir,
                args.minio_endpoint,
                args.minio_access_key,
                args.minio_secret_key,
                args.minio_bucket,
                args.minio_public_endpoint,
            )


if __name__ == "__main__":
    asyncio.run(main())
