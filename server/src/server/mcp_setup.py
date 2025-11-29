"""MCP server initialization and configuration."""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from config.schema import GraphitiConfig, ServerConfig
from graphiti_core.utils.maintenance.graph_data_operations import clear_data
from middleware.cors import CORSHeaderMiddleware
from services.graphiti_service_mcp import GraphitiService
from services.queue_service import QueueService
from services.service_container import ServiceContainer

# Semaphore limit for concurrent Graphiti operations
SEMAPHORE_LIMIT = int(os.getenv("SEMAPHORE_LIMIT", 10))

# Logging configuration
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logger = logging.getLogger(__name__)


def configure_uvicorn_logging():
    """Configure uvicorn loggers to match our format after they're created."""
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uvicorn_logger = logging.getLogger(logger_name)
        # Remove existing handlers and add our own with proper formatting
        uvicorn_logger.handlers.clear()
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        uvicorn_logger.addHandler(handler)
        uvicorn_logger.propagate = False


async def initialize_server(mcp_instance) -> ServerConfig:
    """Parse CLI arguments and initialize the Graphiti server configuration.

    Args:
        mcp_instance: The FastMCP instance to configure

    Returns:
        ServerConfig with transport and connection settings
    """
    parser = argparse.ArgumentParser(
        description="Run the Graphiti MCP server with YAML configuration support"
    )

    # Configuration file argument
    # Default to config/config.yaml relative to the mcp_server directory
    default_config = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config,
        help="Path to YAML configuration file (default: config/config.yaml)",
    )

    # Transport arguments
    parser.add_argument(
        "--transport",
        choices=["sse", "stdio", "http"],
        help="Transport to use: http (recommended, default), stdio (standard I/O), or sse (deprecated)",
    )
    parser.add_argument(
        "--host",
        help="Host to bind the MCP server to",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Port to bind the MCP server to",
    )

    # Provider selection arguments
    parser.add_argument(
        "--llm-provider",
        choices=["openai", "azure_openai", "anthropic", "gemini", "groq"],
        help="LLM provider to use",
    )
    parser.add_argument(
        "--embedder-provider",
        choices=["openai", "azure_openai", "gemini", "voyage"],
        help="Embedder provider to use",
    )
    parser.add_argument(
        "--database-provider",
        choices=["neo4j", "falkordb"],
        help="Database provider to use",
    )

    # LLM configuration arguments
    parser.add_argument("--model", help="Model name to use with the LLM client")
    parser.add_argument(
        "--small-model", help="Small model name to use with the LLM client"
    )
    parser.add_argument(
        "--temperature", type=float, help="Temperature setting for the LLM (0.0-2.0)"
    )

    # Embedder configuration arguments
    parser.add_argument("--embedder-model", help="Model name to use with the embedder")

    # Graphiti-specific arguments
    parser.add_argument(
        "--group-id",
        help="Namespace for the graph. If not provided, uses config file or generates random UUID.",
    )
    parser.add_argument(
        "--user-id",
        help="User ID for tracking operations",
    )
    parser.add_argument(
        "--destroy-graph",
        action="store_true",
        help="Destroy all Graphiti graphs on startup",
    )

    args = parser.parse_args()

    # Set config path in environment for the settings to pick up
    if args.config:
        os.environ["CONFIG_PATH"] = str(args.config)

    # Load configuration with environment variables and YAML
    config = GraphitiConfig()

    # Apply CLI overrides
    config.apply_cli_overrides(args)

    # Also apply legacy CLI args for backward compatibility
    if hasattr(args, "destroy_graph"):
        config.destroy_graph = args.destroy_graph

    # Log configuration details
    logger.info("Using configuration:")
    logger.info(f"  - LLM: {config.llm.provider} / {config.llm.model}")
    logger.info(f"  - Embedder: {config.embedder.provider} / {config.embedder.model}")
    logger.info(f"  - Database: {config.database.provider}")
    logger.info(f"  - Group ID: {config.graphiti.group_id}")
    logger.info(f"  - Transport: {config.server.transport}")

    # Log graphiti-core version
    try:
        import graphiti_core

        graphiti_version = getattr(graphiti_core, "__version__", "unknown")
        logger.info(f"  - Graphiti Core: {graphiti_version}")
    except Exception:
        # Check for Docker-stored version file
        version_file = Path("/app/.graphiti-core-version")
        if version_file.exists():
            graphiti_version = version_file.read_text().strip()
            logger.info(f"  - Graphiti Core: {graphiti_version}")
        else:
            logger.info("  - Graphiti Core: version unavailable")

    # Handle graph destruction if requested
    if hasattr(config, "destroy_graph") and config.destroy_graph:
        logger.warning("Destroying all Graphiti graphs as requested...")
        temp_service = GraphitiService(config, SEMAPHORE_LIMIT)
        await temp_service.initialize()
        client = await temp_service.get_client()
        await clear_data(client.driver)
        logger.info("All graphs destroyed")

    # Initialize services
    graphiti_service = GraphitiService(config, SEMAPHORE_LIMIT)
    queue_service = QueueService()
    await graphiti_service.initialize()

    # Get graphiti client for queue initialization
    graphiti_client = await graphiti_service.get_client()

    # Initialize queue service with the client
    await queue_service.initialize(graphiti_client)

    # Store services in ServiceContainer
    ServiceContainer.set_config(config)
    ServiceContainer.set_graphiti_service(graphiti_service)
    ServiceContainer.set_queue_service(queue_service)

    # Set MCP server settings
    if config.server.host:
        mcp_instance.settings.host = config.server.host
    if config.server.port:
        mcp_instance.settings.port = args.port or config.server.port

    # Return MCP configuration for transport
    return config.server


