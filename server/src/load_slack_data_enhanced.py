#!/usr/bin/env python3
"""
Graphiti準拠Slackデータ投入スクリプト

Graphiti EpisodeType.message要件に準拠:
1. "ユーザー名: メッセージ" 形式（発話者エンティティ抽出用）
2. スレッド構造の保持（10,000文字制限対応で自動分割）
3. 独立メッセージの個別エピソード化（誤グループ化防止）
4. メタデータをsource_descriptionに配置
"""

import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from tqdm import tqdm


def build_slack_url(workspace_id: str, channel_id: str, ts: str, thread_ts: str | None = None) -> str:
    """Build Slack message URL.

    Args:
        workspace_id: Workspace ID (e.g., T09HNJQG1JA)
        channel_id: Channel ID (e.g., C09JQQMUHCZ)
        ts: Message timestamp
        thread_ts: Thread timestamp (if in thread)

    Returns:
        Slack message URL
    """
    # Convert timestamp to message ID format (remove decimal point)
    msg_id = ts.replace(".", "")
    base_url = f"https://app.slack.com/client/{workspace_id}/{channel_id}/p{msg_id}"

    if thread_ts and thread_ts != ts:
        # Thread reply URL
        return f"{base_url}?thread_ts={thread_ts}&cid={channel_id}"

    return base_url


def chunk_slack_data_enhanced(threads_df: pd.DataFrame) -> list[dict]:
    chunks = []

    has_thread = threads_df["thread_ts"].notna() & (
        threads_df["thread_ts"].astype(str) != "nan"
    )

    threaded_messages = threads_df[has_thread].copy()

    if not threaded_messages.empty:
        for thread_ts, group in threaded_messages.groupby("thread_ts"):
            sorted_msgs = group.sort_values("ts")

            parent_msg = sorted_msgs.iloc[0]
            replies = sorted_msgs.iloc[1:] if len(sorted_msgs) > 1 else pd.DataFrame()

            # Graphiti要件準拠: "ユーザー名: メッセージ" 形式
            conversation_lines = []

            # 親メッセージ
            conversation_lines.append(
                f"{parent_msg['user_display']}: {parent_msg['content']}"
            )

            # 返信メッセージ
            for _, reply in replies.iterrows():
                conversation_lines.append(
                    f"{reply['user_display']}: {reply['content']}"
                )

            # 10,000文字制限対応: スレッドを複数パートに分割
            MAX_CHARS_PER_EPISODE = 9500  # 安全マージン込み
            parts = []
            current_part = []
            current_length = 0

            for line in conversation_lines:
                line_length = len(line) + 1  # +1 for newline

                if current_length + line_length > MAX_CHARS_PER_EPISODE:
                    # 現在のパートを保存して新パート開始
                    if current_part:
                        parts.append("\n".join(current_part))
                    current_part = [line]
                    current_length = line_length
                else:
                    current_part.append(line)
                    current_length += line_length

            # 最後のパートを追加
            if current_part:
                parts.append("\n".join(current_part))

            # 長いスレッドの警告
            if len(parts) > 1:
                print(
                    f"⚠️  Thread {thread_ts}: {len(conversation_lines)} messages, split into {len(parts)} parts"
                )

            first_time = pd.to_datetime(parent_msg["ts"], unit="s", utc=True)
            last_time = (
                pd.to_datetime(sorted_msgs.iloc[-1]["ts"], unit="s", utc=True)
                if len(sorted_msgs) > 1
                else first_time
            )

            # パートごとにchunksに追加
            for i, part_body in enumerate(parts, 1):
                part_suffix = f":part{i}" if len(parts) > 1 else ""

                chunks.append(
                    {
                        "name": f"slack:thread:{thread_ts}{part_suffix}",  # フルIDを使用
                        "body": part_body,
                        "timestamp_str": str(parent_msg["ts"]),
                        "type": "thread",
                        "thread_ts": str(thread_ts),
                        "part_info": f"{i}/{len(parts)}" if len(parts) > 1 else "1/1",
                        "message_count": len(sorted_msgs),
                        "participants": sorted_msgs["user_display"].unique().tolist(),
                        "start_time": first_time.isoformat(),
                        "end_time": last_time.isoformat(),
                        "date": first_time.strftime("%Y-%m-%d"),
                    }
                )

    # 非スレッドメッセージは個別エピソード化
    non_thread_mask = threads_df["thread_ts"].isna() | (
        threads_df["thread_ts"].astype(str) == "nan"
    )
    non_threaded = threads_df[non_thread_mask].copy()

    if not non_threaded.empty:
        print(f"  📝 非スレッドメッセージ: {len(non_threaded)}件（個別エピソード化）")

        for _, row in non_threaded.iterrows():
            # Graphiti要件準拠フォーマット
            episode_body = f"{row['user_display']}: {row['content']}"

            # タイムスタンプ解析
            try:
                timestamp_float = float(row["ts"])
                message_time = datetime.fromtimestamp(timestamp_float, tz=timezone.utc)
            except (ValueError, TypeError):
                print(f"⚠️  タイムスタンプ解析エラー: {row['ts']}")
                continue

            # メタデータ
            metadata_str = (
                f"standalone_message, "
                f"date: {message_time.strftime('%Y-%m-%d')}, "
                f"time: {message_time.strftime('%H:%M')}, "
                f"user: {row['user_display']}"
            )

            # フルmessage_idを使用（ID衝突回避）
            chunk = {
                "name": f"slack:message:{str(row['message_id'])}",
                "body": episode_body,
                "timestamp_str": str(row["ts"]),
                "type": "standalone_message",
                "metadata": metadata_str,
            }

            chunks.append(chunk)

    return chunks


