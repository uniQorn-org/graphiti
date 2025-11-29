"""CORS middleware for Graphiti MCP server."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class CORSHeaderMiddleware(BaseHTTPMiddleware):
    """Add CORS headers to all responses."""

    async def dispatch(self, request, call_next):
        # Handle OPTIONS requests for preflight
        if request.method == "OPTIONS":
            response = Response(status_code=200)
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, PATCH, OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Max-Age"] = "3600"
            return response

        # Process the request
        response = await call_next(request)

        # Add CORS headers to the response
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, PATCH, OPTIONS"
        )
        response.headers["Access-Control-Allow-Headers"] = "*"

        return response
