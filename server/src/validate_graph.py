#!/usr/bin/env python3
"""
グラフ品質検証スクリプト

Graphitiで生成されたナレッジグラフの品質を評価し、
チャンク化戦略が適切かどうかを判定します。
"""

import argparse
import asyncio
import json
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def get_graph_statistics(session: ClientSession) -> dict[str, Any]:
    stats = {}

    episodes_result = await session.call_tool(
        "get_episodes", arguments={"max_episodes": 1000, "group_ids": ["main"]}
    )
    episodes_data = episodes_result.structuredContent or json.loads(
        episodes_result.content[0].text
    )
    episodes = (
        episodes_data.get("result", {}).get("episodes", [])
        if isinstance(episodes_data, dict) and "result" in episodes_data
        else episodes_data.get("episodes", [])
    )
    stats["episode_count"] = len(episodes)

    if episodes:
        episode_lengths = [len(ep["content"]) for ep in episodes]
        stats["avg_episode_length"] = sum(episode_lengths) / len(episode_lengths)
        stats["min_episode_length"] = min(episode_lengths)
        stats["max_episode_length"] = max(episode_lengths)

    nodes_result = await session.call_tool(
        "search_nodes",
        arguments={
            "query": "GraphRAG OR Slack OR tonoyama OR entity",
            "max_nodes": 1000,
            "group_ids": ["main"],
        },
    )
    nodes_data = (
        nodes_result.structuredContent["result"]
        if nodes_result.structuredContent
        else json.loads(nodes_result.content[0].text)
    )
    nodes = nodes_data.get("nodes", [])
    stats["node_count"] = len(nodes)

    if nodes:
        node_labels = {}
        for node in nodes:
            for label in node.get("labels", []):
                node_labels[label] = node_labels.get(label, 0) + 1
        stats["node_labels"] = node_labels

        summary_lengths = [
            len(node.get("summary", "")) for node in nodes if node.get("summary")
        ]
        if summary_lengths:
            stats["avg_node_summary_length"] = sum(summary_lengths) / len(
                summary_lengths
            )

    facts_result = await session.call_tool(
        "search_memory_facts",
        arguments={
            "query": "GraphRAG OR Slack OR entity",
            "max_facts": 1000,
            "group_ids": ["main"],
        },
    )
    facts_data = (
        facts_result.structuredContent["result"]
        if facts_result.structuredContent
        else json.loads(facts_result.content[0].text)
    )
    facts = facts_data.get("facts", [])
    stats["fact_count"] = len(facts)

    if facts:
        fact_types = {}
        for fact in facts:
            fact_name = fact.get("name", "UNKNOWN")
            fact_types[fact_name] = fact_types.get(fact_name, 0) + 1
        stats["fact_types"] = fact_types

    return stats


def calculate_quality_score(stats: dict[str, Any]) -> dict[str, Any]:
    score = 0
    max_score = 0
    details = []

    episode_count = stats.get("episode_count", 0)
    node_count = stats.get("node_count", 0)
    fact_count = stats.get("fact_count", 0)

    if episode_count > 0:
        max_score += 10
        if node_count > 0:
            ratio = node_count / episode_count
            if 0.3 <= ratio <= 3.0:
                score += 10
                details.append(f"✅ ノード/エピソード比: {ratio:.2f} (適切: 0.3-3.0)")
            else:
                score += 5
                details.append(f"⚠️  ノード/エピソード比: {ratio:.2f} (推奨: 0.3-3.0)")
        else:
            details.append("❌ ノードが生成されていません")

    max_score += 10
    if fact_count > 0:
        if node_count > 0:
            ratio = fact_count / node_count
            if ratio >= 1.0:
                score += 10
                details.append(f"✅ ファクト/ノード比: {ratio:.2f} (良好: >= 1.0)")
            elif ratio >= 0.5:
                score += 7
                details.append(f"⚠️  ファクト/ノード比: {ratio:.2f} (改善可能: 0.5-1.0)")
            else:
                score += 3
                details.append(f"❌ ファクト/ノード比: {ratio:.2f} (低すぎる: < 0.5)")
        else:
            details.append("❌ ファクトが生成されていません")
    else:
        details.append("❌ ファクト（関係性）が存在しません")

    max_score += 10
    avg_episode_length = stats.get("avg_episode_length", 0)
    if avg_episode_length > 0:
        if 200 <= avg_episode_length <= 2000:
            score += 10
            details.append(
                f"✅ 平均エピソード長: {avg_episode_length:.0f}文字 (適切: 200-2000)"
            )
        elif 100 <= avg_episode_length < 200:
            score += 7
            details.append(
                f"⚠️  平均エピソード長: {avg_episode_length:.0f}文字 (短い: 100-200)"
            )
        elif avg_episode_length < 100:
            score += 3
            details.append(
                f"❌ 平均エピソード長: {avg_episode_length:.0f}文字 (短すぎる: < 100)"
            )
        else:
            score += 7
            details.append(
                f"⚠️  平均エピソード長: {avg_episode_length:.0f}文字 (長い: > 2000)"
            )

    max_score += 10
    node_labels = stats.get("node_labels", {})
    if len(node_labels) > 0:
        entity_count = node_labels.get("Entity", 0)
        total_nodes = sum(node_labels.values())
        if entity_count > 0:
            entity_ratio = entity_count / total_nodes
            if entity_ratio > 0.8:
                score += 10
                details.append(f"✅ エンティティノード比率: {entity_ratio:.1%} (良好)")
            else:
                score += 7
                details.append(f"⚠️  エンティティノード比率: {entity_ratio:.1%}")
        details.append(f"   ノードラベル分布: {node_labels}")

    max_score += 10
    fact_types = stats.get("fact_types", {})
    unique_fact_types = len(fact_types)
    if unique_fact_types >= 3:
        score += 10
        details.append(f"✅ ファクトタイプ数: {unique_fact_types} (多様性あり)")
    elif unique_fact_types >= 1:
        score += 5
        details.append(f"⚠️  ファクトタイプ数: {unique_fact_types} (多様性が低い)")
    else:
        details.append("❌ ファクトタイプが存在しません")

    if fact_types:
        top_fact_types = sorted(fact_types.items(), key=lambda x: x[1], reverse=True)[
            :5
        ]
        details.append(
            f"   主なファクトタイプ: {', '.join([f'{k}({v})' for k, v in top_fact_types])}"
        )

    return {
        "score": score,
        "max_score": max_score,
        "percentage": (score / max_score * 100) if max_score > 0 else 0,
        "details": details,
    }


