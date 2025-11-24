#!/usr/bin/env python3
"""
Slack messages ingestion CLI script.

This is a thin CLI wrapper around the SlackIngester class.
"""

import argparse
import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ingestion.slack import SlackIngester


async def main():
    parser = argparse.ArgumentParser(
        description="Ingest Slack messages into Graphiti MCP with English translation"
    )
    parser.add_argument("--token", type=str, required=True, help="Slack user token")
    parser.add_argument("--workspace-id", type=str, required=True, help="Slack workspace ID")
    parser.add_argument("--channel-id", type=str, required=True, help="Slack channel ID")
    parser.add_argument(
        "--cookie", type=str, default=None, help="Cookie string for authentication"
    )
    parser.add_argument("--days", type=int, default=1, help="Number of days to fetch")
    parser.add_argument(
        "--clear-existing", action="store_true", help="Clear existing graph data"
    )
    parser.add_argument("--no-save", action="store_true", help="Do not save messages to disk")
    parser.add_argument(
        "--no-translate", action="store_true", help="Do not translate to English"
    )
    parser.add_argument(
        "--mcp-url",
        type=str,
        default="http://localhost:8001/mcp/",
        help="MCP server URL (default: http://localhost:8001/mcp/)",
    )
    args = parser.parse_args()

    # Create ingester
    ingester = SlackIngester(
        token=args.token,
        channel_id=args.channel_id,
        workspace_id=args.workspace_id,
        cookie=args.cookie,
        days=args.days,
        mcp_url=args.mcp_url,
        translate=not args.no_translate,
        save_to_disk=not args.no_save,
    )

    # Run ingestion
    await ingester.ingest(clear_existing=args.clear_existing)


if __name__ == "__main__":
    asyncio.run(main())
