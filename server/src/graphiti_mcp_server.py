#!/usr/bin/env python3
"""
Graphiti MCP Server - Exposes Graphiti functionality through the Model Context Protocol (MCP)
"""

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load .env file from mcp_server directory
mcp_server_dir = Path(__file__).parent.parent
env_file = mcp_server_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    # Try current working directory as fallback
    load_dotenv()

# Configure proxy settings early for OpenAI SDK
# OpenAI SDK uses HTTP_PROXY and HTTPS_PROXY environment variables
from shared.utils.proxy_config import setup_proxy_environment

setup_proxy_environment()

# Configure structured logging with timestamps
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    stream=sys.stderr,
)

# Configure specific loggers
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # Reduce access log noise
logging.getLogger("mcp.server.streamable_http_manager").setLevel(
    logging.WARNING
)  # Reduce MCP noise

logger = logging.getLogger(__name__)

# MCP server instructions
GRAPHITI_MCP_INSTRUCTIONS = """
Graphiti is a memory service for AI agents built on a knowledge graph. Graphiti performs well
with dynamic data such as user interactions, changing enterprise data, and external information.

Graphiti transforms information into a richly connected knowledge network, allowing you to
capture relationships between concepts, entities, and information. The system organizes data as episodes
(content snippets), nodes (entities), and facts (relationships between entities), creating a dynamic,
queryable memory store that evolves with new information. Graphiti supports multiple data formats, including
structured JSON data, enabling seamless integration with existing data pipelines and systems.

Facts contain temporal metadata, allowing you to track the time of creation and whether a fact is invalid
(superseded by new information).

Key capabilities:
1. Add episodes (text, messages, or JSON) to the knowledge graph with the add_memory tool
2. Search for nodes (entities) in the graph using natural language queries with search_nodes
3. Find relevant facts (relationships between entities) with search_facts
4. Retrieve specific entity edges or episodes by UUID
5. Manage the knowledge graph with tools like delete_episode, delete_entity_edge, and clear_graph

The server connects to a database for persistent storage and uses language models for certain operations.
Each piece of information is organized by group_id, allowing you to maintain separate knowledge domains.

When adding information, provide descriptive names and detailed content to improve search quality.
When searching, use specific queries and consider filtering by group_id for more relevant results.

For optimal performance, ensure the database is properly configured and accessible, and valid
API keys are provided for any language model operations.
"""

# MCP server instance
mcp = FastMCP(
    "Graphiti Agent Memory",
    instructions=GRAPHITI_MCP_INSTRUCTIONS,
)


# ============================================================================
# Tool Registration
# ============================================================================

# Import tools from modular tool packages
from tools import citation_tools, memory_tools, search_tools, status_tools

# Register memory tools
mcp.tool()(memory_tools.add_memory)
mcp.tool()(memory_tools.clear_graph)
mcp.tool()(memory_tools.delete_episode)
mcp.tool()(memory_tools.delete_entity_edge)
mcp.tool()(memory_tools.get_entity_edge)
mcp.tool()(memory_tools.get_episodes)

# Register search tools
mcp.tool()(search_tools.search_nodes)
mcp.tool()(search_tools.search_memory_facts)

# Register citation tools
mcp.tool()(citation_tools.search_with_citations)
mcp.tool()(citation_tools.get_citation_chain_tool)

# Register status tool
mcp.tool()(status_tools.get_status)


# ============================================================================
# HTTP Endpoints Registration
# ============================================================================

from server import http_endpoints

# Register health check endpoint
mcp.custom_route("/health", methods=["GET"])(http_endpoints.health_check)

# Register REST API endpoints
mcp.custom_route("/graph/episodes", methods=["POST"])(
    http_endpoints.create_episode_endpoint
)
mcp.custom_route("/graph/search", methods=["POST", "OPTIONS"])(
    http_endpoints.graph_search_endpoint
)
mcp.custom_route("/graph/episodes/{uuid}", methods=["DELETE", "OPTIONS"])(
    http_endpoints.delete_episode_endpoint
)
mcp.custom_route("/graph/facts/{uuid}", methods=["PATCH", "OPTIONS"])(
    http_endpoints.update_fact_endpoint
)

# Pattern Analysis endpoints
mcp.custom_route("/graph/analysis/causality-timeline", methods=["GET", "OPTIONS"])(
    http_endpoints.causality_timeline_endpoint
)
mcp.custom_route("/graph/analysis/recurring-incidents", methods=["GET", "OPTIONS"])(
    http_endpoints.recurring_incidents_endpoint
)

# CVR Analysis endpoints (SRE-style Conversion Rate Analysis)
mcp.custom_route("/graph/analysis/component-impact", methods=["GET", "OPTIONS"])(
    http_endpoints.component_impact_endpoint
)
mcp.custom_route("/graph/analysis/component-severity", methods=["GET", "OPTIONS"])(
    http_endpoints.component_severity_endpoint
)
mcp.custom_route("/graph/analysis/flow-metrics", methods=["GET", "OPTIONS"])(
    http_endpoints.flow_metrics_endpoint
)


# ============================================================================
# Server Initialization and Main Entry Point
# ============================================================================

from server.mcp_setup import run_mcp_server


def main():
    """Main function to run the Graphiti MCP server."""
    try:
        # Run everything in a single event loop
        asyncio.run(run_mcp_server(mcp))
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Error initializing Graphiti MCP server: {str(e)}")
        raise


if __name__ == "__main__":
    main()
