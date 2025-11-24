#!/usr/bin/env python3
"""Simple test to check basic search functionality."""

import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def test_simple_search():
    """Test basic search_memory_facts."""
    async with streamablehttp_client("http://localhost:8001/mcp/") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("Testing search_memory_facts...")
            result = await session.call_tool(
                "search_memory_facts",
                arguments={"query": "API", "max_facts": 3},
            )

            # Extract content from CallToolResult
            if hasattr(result, 'content'):
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        data = json.loads(content_item.text)
                        print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print(result)


if __name__ == "__main__":
    asyncio.run(test_simple_search())
