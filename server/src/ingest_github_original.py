#!/usr/bin/env python3
"""
GitHub Issues ingestion script for Graphiti MCP.

Fetches issues from a GitHub repository and adds them to Graphiti
with source URLs pointing to the issue pages.
"""

import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

from github import Github
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from tqdm import tqdm


async def ingest_github_issues(
    session: ClientSession,
    github_token: str,
    owner: str,
    repo: str,
    state: str = "all",
    max_issues: int | None = None,
    save_to_disk: bool = True,
) -> None:
    """Ingest GitHub issues into Graphiti.

    Args:
        session: MCP client session
        github_token: GitHub personal access token
        owner: Repository owner
        repo: Repository name
        state: Issue state filter (open, closed, all)
        max_issues: Maximum number of issues to ingest (None for all)
        save_to_disk: Whether to save issues to data/github directory
    """
    # Initialize GitHub client
    g = Github(github_token)
    repository = g.get_repo(f"{owner}/{repo}")

    # Get issues
    issues = repository.get_issues(state=state)
    total_issues = issues.totalCount

    print(f"Found {total_issues} issues in {owner}/{repo} (state={state})")

    if max_issues:
        print(f"Limiting to {max_issues} issues")

    # Prepare data directory if saving
    if save_to_disk:
        data_dir = Path("/app/data/github")
        data_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"issues_{owner}_{repo}_{timestamp}.json"
        filepath = data_dir / filename
        
        issues_data = {
            "owner": owner,
            "repo": repo,
            "state": state,
            "fetched_at": datetime.now().isoformat(),
            "total_issues": total_issues,
            "max_issues": max_issues,
            "issues": []
        }

    count = 0
    for issue in tqdm(issues, desc="Ingesting GitHub issues", total=min(max_issues or total_issues, total_issues)):
        if max_issues and count >= max_issues:
            break

        try:
            # Skip pull requests (they appear in issues list)
            if issue.pull_request:
                continue

            # Build episode body
            episode_body = f"# {issue.title}\n\n{issue.body or '(No description)'}"

            # Collect comments
            comments_data = []
            if issue.comments > 0:
                episode_body += "\n\n## Comments\n"
                for comment in issue.get_comments():
                    episode_body += f"\n**{comment.user.login}** at {comment.created_at}:\n{comment.body}\n"
                    comments_data.append({
                        "user": comment.user.login,
                        "created_at": comment.created_at.isoformat(),
                        "body": comment.body
                    })

            # Create episode name
            episode_name = f"github:issue:{owner}/{repo}#{issue.number}"

            # Source URL
            source_url = issue.html_url

            # Source description
            labels = ", ".join([label.name for label in issue.labels])
            source_description = (
                f"GitHub issue #{issue.number}, "
                f"state: {issue.state}, "
                f"author: {issue.user.login}, "
                f"created: {issue.created_at.isoformat()}"
            )
            if labels:
                source_description += f", labels: {labels}"

            # Save issue data if requested
            if save_to_disk:
                issue_data = {
                    "number": issue.number,
                    "title": issue.title,
                    "body": issue.body,
                    "state": issue.state,
                    "html_url": issue.html_url,
                    "created_at": issue.created_at.isoformat(),
                    "updated_at": issue.updated_at.isoformat(),
                    "user": issue.user.login,
                    "labels": [label.name for label in issue.labels],
                    "comments_count": issue.comments,
                    "comments": comments_data
                }
                issues_data["issues"].append(issue_data)

            # Add to Graphiti
            arguments = {
                "name": episode_name,
                "episode_body": episode_body,
                "source": "text",
                "source_description": source_description,
                "source_url": source_url,
            }

            await session.call_tool("add_memory", arguments=arguments)
            print(f"✓ Ingested issue #{issue.number}: {issue.title[:50]}...")

            count += 1

        except Exception as e:
            print(f"✗ Error processing issue #{issue.number}: {e}")

    # Save collected data to disk
    if save_to_disk:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(issues_data, f, ensure_ascii=False, indent=2)
        print(f"Saved {count} issues to: {filepath}")


async def main():
    parser = argparse.ArgumentParser(
        description="Ingest GitHub issues into Graphiti MCP"
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
        default=os.getenv("GITHUB_OWNER", "uniQorn-org"),
        help="GitHub repository owner (default: uniQorn-org)",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=os.getenv("GITHUB_REPO", "uniqorn-zoom"),
        help="GitHub repository name (default: uniqorn-zoom)",
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
    args = parser.parse_args()

    if not args.github_token:
        print("Error: GitHub token not provided. Use --github-token or set GITHUB_TOKEN env var")
        return

    async with streamablehttp_client("http://localhost:8001/mcp/") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            if args.clear_existing:
                print("Clearing existing graph data...")
                await session.call_tool("clear_graph", arguments={})

            await ingest_github_issues(
                session,
                args.github_token,
                args.owner,
                args.repo,
                args.state,
                args.max_issues,
                save_to_disk=not args.no_save,
            )


if __name__ == "__main__":
    asyncio.run(main())
