"""GitHub Issues ingestion."""

from typing import Any

from github import Github

from .base import BaseIngester
from .utils import build_github_issue_url
from shared.constants import MAX_CHARS_TITLE, MAX_CHARS_BODY, MAX_CHARS_COMMENT


class GitHubIngester(BaseIngester):
    """Ingester for GitHub Issues."""

    def __init__(
        self,
        github_token: str,
        owner: str,
        repo: str,
        state: str = "all",
        max_issues: int | None = None,
        **kwargs,
    ):
        """
        Initialize GitHub ingester.

        Args:
            github_token: GitHub personal access token
            owner: Repository owner
            repo: Repository name
            state: Issue state filter (open, closed, all)
            max_issues: Maximum number of issues to ingest (None for all)
            **kwargs: Additional arguments for BaseIngester
        """
        super().__init__(**kwargs)
        self.github_token = github_token
        self.owner = owner
        self.repo = repo
        self.state = state
        self.max_issues = max_issues

    def get_source_type(self) -> str:
        """Get source type identifier."""
        return "github"

    async def fetch_data(self) -> list[dict[str, Any]]:
        """
        Fetch GitHub issues.

        Returns:
            List of issue data dictionaries
        """
        # Initialize GitHub client
        g = Github(self.github_token)
        repository = g.get_repo(f"{self.owner}/{self.repo}")

        # Get issues
        issues = repository.get_issues(state=self.state)
        total_issues = issues.totalCount

        print(f"Found {total_issues} issues in {self.owner}/{self.repo} (state={self.state})")
        if self.max_issues:
            print(f"Limiting to {self.max_issues} issues")

        # Collect issue data
        issues_data = []
        count = 0

        for issue in issues:
            if self.max_issues and count >= self.max_issues:
                break

            # Skip pull requests
            if issue.pull_request:
                continue

            # Collect comments
            comments_data = []
            if issue.comments > 0:
                for comment in issue.get_comments():
                    comments_data.append(
                        {
                            "user": comment.user.login,
                            "created_at": comment.created_at.isoformat(),
                            "body": comment.body,
                        }
                    )

            # Build issue data
            issue_data = {
                "number": issue.number,
                "title": issue.title,
                "body": issue.body or "(No description)",
                "state": issue.state,
                "html_url": issue.html_url,
                "created_at": issue.created_at.isoformat(),
                "updated_at": issue.updated_at.isoformat(),
                "user": issue.user.login,
                "labels": [label.name for label in issue.labels],
                "comments": comments_data,
            }

            issues_data.append(issue_data)
            count += 1

        return issues_data

    def build_episode(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Convert issue data into episode format.

        Args:
            data: Issue data dictionary

        Returns:
            Episode dictionary
        """
        # Translate title and body
        title = self.translate_text(data["title"], max_chars=MAX_CHARS_TITLE)
        body = self.translate_text(data["body"], max_chars=MAX_CHARS_BODY)

        # Build episode body
        episode_body = f"# {title}\n\n{body}"

        # Add comments
        if data["comments"]:
            episode_body += "\n\n## Comments\n"
            for comment in data["comments"]:
                comment_body = self.translate_text(comment["body"], max_chars=MAX_CHARS_COMMENT)
                episode_body += (
                    f"\n**{comment['user']}** at {comment['created_at']}:\n{comment_body}\n"
                )

        # Create episode name
        episode_name = f"github:issue:{self.owner}/{self.repo}#{data['number']}"

        # Source URL
        source_url = data["html_url"]

        # Source description
        labels = ", ".join(data["labels"])
        source_description = (
            f"GitHub issue #{data['number']}, "
            f"state: {data['state']}, "
            f"author: {data['user']}, "
            f"created: {data['created_at']}"
        )
        if labels:
            source_description += f", labels: {labels}"

        return {
            "name": episode_name,
            "episode_body": episode_body,
            "source": "text",
            "source_description": source_description,
            "source_url": source_url,
        }
