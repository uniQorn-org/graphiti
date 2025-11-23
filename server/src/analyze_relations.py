#!/usr/bin/env python3
import asyncio

from neo4j import AsyncGraphDatabase


async def analyze_relations():
    driver = AsyncGraphDatabase.driver(
        "bolt://localhost:7687", auth=("neo4j", "uniqorns")
    )
    async with driver.session() as session:
        print("=== 関係性の詳細分析 ===\n")

        result = await session.run(
            "MATCH ()-[r:RELATES_TO]->() RETURN count(r) as count"
        )
        total = (await result.single())["count"]
        print(f"全RELATES_TO関係数: {total}")

        print("\n関係タイプ（r.name）の分布:")
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
                print(f"  {rel_type}: {count}回")
                named_count += count
            else:
                print(f"  （NULL/未指定）: {count}回")
                generic_count += count

        if total > 0:
            print(
                f"\n具体的な名前あり: {named_count}/{total} ({named_count / total * 100:.1f}%)"
            )
            print(
                f"未分類: {generic_count}/{total} ({generic_count / total * 100:.1f}%)"
            )

        print("\n\nサンプルエッジ（具体的な名前あり）:")
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
                print(f"    説明: {fact[:100]}...")
            count += 1

        if count == 0:
            print("  （具体的な名前を持つエッジが見つかりませんでした）")

    await driver.close()


asyncio.run(analyze_relations())