async def add_slack_data_enhanced(
    session: ClientSession,
    chunked: bool = True,
    workspace_id: str = "T09HNJQG1JA",
    channel_id: str = "C09JQQMUHCZ",
) -> None:
    script_dir = Path(__file__).parent.parent

    # Use English CSV by default if available, fallback to original
    threads_en_path = script_dir / "slack_data" / "threads_ordered_en.csv"
    threads_path = (
        threads_en_path
        if threads_en_path.exists()
        else script_dir / "slack_data" / "threads_ordered.csv"
    )

    slack_data_paths = {
        "threads": threads_path,
        "users": script_dir / "slack_data" / "users_used.csv",
    }

    threads_df = pd.read_csv(slack_data_paths["threads"])
    users_df = pd.read_csv(slack_data_paths["users"])

    print(f"  💬 メッセージ数: {len(threads_df)}")
    print(f"  👥 ユーザー数: {len(users_df)}")

    if chunked:
        print(f"  📦 Graphiti準拠フォーマット: 有効")
        chunks = chunk_slack_data_enhanced(threads_df)
        print(f"  📊 生成されたエピソード数: {len(chunks)}")

        thread_chunks = [c for c in chunks if c["type"] == "thread"]
        standalone_chunks = [c for c in chunks if c["type"] == "standalone_message"]
        print(f"    - スレッドエピソード: {len(thread_chunks)}")
        print(f"    - 独立メッセージエピソード: {len(standalone_chunks)}")

        for chunk in tqdm(chunks, desc="チャンクを投入中"):
            timestamp_str = chunk["timestamp_str"]

            try:
                timestamp_float = float(timestamp_str)
                message_time = datetime.fromtimestamp(timestamp_float, tz=timezone.utc)
            except (ValueError, TypeError):
                print(f"⚠️  タイムスタンプ解析エラー: {timestamp_str}")
                continue

            # スレッドと非スレッドで分岐
            if chunk["type"] == "thread":
                # スレッドの場合
                metadata_parts = [
                    "slack_thread",
                    f"thread_id: {chunk['thread_ts']}",
                    f"part: {chunk['part_info']}",
                    f"date: {chunk['date']}",
                    f"start_time: {chunk['start_time']}",
                    f"end_time: {chunk['end_time']}",
                    f"participants: {', '.join(chunk['participants'])}",
                    f"message_count: {chunk['message_count']}",
                ]
                metadata_str = ", ".join(metadata_parts)

            elif chunk["type"] == "standalone_message":
                # 非スレッドメッセージの場合
                metadata_str = chunk["metadata"]

            else:
                # 旧形式が残っている場合（移行期間用）
                metadata_str = f"type: {chunk['type']}"

            # Build source URL
            if chunk["type"] == "thread":
                source_url = build_slack_url(workspace_id, channel_id, chunk["timestamp_str"], chunk["thread_ts"])
            else:
                source_url = build_slack_url(workspace_id, channel_id, chunk["timestamp_str"])

            arguments = {
                "name": chunk["name"],
                "episode_body": chunk["body"],
                "source": "message",  # EpisodeType.message に対応（会話フォーマット）
                "source_description": metadata_str,
                "source_url": source_url,
                # group_id指定なし
            }

            await session.call_tool("add_memory", arguments=arguments)


async def main():
    parser = argparse.ArgumentParser(
        description="SlackデータをGraphiti準拠フォーマットで投入します。"
    )
    parser.add_argument(
        "--clear_existing",
        action="store_true",
        help="既存のデータをクリアしてからSlackデータを追加します。",
    )
    args = parser.parse_args()

    async with streamablehttp_client("http://localhost:8001/mcp/") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            if args.clear_existing:
                print("既存のデータをクリアしています...")
                await session.call_tool("clear_graph", arguments={})
            await add_slack_data_enhanced(session, chunked=True)


if __name__ == "__main__":
    asyncio.run(main())
