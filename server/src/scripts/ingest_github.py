#!/usr/bin/env python3
"""
GitHub Issues ingestion CLI script.

This is a thin CLI wrapper around the GitHubIngester class.
"""

import argparse
import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ingestion.github import GitHubIngester


async def main():
    parser = argparse.ArgumentParser(
        description="Ingest GitHub issues into Graphiti MCP with English translation"
    )
    parser.add_argument(
        "--github-token",
        type=str,
        default=os.getenv("GITHUB_TOKEN"),
        help="GitHub personal access token (or set GITHUB_TOKEN env var)",
    )
    parser.add_argument(
        "--owner",
        type=str,
        default=os.getenv("GITHUB_OWNER", "hoge-org"),
        help="GitHub repository owner (default: hoge-org)",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=os.getenv("GITHUB_REPO", "hoge-repo"),
        help="GitHub repository name (default: hoge-repo)",
    )
    parser.add_argument(
        "--state",
        type=str,
        default="all",
        choices=["open", "closed", "all"],
        help="Issue state filter (default: all)",
    )
    parser.add_argument(
        "--max-issues",
        type=int,
        default=None,
        help="Maximum number of issues to ingest (default: all)",
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Clear existing graph data before ingestion",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save issues to data/github directory",
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

    if not args.github_token:
        print("Error: GitHub token not provided. Use --github-token or set GITHUB_TOKEN env var")
        return

    # Create ingester
    ingester = GitHubIngester(
        github_token=args.github_token,
        owner=args.owner,
        repo=args.repo,
        state=args.state,
        max_issues=args.max_issues,
        mcp_url=args.mcp_url,
        translate=not args.no_translate,
        save_to_disk=not args.no_save,
    )

    # Run ingestion
    await ingester.ingest(clear_existing=args.clear_existing)


if __name__ == "__main__":
    asyncio.run(main())
