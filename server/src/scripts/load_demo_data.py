#!/usr/bin/env python3
"""Load demo data from data/ directory into Graphiti.

This script loads all available demo data (GitHub issues, Slack messages, Zoom transcripts)
from the data/ directory into the Graphiti knowledge graph.
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
from ingestion.mcp_client import MCPClient


async def load_demo_data(
    data_dir: Path,
    mcp_url: str,
    clear_existing: bool = False,
):
    """
    Load all demo data from data/ directory into Graphiti.

    Args:
        data_dir: Path to the data directory (default: ./data)
        mcp_url: MCP server URL
        clear_existing: Whether to clear existing graph data
    """
    print("=" * 70)
    print("🚀 Graphiti Demo Data Loader")
    print("=" * 70)
    print()

    # Find all data files
    github_files = list((data_dir / "github").glob("*.json"))
    slack_files = list((data_dir / "slack").glob("*.json"))
    zoom_files = list((data_dir / "zoom").glob("*.vtt"))

    print(f"📂 Scanning data directory: {data_dir}")
    print(f"   Found {len(github_files)} GitHub file(s)")
    print(f"   Found {len(slack_files)} Slack file(s)")
    print(f"   Found {len(zoom_files)} Zoom file(s)")
    print()

    if not github_files and not slack_files and not zoom_files:
        print("❌ No demo data files found in data/ directory!")
        print("   Please ensure data files are placed in:")
        print("   - data/github/*.json")
        print("   - data/slack/*.json")
        print("   - data/zoom/*.vtt")
        sys.exit(1)

    # Initialize MCP client
    mcp_client = MCPClient(mcp_url)

    total_success = 0
    total_errors = 0

    async with mcp_client.connect() as session:
        # Clear existing data if requested
        if clear_existing:
            print("🗑️  Clearing existing graph data...")
            await mcp_client.clear_graph(session)
            print("✓ Graph cleared")
            print()

        # Process GitHub files
        if github_files:
            print("-" * 70)
            print("📊 Processing GitHub Issues")
            print("-" * 70)
            for github_file in github_files:
                success, errors = await process_github_file(
                    github_file, mcp_client, session
                )
                total_success += success
                total_errors += errors
            print()

        # Process Slack files
        if slack_files:
            print("-" * 70)
            print("💬 Processing Slack Messages")
            print("-" * 70)
            for slack_file in slack_files:
                success, errors = await process_slack_file(
                    slack_file, mcp_client, session
                )
                total_success += success
                total_errors += errors
            print()

        # Process Zoom files
        if zoom_files:
            print("-" * 70)
            print("🎥 Processing Zoom Transcripts")
            print("-" * 70)
            for zoom_file in zoom_files:
                success, errors = await process_zoom_file(
                    zoom_file, mcp_client, session
                )
                total_success += success
                total_errors += errors
            print()

    # Print final summary
    print("=" * 70)
    print("📈 Demo Data Loading Complete!")
    print("=" * 70)
    print(f"✓ Successfully loaded: {total_success} items")
    if total_errors > 0:
        print(f"✗ Errors: {total_errors} items")
    print()
    print("🌐 Access your knowledge graph at:")
    print("   Frontend UI:  http://localhost:20002")
    print("   Neo4j Browser: http://localhost:20474 (user: neo4j, pass: password123)")
    print("=" * 70)


async def process_github_file(
    file_path: Path, mcp_client: MCPClient, session
) -> tuple[int, int]:
    """Process a GitHub issues JSON file."""
    print(f"📄 Loading: {file_path.name}")

    with open(file_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    # Check if this is actually GitHub data
    # Accept files with source_type="github" or files that have "issues" key (GitHub format)
    source_type = json_data.get("source_type")
    has_issues_key = "issues" in json_data

    if source_type and source_type != "github" and not has_issues_key:
        print(f"   ⚠️  File marked as '{source_type}', not GitHub data - skipping")
        return 0, 0

    # Extract data - handle both "data" and "issues" keys
    if "data" in json_data:
        data = json_data["data"]
    elif "issues" in json_data:
        data = json_data["issues"]
    else:
        data = json_data if isinstance(json_data, list) else [json_data]

    # Validate data structure (must have 'title' field for GitHub issues)
    if data and isinstance(data, list) and len(data) > 0:
        if "title" not in data[0]:
            print(f"   ⚠️  Invalid GitHub issue format (missing 'title' field) - skipping")
            return 0, 0
    elif not data:
        print(f"   ⚠️  No issue data found - skipping")
        return 0, 0

    print(f"   Found {len(data)} issue(s)")

    # Create ingester
    ingester = GitHubIngester(
        github_token="dummy",
        owner="dummy",
        repo="dummy",
        mcp_url=mcp_client.mcp_url,
        translate=False,
        save_to_disk=False,
    )

    # Ingest items
    success_count = 0
    error_count = 0

    try:
        from tqdm import tqdm

        for item in tqdm(data, desc="   Ingesting", unit="issue"):
            try:
                episode = ingester.build_episode(item)
                await mcp_client.add_episode(session, **episode)
                success_count += 1
            except Exception as e:
                error_count += 1
                print(f"   ✗ Error: {e}")
    except ImportError:
        # Fallback without tqdm
        for i, item in enumerate(data, 1):
            try:
                episode = ingester.build_episode(item)
                await mcp_client.add_episode(session, **episode)
                success_count += 1
                print(f"   Processing {i}/{len(data)}...", end="\r")
            except Exception as e:
                error_count += 1
                print(f"   ✗ Error: {e}")
        print()

    print(f"   ✓ Loaded {success_count} GitHub issue(s)")
    if error_count > 0:
        print(f"   ✗ {error_count} error(s)")

    return success_count, error_count


async def process_slack_file(
    file_path: Path, mcp_client: MCPClient, session
) -> tuple[int, int]:
    """Process a Slack messages JSON file."""
    print(f"📄 Loading: {file_path.name}")

    with open(file_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    # Extract data
    if "data" in json_data:
        data = json_data["data"]
        channel_id = json_data.get("channel_id", "demo-channel")
        workspace_id = json_data.get("workspace_id", "demo-workspace")
    elif "messages" in json_data:
        # Handle raw Slack export format
        raw_messages = json_data["messages"]
        channel_id = json_data.get("channel_id", "demo-channel")
        workspace_id = json_data.get("workspace_id", "demo-workspace")

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
        data = json_data if isinstance(json_data, list) else [json_data]
        channel_id = "demo-channel"
        workspace_id = "demo-workspace"

    print(f"   Found {len(data)} message(s)/thread(s)")

    # Create ingester
    ingester = SlackIngester(
        token="dummy",
        channel_id=channel_id,
        workspace_id=workspace_id,
        mcp_url=mcp_client.mcp_url,
        translate=False,
        save_to_disk=False,
    )

    # Ingest items
    success_count = 0
    error_count = 0

    try:
        from tqdm import tqdm

        for item in tqdm(data, desc="   Ingesting", unit="msg"):
            try:
                episode = ingester.build_episode(item)
                await mcp_client.add_episode(session, **episode)
                success_count += 1
            except Exception as e:
                error_count += 1
                print(f"   ✗ Error: {e}")
    except ImportError:
        # Fallback without tqdm
        for i, item in enumerate(data, 1):
            try:
                episode = ingester.build_episode(item)
                await mcp_client.add_episode(session, **episode)
                success_count += 1
                print(f"   Processing {i}/{len(data)}...", end="\r")
            except Exception as e:
                error_count += 1
                print(f"   ✗ Error: {e}")
        print()

    print(f"   ✓ Loaded {success_count} Slack message(s)")
    if error_count > 0:
        print(f"   ✗ {error_count} error(s)")

    return success_count, error_count


async def process_zoom_file(
    file_path: Path, mcp_client: MCPClient, session
) -> tuple[int, int]:
    """Process a Zoom transcript VTT file."""
    print(f"📄 Loading: {file_path.name}")

    # Read VTT file
    with open(file_path, "r", encoding="utf-8") as f:
        vtt_content = f.read()

    print(f"   Found transcript ({len(vtt_content)} characters)")

    # Parse VTT to extract conversation
    try:
        from datetime import datetime, timezone

        # Simple VTT parsing - extract speaker and text
        lines = vtt_content.split("\n")
        conversation_text = []

        for line in lines:
            line = line.strip()
            # Skip WEBVTT header, timestamps, and empty lines
            if line.startswith("WEBVTT") or "-->" in line or not line or line.isdigit():
                continue
            conversation_text.append(line)

        # Build episode content
        episode_content = "\n".join(conversation_text)

        # Create episode name
        episode_name = f"zoom:transcript:{file_path.stem}"

        # Reference time (use file modification time or current time)
        reference_time = datetime.now(timezone.utc)

        # Source description
        source_description = f"Zoom meeting transcript from {file_path.name}"

        # Source URL (use MinIO URL if available, otherwise local path)
        source_url = f"http://localhost:20734/zoom-transcripts/{file_path.name}"

        # Create episode
        episode = {
            "name": episode_name,
            "episode_body": episode_content,
            "reference_time": reference_time,
            "source_description": source_description,
            "source_url": source_url,
            "source": "zoom",
        }

        await mcp_client.add_episode(session, **episode)

        print(f"   ✓ Loaded Zoom transcript")
        return 1, 0
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 0, 1


def main():
    parser = argparse.ArgumentParser(
        description="Load demo data from data/ directory into Graphiti"
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Path to the data directory (default: data)",
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

    # Validate data directory exists
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"❌ Error: Data directory not found: {data_dir}")
        sys.exit(1)

    asyncio.run(
        load_demo_data(
            data_dir=data_dir,
            mcp_url=args.mcp_url,
            clear_existing=args.clear_existing,
        )
    )


if __name__ == "__main__":
    main()
