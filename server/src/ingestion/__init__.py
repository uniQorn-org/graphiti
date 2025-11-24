"""
Ingestion module for Graphiti MCP.

This module provides a unified framework for ingesting data from various sources
(GitHub, Slack, Zoom) into Graphiti knowledge graphs.
"""

from .base import BaseIngester
from .github import GitHubIngester
from .slack import SlackIngester
from .zoom import ZoomIngester

__all__ = [
    "BaseIngester",
    "GitHubIngester",
    "SlackIngester",
    "ZoomIngester",
]
