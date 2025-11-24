#!/usr/bin/env python3
"""Test script to verify source URLs in search_with_citations."""

import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def test_search_with_citations():
    """Test search_with_citations and display source URLs."""
    async with streamablehttp_client("http://localhost:8001/mcp/") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Search for Zoom-related content
            print("=" * 80)
            print("Searching for Zoom meeting content...")
            print("=" * 80)

            result = await session.call_tool(
                "search_with_citations",
                arguments={"query": "meeting API", "max_facts": 5},
            )

            # Extract content from CallToolResult
            data = None
            if hasattr(result, 'content'):
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        data = json.loads(content_item.text)
                        break

            if data and "facts" in data:
                print(f"\nFound {len(data['facts'])} facts:\n")

                for i, fact in enumerate(data["facts"], 1):
                    print(f"Fact #{i}:")
                    print(f"  Content: {fact.get('fact', 'N/A')[:100]}...")
                    print(f"  From: {fact.get('from_node', 'N/A')}")
                    print(f"  To: {fact.get('to_node', 'N/A')}")

                    citations = fact.get("citations", [])
                    if citations:
                        print(f"  Citations ({len(citations)}):")
                        for citation in citations:
                            print(f"    - Episode: {citation.get('episode_name', 'N/A')}")
                            print(f"      Source: {citation.get('source', 'N/A')}")
                            print(f"      URL: {citation.get('source_url', 'NO URL')}")
                            print(f"      Description: {citation.get('source_description', 'N/A')[:80]}...")
                    else:
                        print("  No citations found")
                    print()

            # Search for GitHub issue content
            print("=" * 80)
            print("Searching for GitHub issue content...")
            print("=" * 80)

            result = await session.call_tool(
                "search_with_citations",
                arguments={"query": "API フロントエンド", "max_facts": 3},
            )

            # Extract content from CallToolResult
            data = None
            if hasattr(result, 'content'):
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        data = json.loads(content_item.text)
                        break

            if data and "facts" in data:
                print(f"\nFound {len(data['facts'])} facts:\n")

                for i, fact in enumerate(data["facts"], 1):
                    print(f"Fact #{i}:")
                    print(f"  Content: {fact.get('fact', 'N/A')[:100]}...")

                    citations = fact.get("citations", [])
                    if citations:
                        print(f"  Citations ({len(citations)}):")
                        for citation in citations:
                            print(f"    - Episode: {citation.get('episode_name', 'N/A')}")
                            print(f"      URL: {citation.get('source_url', 'NO URL')}")
                    print()


if __name__ == "__main__":
    asyncio.run(test_search_with_citations())
