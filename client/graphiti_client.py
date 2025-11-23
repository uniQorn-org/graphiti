"""Graphiti Client Adapter for Knowledge Graph Operations.

This module provides a wrapper around graphiti-core for:
- Episode ingestion (add_episode)
- Fact management (add_facts, invalidate facts)
- Hybrid search (embedding + BM25 + graph traversal)
- Entity/Community management
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

load_dotenv()


class GraphitiClient:
    """Graphiti Knowledge Graph Client."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """Initialize Graphiti client.

        Args:
            uri: Neo4j connection URI (default: from env NEO4J_URI)
            user: Neo4j username (default: from env NEO4J_USER)
            password: Neo4j password (default: from env NEO4J_PASSWORD)
        """
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password123")

        self.graphiti = Graphiti(self.uri, self.user, self.password)

    async def ensure_ready(self) -> None:
        """Ensure Graphiti is ready by building indices and constraints."""
        await self.graphiti.build_indices_and_constraints()

    async def add_episode(
        self,
        name: str,
        episode_body: str | Dict[str, Any],
        source: str = "system",
        source_description: Optional[str] = None,
        reference_time: Optional[datetime] = None,
        event_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Add an episode to the knowledge graph.

        Episodes represent events or observations that happened at a specific time.
        They follow a bi-temporal model with event_time (when it happened) and
        observed_time (when it was recorded).

        Args:
            name: Unique episode identifier (e.g., "task:123:abc")
            episode_body: Episode content (string or JSON dict)
            source: Source type (zoom_webhook, user_input, system, job_runtime)
            source_description: Human-readable source description
            reference_time: Reference time for the episode (defaults to now)
            event_time: When the event actually occurred (defaults to reference_time)

        Returns:
            Dict containing episode metadata and extracted entities/facts
        """
        # Convert episode_body to string if it's a dict
        if isinstance(episode_body, dict):
            import json

            body_str = json.dumps(episode_body, ensure_ascii=False)
        else:
            body_str = episode_body

        # Map source string to EpisodeType
        source_type_map = {
            "zoom_webhook": EpisodeType.json,
            "user_input": EpisodeType.text,
            "system": EpisodeType.json,
            "job_runtime": EpisodeType.json,
        }
        episode_type = source_type_map.get(source, EpisodeType.text)

        # Set timestamps
        now = datetime.now()
        ref_time = reference_time or now
        evt_time = event_time or ref_time

        result = await self.graphiti.add_episode(
            name=name,
            episode_body=body_str,
            source=episode_type,
            source_description=source_description or f"Episode from {source}",
            reference_time=ref_time,
        )

        return {
            "episode_name": name,
            "source": source,
            "event_time": evt_time.isoformat(),
            "observed_time": now.isoformat(),
            "result": result,
        }

    async def search(
        self,
        query: str,
        center_node_id: Optional[str] = None,
        num_results: int = 20,
    ) -> Dict[str, Any]:
        """Perform hybrid search on the knowledge graph.

        Uses RRF (Reciprocal Rank Fusion) combining:
        - Embedding similarity search
        - BM25 keyword search
        - Graph traversal from center node (if provided)

        Args:
            query: Natural language search query
            center_node_id: Optional center node for distance re-ranking
            num_results: Maximum number of results to return

        Returns:
            Dict containing:
            - nodes: List of matching entities
            - edges: List of relevant relationships
            - snippets: Text excerpts from episodes
            - explain: Search explanation/debug info
        """
        results = await self.graphiti.search(query=query, num_results=num_results)

        return {
            "query": query,
            "center_node": center_node_id,
            "num_results": len(results) if results else 0,
            "results": results,
        }

    async def add_task_episode(
        self,
        task_id: str,
        title: str,
        description: str,
        priority: str,
        source: str = "zoom_webhook",
        meeting_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a task creation episode.

        Args:
            task_id: Task UUID
            title: Task title
            description: Task description
            priority: Task priority (low, medium, high)
            source: Source of task creation
            meeting_id: Optional Zoom meeting ID

        Returns:
            Episode creation result
        """
        episode_body = {
            "event_type": "task_created",
            "task_id": task_id,
            "title": title,
            "description": description,
            "priority": priority,
            "meeting_id": meeting_id,
        }

        return await self.add_episode(
            name=f"task:{task_id}:created",
            episode_body=episode_body,
            source=source,
            source_description=f"Task '{title}' created from {source}",
        )

    async def add_workflow_episode(
        self,
        workflow_id: str,
        task_id: str,
        workflow_name: str,
        nodes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Add a workflow generation episode.

        Args:
            workflow_id: Workflow UUID
            task_id: Associated task UUID
            workflow_name: Workflow name
            nodes: List of workflow nodes/jobs

        Returns:
            Episode creation result
        """
        episode_body = {
            "event_type": "workflow_generated",
            "workflow_id": workflow_id,
            "task_id": task_id,
            "workflow_name": workflow_name,
            "num_nodes": len(nodes),
            "nodes": nodes,
        }

        return await self.add_episode(
            name=f"workflow:{workflow_id}:generated",
            episode_body=episode_body,
            source="system",
            source_description=f"Workflow '{workflow_name}' generated for task {task_id}",
        )

    async def add_job_execution_episode(
        self,
        job_id: str,
        workflow_id: str,
        node_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add a job execution episode.

        Args:
            job_id: Job UUID
            workflow_id: Parent workflow UUID
            node_id: Node identifier
            status: Job status (pending, running, success, failed)
            result: Optional job execution result

        Returns:
            Episode creation result
        """
        episode_body = {
            "event_type": "job_executed",
            "job_id": job_id,
            "workflow_id": workflow_id,
            "node_id": node_id,
            "status": status,
            "result": result,
        }

        return await self.add_episode(
            name=f"job:{job_id}:{status}",
            episode_body=episode_body,
            source="job_runtime",
            source_description=f"Job {node_id} {status}",
        )

    async def add_conversation_episode(
        self, session_id: str, task_id: str, question: str, answer: str, field: str
    ) -> Dict[str, Any]:
        """Add a conversation turn episode.

        Records a single question-answer exchange in the conversation.

        Args:
            session_id: Conversation session UUID
            task_id: Associated task UUID
            question: Question text
            answer: User's answer
            field: Field name being collected

        Returns:
            Episode creation result
        """
        episode_body = {
            "event_type": "conversation_turn",
            "session_id": session_id,
            "task_id": task_id,
            "question": question,
            "answer": answer,
            "field": field,
        }

        return await self.add_episode(
            name=f"conversation:{session_id}:{field}",
            episode_body=episode_body,
            source="user_input",
            source_description=f"Conversation about {field} for task {task_id}",
        )

    async def search_similar_tasks(
        self, task_title: str, task_description: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar tasks.

        Phase 2 implementation: Search Graphiti for tasks with similar
        titles, descriptions, and execution patterns.

        Args:
            task_title: Task title
            task_description: Task description
            limit: Maximum number of results

        Returns:
            List of similar tasks with metadata
        """
        # Phase 1: Return empty list (stub)
        # Phase 2: Implement actual search
        query = f"""
        過去に実行された以下のようなタスクを探してください：
        タイトル: {task_title}
        説明: {task_description}
        
        特に以下の情報を含むタスクを優先してください：
        - 担当者情報
        - 必要なリソース
        - 実行手順
        - 注意事項
        """

        try:
            results = await self.search(query, num_results=limit)
            return self._extract_task_info(results)
        except Exception as e:
            print(f"[search_similar_tasks] Error: {e}")
            return []

    async def search_task_context(
        self, field: str, task_title: str, task_description: str
    ) -> List[Dict[str, Any]]:
        """Search for context about a specific field.

        Phase 2 implementation: Search for information about specific
        fields like responsible_person, deadline, resources, etc.

        Args:
            field: Field name to search for
            task_title: Task title for context
            task_description: Task description for context

        Returns:
            List of suggestions for the field
        """
        # Phase 1: Return empty list (stub)
        # Phase 2: Implement field-specific search
        queries = {
            "responsible_person": f"'{task_title}'のようなタスクは通常誰が担当していますか？",
            "deadline": f"'{task_title}'の標準的な所要時間はどのくらいですか？",
            "resources": f"'{task_title}'を実行するために必要な情報やドキュメントは何ですか？",
            "dependencies": f"'{task_title}'を始める前に完了すべきタスクはありますか？",
        }

        if field not in queries:
            return []

        try:
            results = await self.search(queries[field], num_results=10)
            return self._extract_field_suggestions(results, field)
        except Exception as e:
            print(f"[search_task_context] Error: {e}")
            return []

    def _extract_task_info(
        self, search_results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract task information from search results.

        Phase 2 implementation: Parse search results and extract
        structured task information.

        Args:
            search_results: Raw search results from Graphiti

        Returns:
            Structured task information
        """
        # Phase 1: Return empty list (stub)
        # Phase 2: Parse and structure results
        return []

    def _extract_field_suggestions(
        self, search_results: Dict[str, Any], field: str
    ) -> List[Dict[str, Any]]:
        """Extract field suggestions from search results.

        Phase 2 implementation: Parse search results and extract
        suggestions for a specific field.

        Args:
            search_results: Raw search results from Graphiti
            field: Field name

        Returns:
            List of suggestions with confidence scores
        """
        # Phase 1: Return empty list (stub)
        # Phase 2: Parse and extract field-specific suggestions
        return []

    async def close(self) -> None:
        """Close the Graphiti client connection."""
        await self.graphiti.close()


# Global client instance
_graphiti_client: Optional[GraphitiClient] = None


def get_graphiti_client() -> GraphitiClient:
    """Get or create the global Graphiti client instance."""
    global _graphiti_client
    if _graphiti_client is None:
        _graphiti_client = GraphitiClient()
    return _graphiti_client


async def init_graphiti() -> GraphitiClient:
    """Initialize Graphiti client and ensure it's ready."""
    client = get_graphiti_client()
    await client.ensure_ready()
    return client
