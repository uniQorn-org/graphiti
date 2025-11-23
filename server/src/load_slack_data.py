import argparse
import asyncio
from datetime import datetime, timezone

import pandas as pd
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client  # HTTP 接続用
from tqdm import tqdm


def chunk_slack_data(threads_df: pd.DataFrame, time_window: str = "1h") -> list[dict]:
    chunks = []

    # パターン1: スレッド単位でグループ化
    # reply_count > 0 のメッセージ（スレッドの親）とその返信をグループ化
    # thread_ts列を使ってスレッドを識別する
    has_thread = threads_df["thread_ts"].notna() & (
        threads_df["thread_ts"].astype(str) != "nan"
    )

    # スレッドに属するメッセージ（親 or 子）
    threaded_messages = threads_df[has_thread].copy()

    if not threaded_messages.empty:
        # thread_tsでグループ化（親メッセージとその返信が同じthread_tsを持つ）
        for thread_ts, group in threaded_messages.groupby("thread_ts"):
            sorted_msgs = group.sort_values("ts")

            conversation_lines = []
            for _, row in sorted_msgs.iterrows():
                user = str(row["user_display"])
                content = str(row["content"])
                conversation_lines.append(f"{user}: {content}")

            conversation = "\n".join(conversation_lines)

            first_msg = sorted_msgs.iloc[0]
            chunks.append(
                {
                    "name": f"Thread_{str(thread_ts)[:8]}",
                    "body": conversation,
                    "timestamp_str": str(first_msg["ts"]),
                    "type": "thread",
                    "thread_ts": str(thread_ts),
                    "message_count": len(sorted_msgs),
                }
            )

    # パターン2: スレッドのないメッセージ（is_parent=True かつ reply_count=0）を時間窓でグループ化
    # thread_tsがないメッセージのみを対象とする
    non_thread_mask = threads_df["thread_ts"].isna() | (
        threads_df["thread_ts"].astype(str) == "nan"
    )
    non_threaded = threads_df[non_thread_mask].copy()

    if not non_threaded.empty:
        non_threaded["ts_datetime"] = pd.to_datetime(
            non_threaded["ts"], errors="coerce", utc=True
        )
        non_threaded = non_threaded.dropna(subset=["ts_datetime"])

        non_threaded["time_window"] = non_threaded["ts_datetime"].dt.floor(time_window)

        for window, group in non_threaded.groupby("time_window"):
            sorted_msgs = group.sort_values("ts")

            conversation_lines = []
            for _, row in sorted_msgs.iterrows():
                user = str(row["user_display"])
                content = str(row["content"])
                conversation_lines.append(f"{user}: {content}")

            conversation = "\n".join(conversation_lines)

            first_msg = sorted_msgs.iloc[0]
            window_str = window.strftime("%Y%m%d_%H%M")
            chunks.append(
                {
                    "name": f"Chat_{window_str}",
                    "body": conversation,
                    "timestamp_str": str(first_msg["ts"]),
                    "type": "time_window",
                    "window": window_str,
                    "message_count": len(sorted_msgs),
                }
            )

    return chunks


async def add_slack_data(
    session: ClientSession, time_window: str = "1h", chunked: bool = True
) -> None:
    import os
    from pathlib import Path

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
        print(f"  📦 チャンク化モード: 有効（時間窓={time_window}）")
        chunks = chunk_slack_data(threads_df, time_window)
        print(f"  📊 生成されたチャンク数: {len(chunks)}")

        thread_chunks = [c for c in chunks if c["type"] == "thread"]
        time_chunks = [c for c in chunks if c["type"] == "time_window"]
        print(f"    - スレッドチャンク: {len(thread_chunks)}")
        print(f"    - 時間窓チャンク: {len(time_chunks)}")

        for chunk in tqdm(chunks, desc="チャンクを投入中"):
            timestamp_str = chunk["timestamp_str"]

            try:
                message_time = datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                )
            except ValueError:
                try:
                    timestamp_float = float(timestamp_str)
                    message_time = datetime.fromtimestamp(
                        timestamp_float, tz=timezone.utc
                    )
                except (ValueError, TypeError):
                    print(f"⚠️  タイムスタンプ解析エラー: {timestamp_str}")
                    continue

            metadata_str = f"timestamp: {message_time.isoformat()}, chunk_type: {chunk['type']}, message_count: {chunk['message_count']}"
            if chunk["type"] == "thread":
                metadata_str += f", thread_ts: {chunk['thread_ts']}"
            else:
                metadata_str += f", time_window: {chunk['window']}"

            arguments = {
                "name": chunk["name"],
                "episode_body": chunk["body"],
                "source": "message",
                "source_description": metadata_str,
            }

            await session.call_tool("add_memory", arguments=arguments)
    else:
        print("  📦 チャンク化モード: 無効（メッセージ単位で投入）")
        for _, row in tqdm(threads_df.iterrows(), total=len(threads_df)):
            message_id = str(row["message_id"])
            user_display = str(row["user_display"])
            content = str(row["content"])
            timestamp_str = str(row["ts"])

            try:
                thread_ts = (
                    str(row["thread_ts"]) if str(row["thread_ts"]) != "nan" else None
                )
            except Exception:
                thread_ts = None

            try:
                is_parent = bool(row["is_parent"])
            except Exception:
                is_parent = False

            try:
                message_time = datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                )
            except ValueError:
                try:
                    timestamp_float = float(timestamp_str)
                    message_time = datetime.fromtimestamp(
                        timestamp_float, tz=timezone.utc
                    )
                except (ValueError, TypeError):
                    print(
                        f"⚠️  タイムスタンプ解析エラー ({message_id}): {timestamp_str}"
                    )
                    continue

            episode_name = f"Slack_{message_id[:8]}"
            if is_parent:
                episode_name += "_thread"

            episode_content = f"{user_display}: {content}"

            if not is_parent and thread_ts:
                episode_content += f"\n[返信: スレッド {thread_ts}]"

            metadata_str = f"timestamp: {message_time.isoformat()}, message_id: {message_id}, user: {user_display}, thread_ts: {thread_ts}, is_parent: {is_parent}"

            arguments = {
                "name": episode_name,
                "episode_body": episode_content,
                "source": "message",
                "source_description": metadata_str,
            }
            await session.call_tool("add_memory", arguments=arguments)


async def main():
    parser = argparse.ArgumentParser(
        description="SlackデータをGraphitiに投入します。チャンク化により関連メッセージをグループ化できます。"
    )
    parser.add_argument(
        "--clear_existing",
        action="store_true",
        help="既存のデータをクリアしてからSlackデータを追加します。",
    )
    parser.add_argument(
        "--no-chunk",
        action="store_true",
        help="チャンク化を無効にし、メッセージ単位で投入します。",
    )
    parser.add_argument(
        "--time-window",
        type=str,
        default="1h",
        help="スレッドのないメッセージをグループ化する時間窓（例: 1h, 2h, 1d）。デフォルトは1h（1時間）。",
    )
    args = parser.parse_args()

    async with streamablehttp_client("http://localhost:8001/mcp/") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            if args.clear_existing:
                print("既存のデータをクリアしています...")
                await session.call_tool("clear_graph", arguments={})
            await add_slack_data(
                session, time_window=args.time_window, chunked=not args.no_chunk
            )


if __name__ == "__main__":
    asyncio.run(main())
