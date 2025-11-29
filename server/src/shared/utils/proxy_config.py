"""Proxy configuration utilities for OpenAI API access.

This module provides utilities for configuring HTTP proxies for OpenAI API calls,
which is useful when running behind corporate firewalls or for testing purposes.

Consolidated from server/src/utils/proxy_utils.py and backend/src/utils/proxy_utils.py
to eliminate code duplication.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)


def _mask_proxy_credentials(proxy_url: str) -> str:
    """Mask credentials in proxy URL for safe logging.

    Args:
        proxy_url: Proxy URL potentially containing credentials

    Returns:
        Proxy URL with credentials removed (everything after @ symbol)

    Example:
        >>> _mask_proxy_credentials("http://user:pass@proxy.com:8080")
        "proxy.com:8080"
    """
    return proxy_url.split('@')[-1] if '@' in proxy_url else proxy_url


def get_proxy_config() -> dict[str, str] | None:
    """Get proxy configuration from environment variables.

    Reads proxy settings from the following environment variables:
    - PROXY_USE: Enable/disable proxy (TRUE/FALSE). If FALSE or not set, proxy is disabled.
    - OPENAI_PROXY: Proxy URL (e.g., http://proxy.company.com:8080)
    - OPENAI_PROXY_USERNAME: Optional username for proxy authentication
    - OPENAI_PROXY_PASSWORD: Optional password for proxy authentication
    - NO_PROXY: Comma-separated list of hosts to bypass proxy

    Returns:
        Dictionary with proxy configuration for http:// and https://, or None if no proxy is configured.
        Format: {"http://": "proxy_url", "https://": "proxy_url"}
    """
    # Check if proxy is enabled
    proxy_use = os.getenv("PROXY_USE", "FALSE").upper()
    if proxy_use != "TRUE":
        return None

    proxy_url = os.getenv("OPENAI_PROXY")

    if not proxy_url:
        logger.warning("PROXY_USE is TRUE but OPENAI_PROXY is not set")
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

    logger.info(f"Configuring OpenAI API proxy: {_mask_proxy_credentials(proxy_url)}")

    # Return proxy configuration for both HTTP and HTTPS
    return {
        "http://": proxy_url,
        "https://": proxy_url,
    }


def get_no_proxy_hosts() -> str | None:
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
        # Use the proxy URL (httpx 0.27.0+ uses 'proxy' parameter, not 'proxies')
        proxy_url = proxy_config.get("https://", proxy_config.get("http://"))
        client_kwargs["proxy"] = proxy_url
        logger.debug(f"Creating httpx client with proxy: {_mask_proxy_credentials(proxy_url)}")
    else:
        logger.debug("Creating httpx client without proxy")

    return httpx.Client(**client_kwargs)


def create_async_httpx_client(timeout: float = 60.0) -> httpx.AsyncClient:
    """Create an async httpx.AsyncClient with proxy configuration from environment variables.

    This client can be passed to OpenAI SDK's http_client parameter for async operations.

    Args:
        timeout: Request timeout in seconds (default: 60.0)

    Returns:
        httpx.AsyncClient configured with proxy settings

    Example:
        >>> http_client = create_async_httpx_client()
        >>> from openai import AsyncOpenAI
        >>> client = AsyncOpenAI(api_key="...", http_client=http_client)
    """
    proxy_config = get_proxy_config()

    # Build httpx client configuration
    client_kwargs = {
        "timeout": timeout,
    }

    if proxy_config:
        # Use the proxy URL (httpx 0.27.0+ uses 'proxy' parameter, not 'proxies')
        proxy_url = proxy_config.get("https://", proxy_config.get("http://"))
        client_kwargs["proxy"] = proxy_url
        logger.debug(f"Creating async httpx client with proxy: {_mask_proxy_credentials(proxy_url)}")
    else:
        logger.debug("Creating async httpx client without proxy")

    return httpx.AsyncClient(**client_kwargs)


def setup_proxy_environment() -> bool:
    """Setup HTTP_PROXY and HTTPS_PROXY environment variables for SDK usage.

    Many SDKs (OpenAI, LangChain) automatically use HTTP_PROXY/HTTPS_PROXY environment variables.
    This function sets them based on the PROXY_USE and OPENAI_PROXY settings.

    Returns:
        True if proxy was configured, False otherwise
    """
    proxy_config = get_proxy_config()
    if not proxy_config:
        return False

    proxy_url = proxy_config.get("https://", proxy_config.get("http://"))
    os.environ["HTTP_PROXY"] = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url

    logger.info(f"✓ Proxy configured for SDKs: {_mask_proxy_credentials(proxy_url)}")

    return True


def log_proxy_status():
    """Log the current proxy configuration status for debugging purposes."""
    proxy_use = os.getenv("PROXY_USE", "FALSE").upper()
    proxy_url = os.getenv("OPENAI_PROXY")
    no_proxy = get_no_proxy_hosts()

    if proxy_use != "TRUE":
        logger.info("✓ Proxy disabled (PROXY_USE=FALSE or not set)")
        if proxy_url:
            logger.info(f"  ℹ️  OPENAI_PROXY is set to: {_mask_proxy_credentials(proxy_url)} but not used")
        return

    if proxy_url:
        logger.info(f"✓ OpenAI API proxy enabled (PROXY_USE=TRUE)")
        logger.info(f"✓ Proxy URL: {_mask_proxy_credentials(proxy_url)}")

        if os.getenv("OPENAI_PROXY_USERNAME"):
            logger.info("✓ Proxy authentication enabled")

        if no_proxy:
            logger.info(f"✓ NO_PROXY hosts: {no_proxy}")
    else:
        logger.warning("⚠️  PROXY_USE=TRUE but OPENAI_PROXY is not set!")
