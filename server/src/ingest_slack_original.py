#!/usr/bin/env python3
"""
Slack messages ingestion script for Graphiti MCP with cookie support.

Fetches Slack messages using the Slack Web API and adds them to Graphiti
with source URLs pointing to the message permalinks.
"""

import argparse
import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from tqdm import tqdm


def fetch_slack_messages(
    token: str,
    channel_id: str,
    workspace_id: str,
    cookie: str | None = None,
    oldest: float | None = None,
    latest: float | None = None,
) -> list[dict]:
    """Fetch Slack messages using conversations.history API.

    Args:
        token: Slack user token (xoxc-...)
        channel_id: Slack channel ID
        workspace_id: Slack workspace ID
        cookie: Cookie string for authentication
        oldest: Only messages after this Unix timestamp
        latest: Only messages before this Unix timestamp

    Returns:
        List of message dicts
    """
    url = "https://slack.com/api/conversations.history"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if cookie:
        headers["Cookie"] = cookie
    
    params = {
        "channel": channel_id,
        "limit": 100,
    }
    if oldest:
        params["oldest"] = str(oldest)
    if latest:
        params["latest"] = str(latest)

    all_messages = []
    cursor = None

    while True:
        if cursor:
            params["cursor"] = cursor

        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        if not data.get("ok"):
            error = data.get("error", "Unknown error")
            raise Exception(f"Slack API error: {error}")

        messages = data.get("messages", [])
        all_messages.extend(messages)

        # Check for pagination
        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    return all_messages


def get_user_info(token: str, user_id: str, user_cache: dict, cookie: str | None = None) -> str:
    """Get user display name from Slack API.

    Args:
        token: Slack user token
        user_id: Slack user ID
        user_cache: Cache dict for user info
        cookie: Cookie string for authentication

    Returns:
        User display name
    """
    if user_id in user_cache:
        return user_cache[user_id]

    url = "https://slack.com/api/users.info"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if cookie:
        headers["Cookie"] = cookie
    
    params = {"user": user_id}

    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        if data.get("ok"):
            user = data.get("user", {})
            display_name = (
                user.get("profile", {}).get("display_name")
                or user.get("real_name")
                or user.get("name")
                or user_id
            )
            user_cache[user_id] = display_name
            return display_name
    except Exception as e:
        print(f"Warning: Could not fetch user info for {user_id}: {e}")

    user_cache[user_id] = user_id
    return user_id


def build_message_url(workspace_id: str, channel_id: str, message_ts: str, thread_ts: str | None = None) -> str:
    """Build Slack message URL.

    Args:
        workspace_id: Slack workspace ID
        channel_id: Channel ID
        message_ts: Message timestamp
        thread_ts: Thread timestamp (if in thread)

    Returns:
        Slack message URL
    """
    # Convert timestamp to message ID format (remove decimal point)
    msg_id = message_ts.replace(".", "")

    base_url = f"https://app.slack.com/client/{workspace_id}/{channel_id}/p{msg_id}"

    if thread_ts and thread_ts != message_ts:
        # Thread reply URL
        thread_id = thread_ts.replace(".", "")
        return f"{base_url}?thread_ts={thread_ts}&cid={channel_id}"

    return base_url