async def run_mcp_server(mcp_instance):
    """Run the MCP server in the current event loop.

    Args:
        mcp_instance: The FastMCP instance to run
    """
    # Initialize the server
    mcp_config = await initialize_server(mcp_instance)

    # Run the server with configured transport
    logger.info(f"Starting MCP server with transport: {mcp_config.transport}")
    if mcp_config.transport == "stdio":
        await mcp_instance.run_stdio_async()
    elif mcp_config.transport == "sse":
        logger.info(
            f"Running MCP server with SSE transport on {mcp_instance.settings.host}:{mcp_instance.settings.port}"
        )
        logger.info(
            f"Access the server at: http://{mcp_instance.settings.host}:{mcp_instance.settings.port}/sse"
        )
        await mcp_instance.run_sse_async()
    elif mcp_config.transport == "http":
        # Use localhost for display if binding to 0.0.0.0
        display_host = (
            "localhost"
            if mcp_instance.settings.host == "0.0.0.0"
            else mcp_instance.settings.host
        )
        logger.info(
            f"Running MCP server with streamable HTTP transport on {mcp_instance.settings.host}:{mcp_instance.settings.port}"
        )
        logger.info("=" * 60)
        logger.info("MCP Server Access Information:")
        logger.info(f"  Base URL: http://{display_host}:{mcp_instance.settings.port}/")
        logger.info(
            f"  MCP Endpoint: http://{display_host}:{mcp_instance.settings.port}/mcp/"
        )
        logger.info("  Transport: HTTP (streamable)")
        logger.info("=" * 60)
        logger.info("For MCP clients, connect to the /mcp/ endpoint above")

        # Configure uvicorn logging to match our format
        configure_uvicorn_logging()

        # Add CORS middleware to the underlying FastAPI app
        # Use custom middleware to add CORS headers to all responses
        try:
            app = mcp_instance.streamable_http_app()
            app.add_middleware(CORSHeaderMiddleware)
            logger.info("CORS middleware enabled for cross-origin requests")
        except Exception as e:
            logger.warning(f"Could not add CORS middleware: {e}")

        await mcp_instance.run_streamable_http_async()
    else:
        raise ValueError(
            f'Unsupported transport: {mcp_config.transport}. Use "sse", "stdio", or "http"'
        )
