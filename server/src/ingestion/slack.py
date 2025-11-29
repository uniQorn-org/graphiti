"""Slack messages ingestion.

reference_time definition:
- For thread episodes: Timestamp of the first message in the thread (thread_ts)
- For standalone messages: Timestamp of the message (ts)

This timestamp represents when the conversation/message actually occurred in Slack,
and will be used by graphiti-core as the valid_at for extracted entities and relations.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .base import BaseIngester
from .utils import build_slack_url


class SlackIngester(BaseIngester):
    """Ingester for Slack messages."""

    def __init__(
        self,
        token: str,
        channel_id: str,
        workspace_id: str,
        cookie: str | None = None,
        days: int = 1,
        **kwargs,
    ):
        """
        Initialize Slack ingester.

        Args:
            token: Slack user token
            channel_id: Slack channel ID
            workspace_id: Slack workspace ID
            cookie: Cookie string for authentication (optional)
            days: Number of days to fetch messages
            **kwargs: Additional arguments for BaseIngester
        """
        super().__init__(**kwargs)
        self.token = token
        self.channel_id = channel_id
        self.workspace_id = workspace_id
        self.cookie = cookie
        self.days = days
        self.user_cache: dict[str, str] = {}

    def get_source_type(self) -> str:
        """Get source type identifier."""
        return "slack"

    def _fetch_slack_messages(
        self, oldest: float | None = None, latest: float | None = None
    ) -> list[dict]:
        """
        Fetch Slack messages using conversations.history API.

        Args:
            oldest: Oldest timestamp to fetch
            latest: Latest timestamp to fetch

        Returns:
            List of message dictionaries
        """
        url = "https://slack.com/api/conversations.history"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie

        params = {
            "channel": self.channel_id,
            "limit": 100,
        }
        if oldest:
            params["oldest"] = str(oldest)
        if latest:
            params["latest"] = str(latest)

        all_messages = []
        cursor = None

        # Disable proxy for Slack API requests (bypass corporate proxy)
        proxies = {
            'http': None,
            'https': None,
        }

        while True:
            if cursor:
                params["cursor"] = cursor

            response = requests.get(url, headers=headers, params=params, proxies=proxies)
            data = response.json()

            if not data.get("ok"):
                error = data.get("error", "Unknown error")
                raise Exception(f"Slack API error: {error}")

            messages = data.get("messages", [])
            all_messages.extend(messages)

            cursor = data.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return all_messages

    def _get_user_info(self, user_id: str) -> str:
        """
        Get user display name from Slack API.

        Args:
            user_id: Slack user ID

        Returns:
            User display name
        """
        if user_id in self.user_cache:
            return self.user_cache[user_id]

        url = "https://slack.com/api/users.info"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie

        params = {"user": user_id}

        # Disable proxy for Slack API requests (bypass corporate proxy)
        proxies = {
            'http': None,
            'https': None,
        }

        try:
            response = requests.get(url, headers=headers, params=params, proxies=proxies)
            data = response.json()

            if data.get("ok"):
                user = data.get("user", {})
                display_name = (
                    user.get("profile", {}).get("display_name")
                    or user.get("real_name")
                    or user.get("name")
                    or user_id
                )
                self.user_cache[user_id] = display_name
                return display_name
        except Exception as e:
            print(f"Warning: Could not fetch user info for {user_id}: {e}")

        self.user_cache[user_id] = user_id
        return user_id

    async def fetch_data(self) -> list[dict[str, Any]]:
        """
        Fetch Slack messages.

        Returns:
            List of message groups (threads and standalone messages)
        """
        now = datetime.now()
        oldest_dt = now - timedelta(days=self.days)
        oldest = oldest_dt.timestamp()

        print(f"Fetching messages from last {self.days} day(s)...")
        print(f"  From: {oldest_dt.isoformat()}")
        print(f"  To: {now.isoformat()}")

        # Fetch messages
        messages = self._fetch_slack_messages(oldest=oldest)

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

        # Prepare data for ingestion
        data = []

        # Add threads
        for thread_ts, thread_msgs in threads.items():
            thread_msgs.sort(key=lambda m: float(m.get("ts", 0)))
            data.append({"type": "thread", "thread_ts": thread_ts, "messages": thread_msgs})

        # Add standalone messages
        for msg in standalone:
            data.append({"type": "standalone", "message": msg})

        return data

    def build_episode(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Convert message data into episode format.

        Args:
            data: Message data dictionary

        Returns:
            Episode dictionary
        """
        if data["type"] == "thread":
            return self._build_thread_episode(data)
        else:
            return self._build_standalone_episode(data)

    def _build_thread_episode(self, data: dict[str, Any]) -> dict[str, Any]:
        """Build episode for a thread."""
        thread_ts = data["thread_ts"]
        thread_msgs = data["messages"]

        # Build conversation (without user IDs in text)
        conversation_lines = []
        user_metadata = []  # Collect unique users

        for msg in thread_msgs:
            user_id = msg.get("user", "Unknown")
            user_name = self._get_user_info(user_id)
            text = msg.get("text", "")

            # Translate message
            if text:
                text = self.translate_text(text, max_chars=1000)

            conversation_lines.append(f"{user_name}: {text}")

            # Collect unique user metadata
            if user_id not in [u["id"] for u in user_metadata]:
                user_metadata.append({
                    "id": user_id,
                    "name": user_name,
                })

        conversation = "\n".join(conversation_lines)

        # Get parent message and timestamp
        parent_msg = thread_msgs[0]
        parent_ts = parent_msg["ts"]
        first_ts = float(parent_ts)
        first_datetime = datetime.fromtimestamp(first_ts, tz=timezone.utc)

        # Build structured metadata for participants
        participants_str = ", ".join([f"{u['name']} ({u['id']})" for u in user_metadata])

        # Build episode metadata
        episode_name = f"slack:thread:{self.channel_id}:{thread_ts}"
        source_url = build_slack_url(self.workspace_id, self.channel_id, parent_ts, thread_ts)
        source_description = (
            f"Slack thread, channel: {self.channel_id}, "
            f"thread_ts: {thread_ts}, "
            f"timestamp: {first_datetime.isoformat()}, "
            f"participants: {participants_str}, "
            f"messages: {len(thread_msgs)}"
        )

        return {
            "name": episode_name,
            "episode_body": conversation,
            "source": "message",
            "source_description": source_description,
            "source_url": source_url,
            "reference_time": first_datetime,  # Timestamp of first message
        }

    def _build_standalone_episode(self, data: dict[str, Any]) -> dict[str, Any]:
        """Build episode for a standalone message."""
        msg = data["message"]

        user_id = msg.get("user", "Unknown")
        user_name = self._get_user_info(user_id)
        text = msg.get("text", "")
        ts = msg["ts"]

        # Translate message
        if text:
            text = self.translate_text(text, max_chars=1000)

        episode_body = f"{user_name}: {text}"
        episode_name = f"slack:message:{self.channel_id}:{ts}"
        source_url = build_slack_url(self.workspace_id, self.channel_id, ts)

        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        source_description = (
            f"Slack message, channel: {self.channel_id}, "
            f"timestamp: {dt.isoformat()}, "
            f"user: {user_name} ({user_id})"  # Include user ID in metadata
        )

        return {
            "name": episode_name,
            "episode_body": episode_body,
            "source": "message",
            "source_description": source_description,
            "source_url": source_url,
            "reference_time": dt,  # Timestamp of the message
        }
