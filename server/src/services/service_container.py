"""Service container for managing global application state.

This module provides a centralized location for accessing application-wide services
and configuration. It prevents circular import issues by being a dependency of other
modules without importing them.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config.schema import GraphitiConfig
    from services.graphiti_service_mcp import GraphitiService
    from services.queue_service import QueueService


class ServiceContainer:
    """Container for global application services and configuration."""

    _config: "GraphitiConfig | None" = None
    _graphiti_service: "GraphitiService | None" = None
    _queue_service: "QueueService | None" = None

    @classmethod
    def set_config(cls, config: "GraphitiConfig") -> None:
        """Set the global configuration instance."""
        cls._config = config

    @classmethod
    def set_graphiti_service(cls, service: "GraphitiService") -> None:
        """Set the global Graphiti service instance."""
        cls._graphiti_service = service

    @classmethod
    def set_queue_service(cls, service: "QueueService") -> None:
        """Set the global queue service instance."""
        cls._queue_service = service

    @classmethod
    def get_config(cls) -> "GraphitiConfig":
        """Get the global configuration instance.

        Raises:
            RuntimeError: If configuration has not been initialized
        """
        if cls._config is None:
            raise RuntimeError("Configuration not initialized")
        return cls._config

    @classmethod
    def get_graphiti_service(cls) -> "GraphitiService":
        """Get the global Graphiti service instance.

        Raises:
            RuntimeError: If Graphiti service has not been initialized
        """
        if cls._graphiti_service is None:
            raise RuntimeError("Graphiti service not initialized")
        return cls._graphiti_service

    @classmethod
    def get_queue_service(cls) -> "QueueService":
        """Get the global queue service instance.

        Raises:
            RuntimeError: If queue service has not been initialized
        """
        if cls._queue_service is None:
            raise RuntimeError("Queue service not initialized")
        return cls._queue_service

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if all services have been initialized."""
        return (
            cls._config is not None
            and cls._graphiti_service is not None
            and cls._queue_service is not None
        )
