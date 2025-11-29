#!/usr/bin/env python3
"""
Zoom transcript ingestion CLI script.

This is a thin CLI wrapper around the ZoomIngester class.
"""

import argparse
import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ingestion.config import ZoomIngestionConfig
from ingestion.zoom import ZoomIngester


async def main():
    parser = argparse.ArgumentParser(
        description="Ingest Zoom transcripts into Graphiti MCP with English translation"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="/app/data/zoom",
        help="Directory containing VTT files",
    )
    parser.add_argument(
        "--minio-endpoint",
        type=str,
        default="localhost:20734",
        help="MinIO endpoint",
    )
    parser.add_argument(
        "--minio-public-endpoint",
        type=str,
        default=None,
        help="MinIO public endpoint (for browser access)",
    )
    parser.add_argument(
        "--minio-access-key",
        type=str,
        default="minio",
        help="MinIO access key",
    )
    parser.add_argument(
        "--minio-secret-key",
        type=str,
        default="miniosecret",
        help="MinIO secret key",
    )
    parser.add_argument(
        "--bucket-name",
        type=str,
        default="zoom-transcripts",
        help="MinIO bucket name",
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Clear existing graph data before ingestion",
    )
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="Do not translate content to English",
    )
    parser.add_argument(
        "--mcp-url",
        type=str,
        default="http://localhost:8001/mcp/",
        help="MCP server URL (default: http://localhost:8001/mcp/)",
    )
    args = parser.parse_args()

    # Create configuration
    zoom_config = ZoomIngestionConfig(
        data_dir=args.data_dir,
        minio_endpoint=args.minio_endpoint,
        minio_public_endpoint=args.minio_public_endpoint,
        minio_access_key=args.minio_access_key,
        minio_secret_key=args.minio_secret_key,
        bucket_name=args.bucket_name,
        translate_to_english=not args.no_translate,
    )

    # Create ingester
    ingester = ZoomIngester(
        config=zoom_config,
        mcp_url=args.mcp_url,
        save_to_disk=False,  # VTT files are already on disk
    )

    # Run ingestion
    await ingester.ingest(clear_existing=args.clear_existing)


if __name__ == "__main__":
    asyncio.run(main())
