#!/usr/bin/env python3
import asyncio

from neo4j import AsyncGraphDatabase


async def analyze_relations():
    driver = AsyncGraphDatabase.driver(
        "bolt://localhost:7687", auth=("neo4j", "uniqorns")
    )
    async with driver.session() as session:
        print("=== Detailed Relationship Analysis ===\n")

        result = await session.run(
            "MATCH ()-[r:RELATES_TO]->() RETURN count(r) as count"
        )
        total = (await result.single())["count"]
        print(f"Total RELATES_TO relationships: {total}")

        print("\nRelationship type (r.name) distribution:")
        result = await session.run("""
            MATCH ()-[r:RELATES_TO]->()
            RETURN r.name as rel_type, count(*) as count
            ORDER BY count DESC
            LIMIT 20
        """)

        named_count = 0
        generic_count = 0
        async for record in result:
            rel_type = record["rel_type"]
            count = record["count"]
            if rel_type:
                print(f"  {rel_type}: {count} times")
                named_count += count
            else:
                print(f"  (NULL/unspecified): {count} times")
                generic_count += count

        if total > 0:
            print(
                f"\nWith specific names: {named_count}/{total} ({named_count / total * 100:.1f}%)"
            )
            print(
                f"Unclassified: {generic_count}/{total} ({generic_count / total * 100:.1f}%)"
            )

        print("\n\nSample edges (with specific names):")
        result = await session.run("""
            MATCH (s)-[r:RELATES_TO]->(t)
            WHERE r.name IS NOT NULL
            RETURN s.name as source, r.name as rel, t.name as target, r.fact as fact
            LIMIT 10
        """)
        count = 0
        async for record in result:
            source = record["source"]
            rel_name = record["rel"]
            target = record["target"]
            fact = record["fact"]
            print(f"\n  {source} --[{rel_name}]--> {target}")
            if fact:
                print(f"    Description: {fact[:100]}...")
            count += 1

        if count == 0:
            print("  (No edges with specific names found)")

    await driver.close()


asyncio.run(analyze_relations())
