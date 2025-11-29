#!/usr/bin/env python3
"""Ingest data from saved JSON files into Graphiti.

This script allows you to ingest data from previously saved JSON files
without re-fetching from the source (Slack, GitHub, Zoom, etc.).
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.slack import SlackIngester
from ingestion.github import GitHubIngester
from ingestion.zoom import ZoomIngester
from ingestion.mcp_client import MCPClient


async def ingest_from_json(
    json_file: Path,
    source_type: str,
    mcp_url: str,
    clear_existing: bool = False,
):
    """
    Ingest data from a JSON file into Graphiti.

    Args:
        json_file: Path to the JSON file
        source_type: Type of source (slack, github, zoom)
        mcp_url: MCP server URL
        clear_existing: Whether to clear existing graph data
    """
    print(f"📂 Loading data from: {json_file}")

    # Load JSON file
    with open(json_file, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    # Extract data based on source type
    if "data" in json_data:
        data = json_data["data"]
        source_type_from_file = json_data.get("source_type", source_type)
    elif "messages" in json_data:
        # Handle Slack export format with "messages" key
        raw_messages = json_data["messages"]
        source_type_from_file = "slack"

        # Transform raw Slack messages into the format expected by build_episode
        # Group messages by thread
        threads = {}
        standalone = []

        for msg in raw_messages:
            if msg.get("thread_ts"):
                thread_ts = msg["thread_ts"]
                if thread_ts not in threads:
                    threads[thread_ts] = []
                threads[thread_ts].append(msg)
            else:
                standalone.append(msg)

        # Convert to expected format
        data = []
        for thread_ts, thread_msgs in threads.items():
            thread_msgs.sort(key=lambda m: float(m.get("ts", 0)))
            data.append({"type": "thread", "thread_ts": thread_ts, "messages": thread_msgs})

        for msg in standalone:
            data.append({"type": "standalone", "message": msg})
    else:
        # Assume the file contains raw data
        data = json_data
        source_type_from_file = source_type

    print(f"✓ Loaded {len(data)} items")
    print(f"📍 Source type: {source_type_from_file}")

    # Create appropriate ingester based on source type
    # We need to create a mock ingester that doesn't fetch data
    mcp_client = MCPClient(mcp_url)

    if source_type_from_file == "slack":
        # Create a minimal SlackIngester just for building episodes
        # Get channel_id and workspace_id from JSON if available
        channel_id = json_data.get("channel_id", "dummy")
        workspace_id = json_data.get("workspace_id", "dummy")

        ingester = SlackIngester(
            token="dummy",  # Not used for JSON ingestion
            channel_id=channel_id,
            workspace_id=workspace_id,
            mcp_url=mcp_url,
            translate=False,  # Already translated
            save_to_disk=False,
        )
    elif source_type_from_file == "github":
        ingester = GitHubIngester(
            token="dummy",
            owner="dummy",
            repo="dummy",
            mcp_url=mcp_url,
            translate=False,
            save_to_disk=False,
        )
    elif source_type_from_file == "zoom":
        ingester = ZoomIngester(
            data_dir="dummy",
            mcp_url=mcp_url,
            translate=False,
            save_to_disk=False,
        )
    else:
        raise ValueError(f"Unsupported source type: {source_type_from_file}")

    # Ingest into Graphiti
    print(f"🚀 Starting ingestion into Graphiti...")

    async with mcp_client.connect() as session:
        # Clear existing data if requested
        if clear_existing:
            print("🗑️  Clearing existing graph data...")
            await mcp_client.clear_graph(session)

        # Ingest items
        success_count = 0
        error_count = 0

        from tqdm import tqdm

        for item in tqdm(data, desc=f"Ingesting {source_type_from_file} items"):
            try:
                episode = ingester.build_episode(item)
                await mcp_client.add_episode(session, **episode)
                success_count += 1
            except Exception as e:
                error_count += 1
                print(f"✗ Error processing item: {e}")

        # Print summary
        print("\n" + "=" * 60)
        print("📊 Ingestion Summary")
        print("=" * 60)
        print(f"Source: {source_type_from_file}")
        print(f"Total items: {len(data)}")
        print(f"✓ Success: {success_count}")
        print(f"✗ Errors: {error_count}")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest data from saved JSON files into Graphiti"
    )
    parser.add_argument(
        "--json-file",
        required=True,
        help="Path to the JSON file to ingest",
    )
    parser.add_argument(
        "--source-type",
        choices=["slack", "github", "zoom"],
        help="Source type (slack, github, zoom). Auto-detected from JSON if not specified.",
    )
    parser.add_argument(
        "--mcp-url",
        default="http://localhost:8001/mcp",
        help="MCP server URL (default: http://localhost:8001/mcp)",
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Clear existing graph data before ingestion",
    )

    args = parser.parse_args()

    # Validate JSON file exists
    json_file = Path(args.json_file)
    if not json_file.exists():
        print(f"❌ Error: JSON file not found: {json_file}")
        sys.exit(1)

    # Auto-detect source type from filename if not specified
    source_type = args.source_type
    if not source_type:
        if "slack" in json_file.name:
            source_type = "slack"
        elif "github" in json_file.name or "issue" in json_file.name:
            source_type = "github"
        elif "zoom" in json_file.name or "transcript" in json_file.name:
            source_type = "zoom"
        else:
            print("❌ Error: Could not auto-detect source type from filename.")
            print("   Please specify --source-type explicitly.")
            sys.exit(1)

    asyncio.run(
        ingest_from_json(
            json_file=json_file,
            source_type=source_type,
            mcp_url=args.mcp_url,
            clear_existing=args.clear_existing,
        )
    )


if __name__ == "__main__":
    main()
