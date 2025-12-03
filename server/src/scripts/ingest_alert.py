#!/usr/bin/env python3
"""
Ingest alert episodes from episodes_json directory into Graphiti.
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.mcp_client import MCPClient


async def ingest_alert_episodes(
    episodes_dir: Path,
    mcp_url: str = "http://localhost:8001/mcp/",
    limit: int | None = None
):
    """
    Ingest alert episodes from JSON files into Graphiti.

    Args:
        episodes_dir: Directory containing episode JSON files
        mcp_url: MCP server URL
        limit: Maximum number of episodes to ingest (None = all)
    """
    # Find all episode JSON files
    episode_files = sorted(episodes_dir.glob("*.episode.json"))

    if not episode_files:
        print(f"[ERROR] No episode files found in {episodes_dir}")
        return

    if limit:
        episode_files = episode_files[:limit]

    print(f"[INFO] Found {len(episode_files)} episode files to ingest")
    print(f"[INFO] MCP URL: {mcp_url}")

    # Initialize MCP client
    mcp_client = MCPClient(mcp_url)

    success_count = 0
    error_count = 0

    async with mcp_client.connect() as session:
        for i, episode_file in enumerate(episode_files, 1):
            try:
                # Load episode JSON
                with open(episode_file, 'r', encoding='utf-8') as f:
                    episode_data = json.load(f)

                # Extract fields
                name = episode_data.get("episode_name", episode_file.stem)
                content = episode_data.get("content", "")
                description = episode_data.get("description", "")
                episode_type = episode_data.get("type", "text")

                # Get reference_time if available
                reference_time = episode_data.get("reference_time")
                if reference_time:
                    try:
                        reference_time = datetime.fromisoformat(reference_time.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        reference_time = None

                # Get metadata
                metadata = episode_data.get("metadata", {})
                issue_url = metadata.get("issue_url", "")

                print(f"[INFO] ({i}/{len(episode_files)}) Ingesting {episode_file.name}")

                # Add episode to Graphiti
                result = await mcp_client.add_episode(
                    session=session,
                    name=name,
                    episode_body=content,
                    source=episode_type,
                    source_description=description,
                    source_url=issue_url,
                    reference_time=reference_time
                )

                print(f"[OK] Successfully ingested {name}")
                success_count += 1

            except Exception as e:
                print(f"[ERROR] Failed to ingest {episode_file.name}: {e}")
                error_count += 1
                continue

    print("\n" + "="*60)
    print(f"[SUMMARY] Ingestion complete")
    print(f"  Success: {success_count}")
    print(f"  Errors:  {error_count}")
    print(f"  Total:   {len(episode_files)}")
    print("="*60)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest alert episodes from JSON files into Graphiti"
    )
    parser.add_argument(
        "--episodes-dir",
        type=Path,
        default=Path("data/alert"),
        help="Directory containing episode JSON files (default: data/alert)"
    )
    parser.add_argument(
        "--mcp-url",
        type=str,
        default="http://localhost:30547/mcp/",
        help="MCP server URL (default: http://localhost:30547/mcp/)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of episodes to ingest (default: all)"
    )

    args = parser.parse_args()

    # Check if directory exists
    if not args.episodes_dir.exists():
        print(f"[ERROR] Directory not found: {args.episodes_dir}")
        sys.exit(1)

    await ingest_alert_episodes(
        episodes_dir=args.episodes_dir,
        mcp_url=args.mcp_url,
        limit=args.limit
    )


if __name__ == "__main__":
    asyncio.run(main())
