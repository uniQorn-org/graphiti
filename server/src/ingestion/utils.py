"""Common utilities for ingestion."""


def build_slack_url(workspace_id: str, channel_id: str, message_ts: str, thread_ts: str | None = None) -> str:
    """
    Build Slack message URL.

    Args:
        workspace_id: Slack workspace ID
        channel_id: Channel ID
        message_ts: Message timestamp
        thread_ts: Thread timestamp (optional)

    Returns:
        Slack message URL
    """
    msg_id = message_ts.replace(".", "")
    base_url = f"https://app.slack.com/client/{workspace_id}/{channel_id}/p{msg_id}"

    if thread_ts and thread_ts != message_ts:
        return f"{base_url}?thread_ts={thread_ts}&cid={channel_id}"

    return base_url


def build_github_issue_url(owner: str, repo: str, issue_number: int) -> str:
    """
    Build GitHub issue URL.

    Args:
        owner: Repository owner
        repo: Repository name
        issue_number: Issue number

    Returns:
        GitHub issue URL
    """
    return f"https://github.com/{owner}/{repo}/issues/{issue_number}"


def build_minio_url(endpoint: str, bucket: str, object_key: str) -> str:
    """
    Build MinIO object URL.

    Args:
        endpoint: MinIO endpoint
        bucket: Bucket name
        object_key: Object key

    Returns:
        MinIO object URL
    """
    return f"http://{endpoint}/{bucket}/{object_key}"
