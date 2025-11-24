"""Proxy configuration utilities for OpenAI API access.

This module provides utilities for configuring HTTP proxies for OpenAI API calls,
which is useful when running behind corporate firewalls or for testing purposes.
"""

import logging
import os
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)


def get_proxy_config() -> Optional[Dict[str, str]]:
    """Get proxy configuration from environment variables.

    Reads proxy settings from the following environment variables:
    - OPENAI_PROXY: Proxy URL (e.g., http://proxy.company.com:8080)
    - OPENAI_PROXY_USERNAME: Optional username for proxy authentication
    - OPENAI_PROXY_PASSWORD: Optional password for proxy authentication
    - NO_PROXY: Comma-separated list of hosts to bypass proxy

    Returns:
        Dictionary with proxy configuration for http:// and https://, or None if no proxy is configured.
        Format: {"http://": "proxy_url", "https://": "proxy_url"}
    """
    proxy_url = os.getenv("OPENAI_PROXY")

    if not proxy_url:
        return None

    # Handle proxy authentication if provided
    username = os.getenv("OPENAI_PROXY_USERNAME")
    password = os.getenv("OPENAI_PROXY_PASSWORD")

    if username and password:
        # Insert authentication into proxy URL
        # Convert http://proxy.com:8080 to http://user:pass@proxy.com:8080
        if "://" in proxy_url:
            protocol, rest = proxy_url.split("://", 1)
            proxy_url = f"{protocol}://{username}:{password}@{rest}"
        else:
            logger.warning(
                "OPENAI_PROXY_USERNAME and OPENAI_PROXY_PASSWORD are set but proxy URL format is invalid"
            )

    logger.info(f"Configuring OpenAI API proxy: {proxy_url.split('@')[-1]}")  # Log without credentials

    # Return proxy configuration for both HTTP and HTTPS
    return {
        "http://": proxy_url,
        "https://": proxy_url,
    }


def get_no_proxy_hosts() -> Optional[str]:
    """Get NO_PROXY environment variable value.

    Returns:
        Comma-separated string of hosts to bypass proxy, or None if not set.
        Example: "localhost,127.0.0.1,neo4j,minio"
    """
    return os.getenv("NO_PROXY")


def create_httpx_client(timeout: float = 60.0) -> httpx.Client:
    """Create an httpx.Client with proxy configuration from environment variables.

    This client can be passed to OpenAI SDK's http_client parameter.

    Args:
        timeout: Request timeout in seconds (default: 60.0)

    Returns:
        httpx.Client configured with proxy settings

    Example:
        >>> http_client = create_httpx_client()
        >>> from openai import OpenAI
        >>> client = OpenAI(api_key="...", http_client=http_client)
    """
    proxy_config = get_proxy_config()

    # Build httpx client configuration
    client_kwargs = {
        "timeout": timeout,
    }

    if proxy_config:
        client_kwargs["proxies"] = proxy_config
        logger.debug(f"Creating httpx client with proxy: {list(proxy_config.values())[0].split('@')[-1]}")
    else:
        logger.debug("Creating httpx client without proxy")

    return httpx.Client(**client_kwargs)


def log_proxy_status():
    """Log the current proxy configuration status for debugging purposes."""
    proxy_url = os.getenv("OPENAI_PROXY")
    no_proxy = get_no_proxy_hosts()

    if proxy_url:
        # Mask credentials in log
        safe_url = proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url
        logger.info(f"✓ OpenAI API proxy configured: {safe_url}")

        if os.getenv("OPENAI_PROXY_USERNAME"):
            logger.info("✓ Proxy authentication enabled")

        if no_proxy:
            logger.info(f"✓ NO_PROXY hosts: {no_proxy}")
    else:
        logger.info("✓ No proxy configured (direct connection)")
