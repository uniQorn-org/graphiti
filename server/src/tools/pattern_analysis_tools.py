"""Pattern analysis tools for detecting incident patterns and trends."""

import logging
import re
from typing import Optional

from models.response_types import ErrorResponse
from services.service_container import ServiceContainer

logger = logging.getLogger(__name__)


# ============================================================================
# Entity Filtering Constants
# ============================================================================

# Entities to exclude from technical analysis (incident management tools)
TOOL_ENTITY_PATTERNS = [
    "PagerDuty",
    "Git",
    "issue metadata",
    "Slack",
    "backlog",
    "runbook",
    "guideline",
    "on-call engineer",
    "dashboard",
    "example.com",  # Example URLs
    "SLO Dashboard",
    "Monitoring System",
]

# Keywords indicating causality relationships
CAUSALITY_KEYWORDS = [
    "caused",
    "triggered",
    "linked",
    "introduced",
    "resulted in",
    "led to",
    "due to",
    "because of",
    "rolled back",
    "mitigated",
    "resolved by",
]


def is_tool_entity(entity_name: str) -> bool:
    """Check if an entity is an incident management tool (not technical)."""
    entity_lower = entity_name.lower()
    return any(pattern.lower() in entity_lower for pattern in TOOL_ENTITY_PATTERNS)


# ============================================================================
# Temporal Causality Tracking and Recurrence Detection
# ============================================================================


async def _get_episode_causality_chain(client, episode_uuid: str) -> list[dict]:
    """Extract causality relationships for a specific episode.

    Args:
        client: Graphiti client
        episode_uuid: Episode UUID

    Returns:
        List of causality relationships
    """
    # Query to find RELATES_TO relationships with causality keywords
    query = """
    MATCH (e:Episodic {uuid: $episode_uuid})-[:MENTIONS]->(entity1:Entity)
    MATCH (entity1)-[r:RELATES_TO]->(entity2:Entity)
    WHERE any(keyword IN $causality_keywords WHERE toLower(r.fact) CONTAINS keyword)
    RETURN entity1.name as from_entity,
           r.fact as relationship,
           entity2.name as to_entity
    """

    async with client.driver.session() as session:
        result = await session.run(
            query,
            episode_uuid=episode_uuid,
            causality_keywords=CAUSALITY_KEYWORDS
        )
        records = await result.data()

    causality_chain = []
    for record in records:
        causality_chain.append({
            "from_entity": record["from_entity"],
            "to_entity": record["to_entity"],
            "relationship": record["relationship"],
        })

    return causality_chain


