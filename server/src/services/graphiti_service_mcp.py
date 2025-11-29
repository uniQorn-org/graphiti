"""Graphiti Service for MCP Server."""

import asyncio
import logging
from typing import Any

from config.schema import GraphitiConfig
from graphiti_core import Graphiti
from pydantic import BaseModel
from services.factories import (DatabaseDriverFactory, EmbedderFactory,
                                LLMClientFactory)

logger = logging.getLogger(__name__)


class GraphitiService:
    """Graphiti service using the unified configuration system."""

    def __init__(self, config: GraphitiConfig, semaphore_limit: int = 10):
        self.config = config
        self.semaphore_limit = semaphore_limit
        self.semaphore = asyncio.Semaphore(semaphore_limit)
        self.client: Graphiti | None = None
        self.entity_types = None

    def _create_llm_and_embedder_clients(self):
        """Create LLM and Embedder clients using factories."""
        llm_client = None
        embedder_client = None

        try:
            llm_client = LLMClientFactory.create(self.config.llm)
        except Exception as e:
            logger.warning(f"Failed to create LLM client: {e}")

        try:
            embedder_client = EmbedderFactory.create(self.config.embedder)
        except Exception as e:
            logger.warning(f"Failed to create embedder client: {e}")

        return llm_client, embedder_client

    def _build_entity_types(self):
        """Build custom entity types from configuration."""
        if not self.config.graphiti.entity_types:
            return None

        custom_types = {}
        for entity_type in self.config.graphiti.entity_types:
            # Create a dynamic Pydantic model for each entity type
            entity_model = type(
                entity_type.name,
                (BaseModel,),
                {"__doc__": entity_type.description},
            )
            custom_types[entity_type.name] = entity_model

        return custom_types

    def _create_graphiti_client(self, llm_client, embedder_client, db_config):
        """Initialize Graphiti client with appropriate database driver."""
        if self.config.database.provider.lower() == "falkordb":
            from graphiti_core.driver.falkordb_driver import FalkorDriver

            falkor_driver = FalkorDriver(
                host=db_config["host"],
                port=db_config["port"],
                password=db_config["password"],
                database=db_config["database"],
            )

            return Graphiti(
                graph_driver=falkor_driver,
                llm_client=llm_client,
                embedder=embedder_client,
                max_coroutines=self.semaphore_limit,
            )
        else:
            # For Neo4j (default)
            return Graphiti(
                uri=db_config["uri"],
                user=db_config["user"],
                password=db_config["password"],
                llm_client=llm_client,
                embedder=embedder_client,
                max_coroutines=self.semaphore_limit,
            )

    def _handle_database_connection_error(self, db_error: Exception, db_config: dict):
        """Handle database connection errors with helpful messages."""
        error_msg = str(db_error).lower()
        if "connection refused" not in error_msg and "could not connect" not in error_msg:
            raise

        db_provider = self.config.database.provider

        if db_provider.lower() == "falkordb":
            raise RuntimeError(
                f"\n{'=' * 70}\n"
                f"Database Connection Error: FalkorDB is not running\n"
                f"{'=' * 70}\n\n"
                f"FalkorDB at {db_config['host']}:{db_config['port']} is not accessible.\n\n"
                f"To start FalkorDB:\n"
                f"  - Using Docker Compose: cd mcp_server && docker compose up\n"
                f"  - Or run FalkorDB manually: docker run -p 6379:6379 falkordb/falkordb\n\n"
                f"{'=' * 70}\n"
            ) from db_error
        elif db_provider.lower() == "neo4j":
            raise RuntimeError(
                f"\n{'=' * 70}\n"
                f"Database Connection Error: Neo4j is not running\n"
                f"{'=' * 70}\n\n"
                f"Neo4j at {db_config.get('uri', 'unknown')} is not accessible.\n\n"
                f"To start Neo4j:\n"
                f"  - Using Docker Compose: cd mcp_server && docker compose -f docker/docker-compose-neo4j.yml up\n"
                f"  - Or install Neo4j Desktop from: https://neo4j.com/download/\n"
                f"  - Or run Neo4j manually: docker run -p 7474:7474 -p 7687:7687 neo4j:latest\n\n"
                f"{'=' * 70}\n"
            ) from db_error
        else:
            raise RuntimeError(
                f"\n{'=' * 70}\n"
                f"Database Connection Error: {db_provider} is not running\n"
                f"{'=' * 70}\n\n"
                f"{db_provider} at {db_config.get('uri', 'unknown')} is not accessible.\n\n"
                f"Please ensure {db_provider} is running and accessible.\n\n"
                f"{'=' * 70}\n"
            ) from db_error

    def _log_configuration(self, llm_client, embedder_client):
        """Log configuration details after successful initialization."""
        logger.info("Successfully initialized Graphiti client")

        if llm_client:
            logger.info(f"Using LLM provider: {self.config.llm.provider} / {self.config.llm.model}")
        else:
            logger.info("No LLM client configured - entity extraction will be limited")

        if embedder_client:
            logger.info(f"Using Embedder provider: {self.config.embedder.provider}")
        else:
            logger.info("No Embedder client configured - search will be limited")

        if self.entity_types:
            entity_type_names = list(self.entity_types.keys())
            logger.info(f"Using custom entity types: {', '.join(entity_type_names)}")
        else:
            logger.info("Using default entity types")

        logger.info(f"Using database: {self.config.database.provider}")
        logger.info(f"Using group_id: {self.config.graphiti.group_id}")

    async def initialize(self) -> None:
        """Initialize the Graphiti client with factory-created components."""
        try:
            # Create clients using factories
            llm_client, embedder_client = self._create_llm_and_embedder_clients()

            # Build entity types
            self.entity_types = self._build_entity_types()

            # Get database configuration
            db_config = DatabaseDriverFactory.create_config(self.config.database)

            # Initialize Graphiti client
            try:
                self.client = self._create_graphiti_client(llm_client, embedder_client, db_config)
            except Exception as db_error:
                self._handle_database_connection_error(db_error, db_config)

            # Build indices
            await self.client.build_indices_and_constraints()

            # Log configuration
            self._log_configuration(llm_client, embedder_client)

        except Exception as e:
            logger.error(f"Failed to initialize Graphiti client: {e}")
            raise

    async def get_client(self) -> Graphiti:
        """Get the Graphiti client, initializing if necessary."""
        if self.client is None:
            await self.initialize()
        if self.client is None:
            raise RuntimeError("Failed to initialize Graphiti client")
        return self.client
