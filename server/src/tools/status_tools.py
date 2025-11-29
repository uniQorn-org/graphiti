"""Status tool for checking server and database health."""

import logging

from models.response_types import StatusResponse
from services.service_container import ServiceContainer

logger = logging.getLogger(__name__)


async def get_status() -> StatusResponse:
    """Get the status of the Graphiti MCP server and database connection."""
    try:
        graphiti_service = ServiceContainer.get_graphiti_service()
    except RuntimeError:
        return StatusResponse(
            status="error", message="Graphiti service not initialized"
        )

    try:
        client = await graphiti_service.get_client()

        # Test database connection with a simple query
        async with client.driver.session() as session:
            result = await session.run("MATCH (n) RETURN count(n) as count")
            # Consume the result to verify query execution
            if result:
                _ = [record async for record in result]

        # Use the provider from the service's config, not the global
        provider_name = graphiti_service.config.database.provider
        return StatusResponse(
            status="ok",
            message=f"Graphiti MCP server is running and connected to {provider_name} database",
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error checking database connection: {error_msg}")
        return StatusResponse(
            status="error",
            message=f"Graphiti MCP server is running but database connection failed: {error_msg}",
        )