async def ingest_slack_messages(
    session: ClientSession,
    token: str,
    channel_id: str,
    workspace_id: str,
    cookie: str | None = None,
    days: int = 1,
    save_to_disk: bool = True,
) -> None:
    """Ingest Slack messages into Graphiti.

    Args:
        session: MCP client session
        token: Slack user token
        channel_id: Channel ID to fetch from
        workspace_id: Workspace ID
        cookie: Cookie string for authentication
        days: Number of days to fetch (from now)
        save_to_disk: Whether to save messages to data/slack directory
    """
    # Calculate time range
    now = datetime.now()
    oldest_dt = now - timedelta(days=days)
    oldest = oldest_dt.timestamp()

    print(f"Fetching messages from last {days} day(s)...")
    print(f"  From: {oldest_dt.isoformat()}")
    print(f"  To: {now.isoformat()}")

    # Fetch messages
    messages = fetch_slack_messages(token, channel_id, workspace_id, cookie, oldest=oldest)
    print(f"Found {len(messages)} messages")

    # Save raw messages to disk if requested
    if save_to_disk:
        data_dir = Path("/app/data/slack")
        data_dir.mkdir(parents=True, exist_ok=True)

        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"messages_{channel_id}_{timestamp}.json"
        filepath = data_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "workspace_id": workspace_id,
                "channel_id": channel_id,
                "fetched_at": now.isoformat(),
                "oldest": oldest_dt.isoformat(),
                "latest": now.isoformat(),
                "message_count": len(messages),
                "messages": messages,
            }, f, ensure_ascii=False, indent=2)

        print(f"Saved raw messages to: {filepath}")

    # User info cache
    user_cache = {}

    # Group messages by thread
    threads = {}
    standalone = []

    for msg in messages:
        if msg.get("thread_ts"):
            thread_ts = msg["thread_ts"]
            if thread_ts not in threads:
                threads[thread_ts] = []
            threads[thread_ts].append(msg)
        else:
            standalone.append(msg)

    print(f"  Threads: {len(threads)}")
    print(f"  Standalone messages: {len(standalone)}")

    # Ingest threads
    for thread_ts, thread_msgs in tqdm(threads.items(), desc="Ingesting threads"):
        try:
            # Sort by timestamp
            thread_msgs.sort(key=lambda m: float(m.get("ts", 0)))

            # Build conversation
            conversation_lines = []
            for msg in thread_msgs:
                user_id = msg.get("user", "Unknown")
                user_name = get_user_info(token, user_id, user_cache, cookie)
                text = msg.get("text", "")
                conversation_lines.append(f"{user_name}: {text}")

            conversation = "\n".join(conversation_lines)

            # First message in thread
            parent_msg = thread_msgs[0]
            parent_ts = parent_msg["ts"]

            # Episode name
            episode_name = f"slack:thread:{channel_id}:{thread_ts}"

            # Source URL (parent message)
            source_url = build_message_url(workspace_id, channel_id, parent_ts, thread_ts)

            # Source description
            source_description = (
                f"Slack thread, channel: {channel_id}, "
                f"thread_ts: {thread_ts}, "
                f"messages: {len(thread_msgs)}"
            )

            # Add to Graphiti
            arguments = {
                "name": episode_name,
                "episode_body": conversation,
                "source": "message",
                "source_description": source_description,
                "source_url": source_url,
            }

            await session.call_tool("add_memory", arguments=arguments)

        except Exception as e:
            print(f"✗ Error processing thread {thread_ts}: {e}")

    # Ingest standalone messages
    for msg in tqdm(standalone, desc="Ingesting standalone messages"):
        try:
            user_id = msg.get("user", "Unknown")
            user_name = get_user_info(token, user_id, user_cache, cookie)
            text = msg.get("text", "")
            ts = msg["ts"]

            # Episode body (Graphiti message format)
            episode_body = f"{user_name}: {text}"

            # Episode name
            episode_name = f"slack:message:{channel_id}:{ts}"

            # Source URL
            source_url = build_message_url(workspace_id, channel_id, ts)

            # Source description
            dt = datetime.fromtimestamp(float(ts))
            source_description = (
                f"Slack message, channel: {channel_id}, "
                f"timestamp: {dt.isoformat()}, "
                f"user: {user_name}"
            )

            # Add to Graphiti
            arguments = {
                "name": episode_name,
                "episode_body": episode_body,
                "source": "message",
                "source_description": source_description,
                "source_url": source_url,
            }

            await session.call_tool("add_memory", arguments=arguments)

        except Exception as e:
            print(f"✗ Error processing message {msg.get('ts')}: {e}")


async def main():
    parser = argparse.ArgumentParser(
        description="Ingest Slack messages into Graphiti MCP"
    )
    parser.add_argument(
        "--token",
        type=str,
        required=True,
        help="Slack user token (xoxc-...)",
    )
    parser.add_argument(
        "--workspace-id",
        type=str,
        required=True,
        help="Slack workspace ID (e.g., T09HNJQG1JA)",
    )
    parser.add_argument(
        "--channel-id",
        type=str,
        required=True,
        help="Slack channel ID (e.g., C09JQQMUHCZ)",
    )
    parser.add_argument(
        "--cookie",
        type=str,
        default=None,
        help="Cookie string for authentication",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days to fetch (default: 1)",
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Clear existing graph data before ingestion",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save messages to data/slack directory",
    )
    args = parser.parse_args()

    async with streamablehttp_client("http://localhost:8001/mcp/") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            if args.clear_existing:
                print("Clearing existing graph data...")
                await session.call_tool("clear_graph", arguments={})

            await ingest_slack_messages(
                session,
                args.token,
                args.channel_id,
                args.workspace_id,
                args.cookie,
                args.days,
                save_to_disk=not args.no_save,
            )


if __name__ == "__main__":
    asyncio.run(main())
