#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import json
from typing import Any, Dict

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client  # HTTP connection


async def call_tool(
    session: ClientSession, name: str, arguments: Dict[str, Any]
) -> Any:
    return await session.call_tool(name, arguments=arguments)


async def demo_run(session: ClientSession) -> None:
    tools = await session.list_tools()
    print("== Tools ==")
    print(
        json.dumps(
            [{"name": t.name, "description": t.description} for t in tools.tools],
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\n== get_status ==")
    status = await call_tool(session, "get_status", {})
    print(
        json.dumps(
            status.structuredContent or status.content[0].to_json(),
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\n== get_episodes ==")
    eps = await call_tool(session, "get_episodes", {"max_episodes": 10})
    print(
        json.dumps(
            eps.structuredContent or eps.content[0].to_json(),
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\n== search_nodes ==")
    nodes = await call_tool(
        session, "search_nodes", {"query": "test OR hello", "max_nodes": 5}
    )
    print(
        json.dumps(
            nodes.structuredContent or nodes.content[0].to_json(),
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\n== search_memory_facts ==")
    facts = await call_tool(
        session,
        "search_memory_facts",
        {"query": "relationships about test", "max_facts": 5},
    )
    print(
        json.dumps(
            facts.structuredContent or facts.content[0].to_json(),
            ensure_ascii=False,
            indent=2,
        )
    )


async def main():
    async with streamablehttp_client("http://localhost:8001/mcp/") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await demo_run(session)


if __name__ == "__main__":
    asyncio.run(main())
