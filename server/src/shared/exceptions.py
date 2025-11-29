"""Custom exception classes for Graphiti."""


class GraphitiError(Exception):
    """Base exception for all Graphiti errors."""
    pass


class IngestionError(GraphitiError):
    """Error during data ingestion from external sources."""
    pass


class MCPClientError(GraphitiError):
    """Error in MCP client communication."""
    pass


class DatabaseConnectionError(GraphitiError):
    """Database connection failure."""

    def __init__(self, provider: str, connection_string: str, original_error: Exception | None = None):
        self.provider = provider
        self.connection_string = connection_string
        self.original_error = original_error
        message = f"Failed to connect to {provider} at {connection_string}"
        if original_error:
            message += f": {str(original_error)}"
        super().__init__(message)


class ConfigurationError(GraphitiError):
    """Configuration error."""
    pass


class TranslationError(GraphitiError):
    """Error during text translation."""
    pass


class ValidationError(GraphitiError):
    """Data validation error."""
    pass
