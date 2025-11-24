"""Citation type definitions for Graphiti MCP Server."""

from typing import Any, TypedDict


class CitationInfo(TypedDict):
    """Information about a citation source (episode)."""

    episode_uuid: str
    episode_name: str
    source: str
    source_description: str
    created_at: str | None
    source_url: str | None


class FactWithCitations(TypedDict):
    """A fact (edge) with its citation information."""

    uuid: str
    from_node: str
    to_node: str
    fact: str
    created_at: str | None
    updated_at: str | None
    attributes: dict[str, Any]
    citations: list[CitationInfo]


class NodeWithCitations(TypedDict):
    """A node (entity) with its citation information."""

    uuid: str
    name: str
    labels: list[str]
    created_at: str | None
    summary: str | None
    group_id: str
    attributes: dict[str, Any]
    citations: list[CitationInfo]


class CitationChainEntry(TypedDict):
    """A single entry in a citation chain."""

    episode_uuid: str
    episode_name: str
    source: str
    source_description: str
    created_at: str | None
    operation: str  # "created", "updated", "referenced"
    source_url: str | None


class FactSearchWithCitationsResponse(TypedDict):
    """Response for search_with_citations tool (facts)."""

    message: str
    facts: list[FactWithCitations]


class NodeSearchWithCitationsResponse(TypedDict):
    """Response for search_with_citations tool (nodes)."""

    message: str
    nodes: list[NodeWithCitations]


class CitationChainResponse(TypedDict):
    """Response for get_citation_chain tool."""

    message: str
    target_uuid: str
    target_type: str  # "edge" or "node"
    chain: list[CitationChainEntry]
