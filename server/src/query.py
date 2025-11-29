#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client  # HTTP connection


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="Search query string.",
    )
    args = parser.parse_args()
    async with streamablehttp_client("http://localhost:8001/mcp/") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            arguments = {"query": args.query, "max_facts": 5}
            facts = await session.call_tool("search_memory_facts", arguments=arguments)
            print(
                json.dumps(
                    facts.structuredContent or facts.content[0].to_json(),
                    ensure_ascii=False,
                    indent=2,
                )
            )


if __name__ == "__main__":
    asyncio.run(main())