async def validate_graph(verbose: bool = False) -> None:
    async with streamablehttp_client("http://localhost:8001/mcp/") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            print("=" * 70)
            print("Graphiti ナレッジグラフ品質検証")
            print("=" * 70)

            stats = await get_graph_statistics(session)

            print("\n📊 基本統計:")
            print(f"  エピソード数: {stats.get('episode_count', 0)}")
            print(f"  ノード数: {stats.get('node_count', 0)}")
            print(f"  ファクト数: {stats.get('fact_count', 0)}")

            if verbose:
                print("\n📏 詳細統計:")
                if "avg_episode_length" in stats:
                    print(f"  平均エピソード長: {stats['avg_episode_length']:.0f}文字")
                    print(
                        f"  最小エピソード長: {stats.get('min_episode_length', 0)}文字"
                    )
                    print(
                        f"  最大エピソード長: {stats.get('max_episode_length', 0)}文字"
                    )
                if "avg_node_summary_length" in stats:
                    print(
                        f"  平均ノード要約長: {stats['avg_node_summary_length']:.0f}文字"
                    )

            quality = calculate_quality_score(stats)

            print("\n🎯 品質スコア:")
            print(
                f"  {quality['score']}/{quality['max_score']} ({quality['percentage']:.1f}%)"
            )

            print("\n📋 評価詳細:")
            for detail in quality["details"]:
                print(f"  {detail}")

            print("\n💡 総合評価:")
            percentage = quality["percentage"]
            if percentage >= 80:
                print("  ✅ 優秀 - グラフは高品質です")
            elif percentage >= 60:
                print("  ⚠️  良好 - いくつか改善の余地があります")
            elif percentage >= 40:
                print("  ⚠️  要改善 - チャンク化戦略の見直しを推奨します")
            else:
                print("  ❌ 不良 - データ投入またはチャンク化に問題があります")

            print("\n📝 改善提案:")
            if stats.get("episode_count", 0) == 0:
                print(
                    "  - データが投入されていません。load_slack_data.pyを実行してください"
                )
            elif stats.get("node_count", 0) == 0:
                print("  - ノードが生成されていません。LLM設定を確認してください")
            elif stats.get("fact_count", 0) == 0:
                print(
                    "  - 関係性が抽出されていません。エピソード内容をより会話的にしてください"
                )
            else:
                avg_length = stats.get("avg_episode_length", 0)
                if avg_length < 100:
                    print(
                        "  - エピソードが短すぎます。時間窓を長く（例: 4H, 1D）してください"
                    )
                elif avg_length > 2000:
                    print(
                        "  - エピソードが長すぎます。時間窓を短く（例: 30min, 1H）してください"
                    )

                node_ratio = stats.get("node_count", 0) / stats.get("episode_count", 1)
                if node_ratio < 0.3:
                    print(
                        "  - ノード数が少なすぎます。より具体的な内容のエピソードを作成してください"
                    )
                elif node_ratio > 3.0:
                    print(
                        "  - ノード数が多すぎます。エピソードをより凝集させてください"
                    )

                fact_ratio = stats.get("fact_count", 0) / max(
                    stats.get("node_count", 1), 1
                )
                if fact_ratio < 0.5:
                    print(
                        "  - 関係性が少なすぎます。スレッド単位でのチャンク化を推奨します"
                    )

            print("\n" + "=" * 70)


async def main():
    parser = argparse.ArgumentParser(
        description="Graphitiナレッジグラフの品質を検証します。"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="詳細な統計情報を表示します。"
    )
    args = parser.parse_args()

    await validate_graph(verbose=args.verbose)


if __name__ == "__main__":
    asyncio.run(main())