def _extract_cause_category(content: str) -> Optional[str]:
    """Extract cause category from episode content.

    Looks for Labels section with reason/xxx pattern.

    Args:
        content: Episode content text

    Returns:
        Cause category (e.g., "reason/canary") or None
    """
    # Pattern to match "Labels: Alert; reason/xxx"
    pattern = r"Labels:\s*Alert;\s*(reason/\w+)"

    match = re.search(pattern, content, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


async def get_causality_timeline(
    component: str | None = None,
    category: str | None = None,
    group_ids: list[str] | None = None,
) -> dict | ErrorResponse:
    """Track causality relationships over time.

    Args:
        component: Optional component name to filter by
        category: Optional cause category (reason/xxx) to filter by
        group_ids: Optional list of group IDs to filter results

    Returns:
        Dict with timeline of causality chains, or ErrorResponse
    """
    try:
        graphiti_service = ServiceContainer.get_graphiti_service()
        config = ServiceContainer.get_config()
    except RuntimeError as e:
        return ErrorResponse(error=str(e))

    try:
        client = await graphiti_service.get_client()

        # Resolve group IDs
        effective_group_ids = group_ids if group_ids else [config.graphiti.group_id]

        # Build filters
        group_filter = ""
        component_filter = ""

        if effective_group_ids:
            group_list = ", ".join([f"'{gid}'" for gid in effective_group_ids])
            group_filter = f"WHERE e.group_id IN [{group_list}]"

        if component:
            component_filter = """
            AND EXISTS((e)-[:MENTIONS]->(:Entity {name: $component}))
            """

        # Query to get episodes in chronological order
        query = f"""
        MATCH (e:Episodic)
        {group_filter}
        {component_filter}
        RETURN e.uuid as episode_uuid,
               e.name as episode_name,
               e.valid_at as valid_at,
               e.content as content,
               e.source_description as source_description
        ORDER BY e.valid_at ASC
        """

        params = {}
        if component:
            params["component"] = component

        async with client.driver.session() as session:
            result = await session.run(query, params)
            episode_records = await result.data()

        # Build timeline
        timeline = []
        component_history = {}

        for ep_record in episode_records:
            # Extract cause category
            content = ep_record.get("content", "")
            cause_category = _extract_cause_category(content)

            # Filter by category if specified
            if category and cause_category != category:
                continue

            # Get causality chains for this episode
            causality_chains = await _get_episode_causality_chain(
                client, ep_record["episode_uuid"]
            )

            # Extract components from causality chains
            components_in_episode = set()
            for chain in causality_chains:
                if not is_tool_entity(chain["from_entity"]):
                    components_in_episode.add(chain["from_entity"])
                if not is_tool_entity(chain["to_entity"]):
                    components_in_episode.add(chain["to_entity"])

            # Build timeline entry
            timeline_entry = {
                "date": ep_record["valid_at"].isoformat() if ep_record["valid_at"] else None,
                "episode_uuid": ep_record["episode_uuid"],
                "episode_name": ep_record["episode_name"],
                "cause_category": cause_category,
                "causality_chains": causality_chains,
                "components": list(components_in_episode),
            }
            timeline.append(timeline_entry)

            # Track component history
            for comp in components_in_episode:
                if comp not in component_history:
                    component_history[comp] = {
                        "occurrences": 0,
                        "first_incident": None,
                        "last_incident": None,
                        "incidents": [],
                    }

                comp_history = component_history[comp]
                comp_history["occurrences"] += 1

                incident_date = ep_record["valid_at"].isoformat() if ep_record["valid_at"] else None

                if comp_history["first_incident"] is None:
                    comp_history["first_incident"] = incident_date
                comp_history["last_incident"] = incident_date

                comp_history["incidents"].append({
                    "date": incident_date,
                    "episode_uuid": ep_record["episode_uuid"],
                    "episode_name": ep_record["episode_name"],
                    "cause_category": cause_category,
                })

        return {
            "message": f"Retrieved {len(timeline)} episodes in chronological order",
            "timeline": timeline,
            "component_history": component_history,
            "total_episodes": len(timeline),
            "filters": {
                "component": component,
                "category": category,
            }
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error tracking causality timeline: {error_msg}")
        return ErrorResponse(error=f"Error tracking causality timeline: {error_msg}")


# ============================================================================
# LLM/Embedding-based Similarity Detection
# ============================================================================


async def _calculate_root_cause_similarity_embedding(
    client,
    root_cause1: str,
    root_cause2: str,
) -> float:
    """Calculate similarity between two root causes using embeddings.

    Args:
        client: Graphiti client with embedder
        root_cause1: First root cause text
        root_cause2: Second root cause text

    Returns:
        Cosine similarity score (0.0 to 1.0)
    """
    try:
        import numpy as np

        # Get embedder from client
        embedder = client.embedder

        # Create embeddings using Graphiti's embedder
        embedding1 = await embedder.create(root_cause1)
        embedding2 = await embedder.create(root_cause2)

        # Calculate cosine similarity
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

        return float(similarity)

    except Exception as e:
        logger.error(f"Error calculating embedding similarity: {e}")
        return 0.0


async def _compare_causality_patterns_llm(
    client,
    episode1: dict,
    episode2: dict,
) -> dict:
    """Compare causality patterns using LLM.

    Args:
        client: Graphiti client with LLM
        episode1: First episode with causality chains
        episode2: Second episode with causality chains

    Returns:
        Dict with similarity_score, similarity_reason, common_pattern, is_recurring
    """
    try:
        import json

        # Format causality chains as text
        def format_chains(chains):
            if not chains:
                return "No causality chain information available"
            return "\n".join([
                f"  {c['from_entity']} → {c['to_entity']}: {c['relationship']}"
                for c in chains
            ])

        chain1_text = format_chains(episode1.get("causality_chains", []))
        chain2_text = format_chains(episode2.get("causality_chains", []))

        # Build prompt
        prompt = f"""以下の2つの障害の因果関係チェーンを比較し、類似性を評価してください。

【障害1】
日時: {episode1.get('date', 'N/A')}
名前: {episode1.get('name', 'N/A')}
原因カテゴリ: {episode1.get('cause_category', 'N/A')}
因果関係:
{chain1_text}

【障害2】
日時: {episode2.get('date', 'N/A')}
名前: {episode2.get('name', 'N/A')}
原因カテゴリ: {episode2.get('cause_category', 'N/A')}
因果関係:
{chain2_text}

以下の観点で類似性を評価してください:
1. 原因の種類（設定ミス、キャパシティ不足、外部依存など）が同じか
2. 影響を受けたコンポーネントの種類が類似しているか
3. 障害の伝播パターン（A→B→Cの流れ）が似ているか

必ず以下のJSON形式で回答してください:
{{
  "similarity_score": <0.0から1.0の数値>,
  "similarity_reason": "<類似している理由または相違点の説明>",
  "common_pattern": "<共通する障害パターンの説明。類似度が低い場合は'なし'>",
  "is_recurring": <true または false>
}}"""

        # Call LLM
        llm_client = client.llm_client

        response = await llm_client.generate_response(
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse JSON response
        response_text = response.content if hasattr(response, 'content') else str(response)

        # Extract JSON from response (may have markdown code blocks)
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1

        if json_start >= 0 and json_end > json_start:
            json_text = response_text[json_start:json_end]
            result = json.loads(json_text)
        else:
            # Fallback if JSON parsing fails
            result = {
                "similarity_score": 0.0,
                "similarity_reason": "Failed to parse LLM response",
                "common_pattern": "N/A",
                "is_recurring": False,
            }

        return result

    except Exception as e:
        logger.error(f"Error comparing causality patterns with LLM: {e}")
        return {
            "similarity_score": 0.0,
            "similarity_reason": f"Error: {str(e)}",
            "common_pattern": "N/A",
            "is_recurring": False,
        }


async def get_recurring_incidents_advanced(
    similarity_threshold: float = 0.75,
    use_llm: bool = True,
    group_ids: list[str] | None = None,
) -> dict | ErrorResponse:
    """Detect recurring incidents using LLM and Embeddings.

    This function uses:
    - Embeddings to calculate root cause text similarity
    - LLM to compare causality pattern similarity

    Args:
        similarity_threshold: Minimum embedding similarity to trigger LLM comparison (default: 0.75)
        use_llm: Whether to use LLM for detailed comparison (default: True)
        group_ids: Optional list of group IDs to filter results

    Returns:
        Dict with advanced recurring patterns, or ErrorResponse
    """
    try:
        graphiti_service = ServiceContainer.get_graphiti_service()
        config = ServiceContainer.get_config()
    except RuntimeError as e:
        return ErrorResponse(error=str(e))

    try:
        client = await graphiti_service.get_client()

        # Resolve group IDs
        effective_group_ids = group_ids if group_ids else [config.graphiti.group_id]

        # Build group filter
        group_filter = ""
        if effective_group_ids:
            group_list = ", ".join([f"'{gid}'" for gid in effective_group_ids])
            group_filter = f"WHERE e.group_id IN [{group_list}]"

        # Get all episodes with details
        query = f"""
        MATCH (e:Episodic)
        {group_filter}
        RETURN e.uuid as episode_uuid,
               e.name as episode_name,
               e.valid_at as valid_at,
               e.content as content
        ORDER BY e.valid_at ASC
        """

        async with client.driver.session() as session:
            result = await session.run(query)
            episode_records = await result.data()

        # Build episode details with causality chains
        episodes = []
        for ep_record in episode_records:
            # Extract cause category and root cause
            content = ep_record.get("content", "")
            cause_category = _extract_cause_category(content)

            # Extract root cause section from content
            root_cause = ""
            if "Root cause" in content:
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if "Root cause" in line and i + 1 < len(lines):
                        # Get next few lines after "Root cause"
                        root_cause = "\n".join(lines[i+1:i+4]).strip()
                        break

            # Get causality chains
            causality_chains = await _get_episode_causality_chain(
                client, ep_record["episode_uuid"]
            )

            episodes.append({
                "uuid": ep_record["episode_uuid"],
                "name": ep_record["episode_name"],
                "date": ep_record["valid_at"].isoformat() if ep_record["valid_at"] else None,
                "cause_category": cause_category,
                "root_cause": root_cause,
                "causality_chains": causality_chains,
            })

        # Find similar episodes using Embeddings + LLM
        recurring_patterns = []

        for i, ep1 in enumerate(episodes):
            for ep2 in episodes[i+1:]:
                # Skip if no root cause text
                if not ep1["root_cause"] or not ep2["root_cause"]:
                    continue

                # Calculate embedding similarity
                embedding_sim = await _calculate_root_cause_similarity_embedding(
                    client, ep1["root_cause"], ep2["root_cause"]
                )

                # If similarity is above threshold, do detailed LLM comparison
                if embedding_sim >= similarity_threshold and use_llm:
                    llm_result = await _compare_causality_patterns_llm(
                        client, ep1, ep2
                    )

                    if llm_result["is_recurring"]:
                        # Calculate interval days
                        interval_days = None
                        from datetime import datetime
                        if ep1["date"] and ep2["date"]:
                            date1 = datetime.fromisoformat(ep1["date"].replace("Z", "+00:00"))
                            date2 = datetime.fromisoformat(ep2["date"].replace("Z", "+00:00"))
                            interval_days = abs((date2 - date1).days)

                        recurring_patterns.append({
                            "pattern_type": "llm_detected_similarity",
                            "similar_episodes": [
                                {
                                    "uuid": ep1["uuid"],
                                    "name": ep1["name"],
                                    "date": ep1["date"],
                                    "cause_category": ep1["cause_category"],
                                },
                                {
                                    "uuid": ep2["uuid"],
                                    "name": ep2["name"],
                                    "date": ep2["date"],
                                    "cause_category": ep2["cause_category"],
                                },
                            ],
                            "embedding_similarity": round(embedding_sim, 3),
                            "llm_similarity_score": llm_result["similarity_score"],
                            "common_pattern": llm_result["common_pattern"],
                            "llm_analysis": llm_result["similarity_reason"],
                            "is_recurring": True,
                            "interval_days": interval_days,
                        })

        return {
            "message": f"Found {len(recurring_patterns)} recurring patterns using LLM/Embedding analysis",
            "recurring_patterns": recurring_patterns,
            "total_patterns": len(recurring_patterns),
            "analysis_method": "LLM + Embedding" if use_llm else "Embedding only",
            "similarity_threshold": similarity_threshold,
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error detecting advanced recurring incidents: {error_msg}")
        return ErrorResponse(error=f"Error detecting advanced recurring incidents: {error_msg}")


# ============================================================================
# CVR Analysis Functions (Marketing-style Conversion Rate Analysis)
# ============================================================================


async def get_component_impact_analysis(
    min_incidents: int = 2,
    category_filter: str | None = None,
    component_filter: str | None = None,
    group_ids: list[str] | None = None,
) -> dict | ErrorResponse:
    """Analyze component contribution rate by cause category (CVR-style analysis).

    This function calculates how much each component contributes to incidents
    within each cause category, similar to marketing conversion rate analysis.

    Mapping:
    - (Purchase)/(Action) → (Component Involvement)/(Total Incidents for Cause)
    - "What percentage of reason/config incidents involve web-prod-01?"

    Args:
        min_incidents: Minimum number of incidents to include component (default: 2)
        category_filter: Optional cause category filter (e.g., "reason/config")
        component_filter: Optional component name filter
        group_ids: Optional list of group IDs to filter results

    Returns:
        Dict with component contribution rates by cause category, or ErrorResponse
    """
    try:
        # Reuse existing timeline data
        timeline_result = await get_causality_timeline(
            component=component_filter,
            category=category_filter,
            group_ids=group_ids
        )

        if isinstance(timeline_result, dict) and "error" in timeline_result:
            return timeline_result

        # Extract data from timeline
        timeline = timeline_result.get("timeline", [])
        component_history = timeline_result.get("component_history", {})

        # Count incidents by category
        category_totals = {}
        category_component_counts = {}

        for episode in timeline:
            category = episode.get("cause_category", "unknown")
            components = episode.get("components", [])
            episode_name = episode.get("episode_name", "")

            # Track category totals
            if category not in category_totals:
                category_totals[category] = 0
            category_totals[category] += 1

            # Track component involvement per category
            for component in components:
                if is_tool_entity(component):
                    continue

                key = (category, component)
                if key not in category_component_counts:
                    category_component_counts[key] = {
                        "count": 0,
                        "episodes": [],
                        "severe_count": 0
                    }

                category_component_counts[key]["count"] += 1
                category_component_counts[key]["episodes"].append(episode_name)

                # Check severity
                if "WARNING:2" in episode_name or "CRITICAL" in episode_name:
                    category_component_counts[key]["severe_count"] += 1

        # Build analysis results
        analysis_results = []

        for (category, component), data in category_component_counts.items():
            if data["count"] < min_incidents:
                continue

            total_for_cause = category_totals.get(category, 0)
            if total_for_cause == 0:
                continue

            contribution_rate = round(data["count"] / total_for_cause, 3)
            severe_count = data["severe_count"]

            # Severity weighted rate
            severity_weight = 1.0 + (severe_count / data["count"]) if data["count"] > 0 else 1.0
            severity_weighted_rate = round(contribution_rate * severity_weight, 3)

            analysis_results.append({
                "cause_category": category,
                "component": component,
                "incident_count": data["count"],
                "total_incidents_for_cause": total_for_cause,
                "contribution_rate": contribution_rate,
                "severe_incident_count": severe_count,
                "severity_weighted_rate": severity_weighted_rate,
                "sample_episodes": data["episodes"][:3],
            })

        # Sort by severity_weighted_rate descending
        analysis_results.sort(
            key=lambda x: (x["severity_weighted_rate"], x["contribution_rate"]),
            reverse=True
        )

        return {
            "message": f"Analyzed {len(analysis_results)} component-category pairs",
            "analysis_results": analysis_results,
            "total_pairs": len(analysis_results),
            "category_totals": category_totals,
            "filters": {
                "min_incidents": min_incidents,
                "category_filter": category_filter,
                "component_filter": component_filter,
            }
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error analyzing component impact: {error_msg}")
        return ErrorResponse(error=f"Error analyzing component impact: {error_msg}")


async def get_component_severity_conversion(
    min_incidents: int = 2,
    component_filter: str | None = None,
    group_ids: list[str] | None = None,
) -> dict | ErrorResponse:
    """Analyze component severity conversion rate (CVR from involvement to severe incident).

    This function calculates how likely a component's involvement leads to severe incidents,
    similar to marketing "Action to Purchase" conversion rate.

    Mapping:
    - (Purchase)/(Action) → (Severe Incidents)/(Total Component Involvements)
    - "What percentage of incidents involving web-prod-01 become PagerDuty incidents?"

    Severe incident criteria:
    - Episode name contains "WARNING:2" or "CRITICAL"
    - Causality relationship contains "PagerDuty" or "triggered"
    - Causality relationship contains "SLO"

    Args:
        min_incidents: Minimum number of incidents for component to be included (default: 2)
        component_filter: Optional component name filter
        group_ids: Optional list of group IDs to filter results

    Returns:
        Dict with component severity conversion rates, or ErrorResponse
    """
    try:
        # Reuse existing timeline data
        timeline_result = await get_causality_timeline(
            component=component_filter,
            category=None,
            group_ids=group_ids
        )

        if isinstance(timeline_result, dict) and "error" in timeline_result:
            return timeline_result

        # Extract data from timeline
        timeline = timeline_result.get("timeline", [])

        # Track component incidents
        component_data = {}

        for episode in timeline:
            components = episode.get("components", [])
            episode_name = episode.get("episode_name", "")
            causality_chains = episode.get("causality_chains", [])

            # Check if episode is severe
            is_severe = False

            # Severity check 1: Episode name
            if "WARNING:2" in episode_name or "CRITICAL" in episode_name:
                is_severe = True

            # Severity check 2: Causality keywords
            if not is_severe:
                for chain in causality_chains:
                    relationship = chain.get("relationship", "")
                    if ("PagerDuty" in relationship or
                        "triggered" in relationship or
                        "SLO" in relationship):
                        is_severe = True
                        break

            # Track each component
            for component in components:
                if is_tool_entity(component):
                    continue

                if component not in component_data:
                    component_data[component] = {
                        "total_incidents": 0,
                        "severe_incidents": 0,
                        "severe_episodes": [],
                        "non_severe_episodes": []
                    }

                component_data[component]["total_incidents"] += 1

                if is_severe:
                    component_data[component]["severe_incidents"] += 1
                    component_data[component]["severe_episodes"].append(episode_name)
                else:
                    component_data[component]["non_severe_episodes"].append(episode_name)

        # Build analysis results
        analysis_results = []

        for component, data in component_data.items():
            if data["total_incidents"] < min_incidents:
                continue

            severity_conversion_rate = round(
                data["severe_incidents"] / data["total_incidents"], 3
            ) if data["total_incidents"] > 0 else 0.0

            analysis_results.append({
                "component": component,
                "total_incidents": data["total_incidents"],
                "severe_incidents": data["severe_incidents"],
                "non_severe_incidents": data["total_incidents"] - data["severe_incidents"],
                "severity_conversion_rate": severity_conversion_rate,
                "sample_severe_episodes": data["severe_episodes"][:3],
                "sample_non_severe_episodes": data["non_severe_episodes"][:3],
            })

        # Sort by severity_conversion_rate descending, then by severe_count
        analysis_results.sort(
            key=lambda x: (x["severity_conversion_rate"], x["severe_incidents"]),
            reverse=True
        )

        return {
            "message": f"Analyzed {len(analysis_results)} components for severity conversion",
            "analysis_results": analysis_results,
            "total_components": len(analysis_results),
            "filters": {
                "min_incidents": min_incidents,
                "component_filter": component_filter,
            },
            "severity_criteria": {
                "episode_name": ["WARNING:2", "CRITICAL"],
                "relationship_keywords": ["PagerDuty", "triggered", "SLO"],
            }
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error analyzing component severity conversion: {error_msg}")
        return ErrorResponse(error=f"Error analyzing component severity conversion: {error_msg}")


async def get_cause_to_impact_flow_metrics(
    min_flow_count: int = 1,
    category_filter: str | None = None,
    group_ids: list[str] | None = None,
) -> dict | ErrorResponse:
    """Analyze cause → component → impact flow with CVR metrics.

    This function calculates conversion rates at each stage of the causality flow,
    similar to marketing funnel analysis (Awareness → Interest → Action → Purchase).

    Mapping:
    - Awareness→Interest → reason/X → component involvement
    - Interest→Action → component involvement → severe impact
    - Action→Purchase → severe impact → SLO violation

    Args:
        min_flow_count: Minimum number of flows to include (default: 1)
        category_filter: Optional cause category filter
        group_ids: Optional list of group IDs to filter results

    Returns:
        Dict with flow metrics and conversion rates, or ErrorResponse
    """
    try:
        # Reuse existing timeline data
        timeline_result = await get_causality_timeline(
            component=None,
            category=category_filter,
            group_ids=group_ids
        )

        if isinstance(timeline_result, dict) and "error" in timeline_result:
            return timeline_result

        # Extract data from timeline
        timeline = timeline_result.get("timeline", [])

        # Analyze flows: cause category → component → impact levels
        flow_metrics = {}

        for episode in timeline:
            category = episode.get("cause_category", "unknown")
            components = episode.get("components", [])
            episode_name = episode.get("episode_name", "")
            causality_chains = episode.get("causality_chains", [])

            # Determine severity and SLO violation
            is_severe = False
            is_slo_violation = False

            # Check episode name
            if "WARNING:2" in episode_name or "CRITICAL" in episode_name:
                is_severe = True

            # Check causality chains
            for chain in causality_chains:
                relationship = chain.get("relationship", "")
                if ("PagerDuty" in relationship or "triggered" in relationship):
                    is_severe = True
                if "SLO" in relationship:
                    is_slo_violation = True

            # Track each component flow
            for component in components:
                if is_tool_entity(component):
                    continue

                flow_key = (category, component)

                if flow_key not in flow_metrics:
                    flow_metrics[flow_key] = {
                        "cause_category": category,
                        "component": component,
                        "total_flows": 0,
                        "severe_flows": 0,
                        "slo_violation_flows": 0,
                        "sample_episodes": [],
                    }

                flow_metrics[flow_key]["total_flows"] += 1

                if len(flow_metrics[flow_key]["sample_episodes"]) < 3:
                    flow_metrics[flow_key]["sample_episodes"].append(episode_name)

                if is_severe:
                    flow_metrics[flow_key]["severe_flows"] += 1
                if is_slo_violation:
                    flow_metrics[flow_key]["slo_violation_flows"] += 1

        # Calculate CVR metrics for each flow
        flow_results = []
        category_totals = {}

        for flow_key, metrics in flow_metrics.items():
            if metrics["total_flows"] < min_flow_count:
                continue

            category = metrics["cause_category"]
            component = metrics["component"]
            total_flows = metrics["total_flows"]
            severe_flows = metrics["severe_flows"]
            slo_flows = metrics["slo_violation_flows"]

            # Track category totals
            if category not in category_totals:
                category_totals[category] = 0
            category_totals[category] += total_flows

            # Calculate conversion rates
            # Stage 1: Cause → Component (already involved, so 100%)
            cause_to_component_rate = 1.0

            # Stage 2: Component → Severe Impact
            component_to_severe_rate = round(severe_flows / total_flows, 3) if total_flows > 0 else 0.0

            # Stage 3: Severe → SLO Violation
            severe_to_slo_rate = round(slo_flows / severe_flows, 3) if severe_flows > 0 else 0.0

            # End-to-end CVR: Cause → SLO Violation
            end_to_end_cvr = round(slo_flows / total_flows, 3) if total_flows > 0 else 0.0

            flow_results.append({
                "cause_category": category,
                "component": component,
                "total_flows": total_flows,
                "severe_flows": severe_flows,
                "slo_violation_flows": slo_flows,
                "cause_to_component_rate": cause_to_component_rate,
                "component_to_severe_rate": component_to_severe_rate,
                "severe_to_slo_rate": severe_to_slo_rate,
                "end_to_end_cvr": end_to_end_cvr,
                "sample_episodes": metrics["sample_episodes"],
                "episode_count": total_flows,
            })

        # Sort by end_to_end_cvr descending
        flow_results.sort(
            key=lambda x: (x["end_to_end_cvr"], x["total_flows"]),
            reverse=True
        )

        return {
            "message": f"Analyzed {len(flow_results)} cause-component flows",
            "flow_metrics": flow_results,
            "total_flows": len(flow_results),
            "category_totals": category_totals,
            "filters": {
                "min_flow_count": min_flow_count,
                "category_filter": category_filter,
            },
            "cvr_definitions": {
                "cause_to_component_rate": "Always 1.0 (already filtered to involved components)",
                "component_to_severe_rate": "Severe incidents / Total incidents",
                "severe_to_slo_rate": "SLO violations / Severe incidents",
                "end_to_end_cvr": "SLO violations / Total incidents"
            }
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error analyzing flow metrics: {error_msg}")
        return ErrorResponse(error=f"Error analyzing flow metrics: {error_msg}")
