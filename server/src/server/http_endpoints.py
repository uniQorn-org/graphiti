"""HTTP REST API endpoints for the MCP server."""

from routers.graph_api import (create_episode_api, delete_episode_api,
                               get_cause_category_analysis_api,
                               get_causality_timeline_api,
                               get_component_impact_api,
                               get_component_severity_api,
                               get_flow_metrics_api,
                               get_entity_cooccurrence_api,
                               get_recurring_incidents_api,
                               get_root_causes_api, get_service_frequency_api,
                               search_graph_api, update_fact_api)
from services.service_container import ServiceContainer
from starlette.responses import JSONResponse


async def health_check(request) -> JSONResponse:
    """Health check endpoint for Docker and load balancers."""
    return JSONResponse({"status": "healthy", "service": "graphiti-mcp"})


async def create_episode_endpoint(request):
    """Create a new episode (add to memory).

    POST /graph/episodes
    Body: {
        "name": "Episode name",
        "content": "Episode content",
        "group_id": "optional",
        "source": "text|json|message",
        "source_description": "optional",
        "uuid": "optional"
    }
    """
    graphiti_service = ServiceContainer.get_graphiti_service()
    queue_service = ServiceContainer.get_queue_service()
    config = ServiceContainer.get_config()
    return await create_episode_api(request, graphiti_service, queue_service, config)


async def graph_search_endpoint(request):
    """Search the graph for nodes, facts, or episodes.

    POST /graph/search
    Body: {
        "query": "search query",
        "search_type": "facts|nodes|episodes",
        "max_results": 10,
        "group_ids": ["group1", "group2"],
        "entity_types": ["Person", "Organization"],
        "center_node_uuid": "optional-uuid"
    }
    """
    # CORS headers are handled by CORSHeaderMiddleware
    if request.method == "OPTIONS":
        return JSONResponse({"status": "ok"}, status_code=200)

    graphiti_service = ServiceContainer.get_graphiti_service()
    config = ServiceContainer.get_config()
    return await search_graph_api(request, graphiti_service, config)


async def delete_episode_endpoint(request):
    """Delete an episode and all related nodes/facts by UUID.

    DELETE /graph/episodes/{uuid}
    """
    # CORS headers are handled by CORSHeaderMiddleware
    if request.method == "OPTIONS":
        return JSONResponse({"status": "ok"}, status_code=200)

    graphiti_service = ServiceContainer.get_graphiti_service()
    return await delete_episode_api(request, graphiti_service)


async def update_fact_endpoint(request):
    """Update a fact by creating a new version and expiring the old one.

    PATCH /graph/facts/{uuid}
    Body: {
        "fact": "new fact text",
        "source_node_uuid": "optional",
        "target_node_uuid": "optional",
        "attributes": {"key": "value"}
    }
    """
    # CORS headers are handled by CORSHeaderMiddleware
    if request.method == "OPTIONS":
        return JSONResponse({"status": "ok"}, status_code=200)

    graphiti_service = ServiceContainer.get_graphiti_service()
    return await update_fact_api(request, graphiti_service)


# ============================================================================
# Pattern Analysis Endpoints
# ============================================================================


async def causality_timeline_endpoint(request):
    """Track causality relationships over time.

    GET /graph/analysis/causality-timeline?component=web-prod-01&category=reason/canary
    """
    if request.method == "OPTIONS":
        return JSONResponse({"status": "ok"}, status_code=200)

    graphiti_service = ServiceContainer.get_graphiti_service()
    config = ServiceContainer.get_config()
    return await get_causality_timeline_api(request, graphiti_service, config)


async def recurring_incidents_endpoint(request):
    """Detect recurring incidents using basic or advanced analysis.

    GET /graph/analysis/recurring-incidents?min_occurrences=2&similarity_threshold=0.75&use_llm=true
    """
    if request.method == "OPTIONS":
        return JSONResponse({"status": "ok"}, status_code=200)

    graphiti_service = ServiceContainer.get_graphiti_service()
    config = ServiceContainer.get_config()
    return await get_recurring_incidents_api(request, graphiti_service, config)


async def component_impact_endpoint(request):
    """Analyze component contribution rate by cause category (CVR-style).

    GET /graph/analysis/component-impact?min_incidents=2&category_filter=reason/config
    """
    if request.method == "OPTIONS":
        return JSONResponse({"status": "ok"}, status_code=200)

    graphiti_service = ServiceContainer.get_graphiti_service()
    config = ServiceContainer.get_config()
    return await get_component_impact_api(request, graphiti_service, config)


async def component_severity_endpoint(request):
    """Analyze component severity conversion rate.

    GET /graph/analysis/component-severity?min_incidents=2&component_filter=web-prod-01
    """
    if request.method == "OPTIONS":
        return JSONResponse({"status": "ok"}, status_code=200)

    graphiti_service = ServiceContainer.get_graphiti_service()
    config = ServiceContainer.get_config()
    return await get_component_severity_api(request, graphiti_service, config)


async def flow_metrics_endpoint(request):
    """Analyze cause → component → impact flow with CVR metrics.

    GET /graph/analysis/flow-metrics?min_flow_count=1&category_filter=reason/config
    """
    if request.method == "OPTIONS":
        return JSONResponse({"status": "ok"}, status_code=200)

    graphiti_service = ServiceContainer.get_graphiti_service()
    config = ServiceContainer.get_config()
    return await get_flow_metrics_api(request, graphiti_service, config)
