#!/usr/bin/env python3
"""Visualize temporal causality tracking and recurrence detection from Graphiti."""

import json
from pathlib import Path
from datetime import datetime
import urllib.request
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# API base URL
# Use host.docker.internal when running inside Docker
import os
if os.path.exists("/.dockerenv"):
    API_BASE = "http://host.docker.internal:30547"
else:
    API_BASE = "http://localhost:30547"

# Color palette for cause categories
CATEGORY_COLORS = {
    "reason/canary": "#FF6B6B",
    "reason/config": "#4ECDC4",
    "reason/capacity": "#45B7D1",
    "reason/thirdparty": "#FFA07A",
    "reason/maintenance": "#98D8C8",
    "unknown": "#CCCCCC",
}


def fetch_api_data(endpoint: str) -> dict:
    """Fetch data from Graphiti API endpoint."""
    url = f"{API_BASE}{endpoint}"
    print(f"Fetching data from: {url}")

    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())

    return data


def fetch_timeline_data() -> dict:
    """Fetch causality timeline data."""
    return fetch_api_data("/graph/analysis/causality-timeline")


def fetch_recurring_patterns_basic() -> dict:
    """Fetch basic recurring patterns."""
    return fetch_api_data("/graph/analysis/recurring-incidents?min_occurrences=2")


def fetch_recurring_patterns_advanced() -> dict:
    """Fetch advanced recurring patterns with LLM."""
    return fetch_api_data("/graph/analysis/recurring-incidents?similarity_threshold=0.5&use_llm=true")


def calculate_similarity_matrix(timeline_data: dict, advanced_patterns: dict) -> dict:
    """Calculate similarity matrix for all episode pairs.

    Args:
        timeline_data: Timeline data with all episodes
        advanced_patterns: Advanced recurrence patterns with similarity scores

    Returns:
        Dict with episode_names list and similarity_matrix (2D array)
    """
    episodes = timeline_data.get("timeline", [])
    patterns = advanced_patterns.get("recurring_patterns", [])

    # Create episode name list
    episode_names = [ep["episode_name"] for ep in episodes]
    n = len(episode_names)

    # Initialize matrix with zeros
    matrix = [[0.0 for _ in range(n)] for _ in range(n)]

    # Fill diagonal with 1.0 (self-similarity)
    for i in range(n):
        matrix[i][i] = 1.0

    # Fill matrix with similarity scores from patterns
    for pattern in patterns:
        similar_eps = pattern.get("similar_episodes", [])
        if len(similar_eps) >= 2:
            ep1_uuid = similar_eps[0]["uuid"]
            ep2_uuid = similar_eps[1]["uuid"]
            similarity = pattern.get("embedding_similarity", 0.0)

            # Find indices
            idx1 = next((i for i, ep in enumerate(episodes) if ep["episode_uuid"] == ep1_uuid), None)
            idx2 = next((i for i, ep in enumerate(episodes) if ep["episode_uuid"] == ep2_uuid), None)

            if idx1 is not None and idx2 is not None:
                matrix[idx1][idx2] = similarity
                matrix[idx2][idx1] = similarity

    return {
        "episode_names": episode_names,
        "matrix": matrix,
        "patterns": patterns,
    }


def create_summary_cards(timeline_data: dict, advanced_patterns: dict) -> go.Figure:
    """Create summary indicator cards."""
    total_episodes = timeline_data.get("total_episodes", 0)
    total_patterns = advanced_patterns.get("total_patterns", 0)

    # Calculate average embedding similarity
    patterns = advanced_patterns.get("recurring_patterns", [])
    if patterns:
        avg_similarity = sum(p.get("embedding_similarity", 0.0) for p in patterns) / len(patterns)
    else:
        avg_similarity = 0.0

    # Find most frequent cause category
    timeline = timeline_data.get("timeline", [])
    categories = [ep.get("cause_category", "unknown") for ep in timeline]
    if categories:
        most_frequent_category = max(set(categories), key=categories.count)
    else:
        most_frequent_category = "N/A"

    # Find most impacted component
    component_history = timeline_data.get("component_history", {})
    if component_history:
        most_impacted = max(component_history.items(), key=lambda x: x[1]["occurrences"])
        most_impacted_name = most_impacted[0]
        most_impacted_count = most_impacted[1]["occurrences"]
    else:
        most_impacted_name = "N/A"
        most_impacted_count = 0

    # Create indicator cards
    fig = make_subplots(
        rows=1, cols=4,
        specs=[[{"type": "indicator"}, {"type": "indicator"},
                {"type": "indicator"}, {"type": "indicator"}]],
        horizontal_spacing=0.1
    )

    fig.add_trace(go.Indicator(
        mode="number+delta",
        value=total_episodes,
        title={"text": "総エピソード数"},
        delta={"reference": 0, "increasing": {"color": "#FF6B6B"}},
        domain={"x": [0, 1], "y": [0, 1]}
    ), row=1, col=1)

    fig.add_trace(go.Indicator(
        mode="number+delta",
        value=total_patterns,
        title={"text": "再発パターン検出数"},
        delta={"reference": 0, "increasing": {"color": "#FFA07A"}},
        domain={"x": [0, 1], "y": [0, 1]}
    ), row=1, col=2)

    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=avg_similarity,
        title={"text": "平均類似度"},
        gauge={"axis": {"range": [0, 1]}, "bar": {"color": "#45B7D1"}},
        domain={"x": [0, 1], "y": [0, 1]}
    ), row=1, col=3)

    fig.add_trace(go.Indicator(
        mode="number",
        value=most_impacted_count,
        title={"text": f"最多影響<br>{most_impacted_name[:20]}"},
        domain={"x": [0, 1], "y": [0, 1]}
    ), row=1, col=4)

    fig.update_layout(
        height=200,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='white',
    )

    return fig


def create_timeline_chart(timeline_data: dict) -> go.Figure:
    """Create interactive timeline chart."""
    timeline = timeline_data.get("timeline", [])

    if not timeline:
        fig = go.Figure()
        fig.add_annotation(
            text="タイムラインデータがありません",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20)
        )
        return fig

    # Prepare data
    dates = []
    episode_names = []
    categories = []
    colors = []
    hover_texts = []

    for ep in timeline:
        date_str = ep.get("date")
        if date_str:
            # Handle nanosecond precision by truncating to microseconds
            date_str_cleaned = date_str.replace("Z", "+00:00")
            if "." in date_str_cleaned and "+" in date_str_cleaned:
                # Split at decimal and timezone
                parts = date_str_cleaned.split(".")
                if len(parts) == 2:
                    fractional_and_tz = parts[1].split("+")
                    # Keep only first 6 digits (microseconds) of fractional part
                    microseconds = fractional_and_tz[0][:6]
                    date_str_cleaned = f"{parts[0]}.{microseconds}+{fractional_and_tz[1]}"
            date = datetime.fromisoformat(date_str_cleaned)
            dates.append(date)
            episode_names.append(ep.get("episode_name", "Unknown"))
            category = ep.get("cause_category", "unknown")
            categories.append(category)
            colors.append(CATEGORY_COLORS.get(category, "#CCCCCC"))

            # Build hover text
            chains = ep.get("causality_chains", [])
            chain_summary = f"{len(chains)} causality relationships"
            components = ep.get("components", [])
            comp_summary = ", ".join(components[:3])
            if len(components) > 3:
                comp_summary += f" +{len(components)-3} more"

            hover_text = f"<b>{ep['episode_name']}</b><br>"
            hover_text += f"Date: {date.strftime('%Y-%m-%d %H:%M')}<br>"
            hover_text += f"Category: {category}<br>"
            hover_text += f"Components: {comp_summary}<br>"
            hover_text += f"Causality: {chain_summary}"
            hover_texts.append(hover_text)

    # Create timeline chart
    fig = go.Figure()

    # Add scatter plot for episodes
    fig.add_trace(go.Scatter(
        x=dates,
        y=[1] * len(dates),  # All on same level
        mode='markers+text',
        marker=dict(
            size=20,
            color=colors,
            line=dict(width=2, color='white'),
            symbol='circle'
        ),
        text=[name[:30] + "..." if len(name) > 30 else name for name in episode_names],
        textposition="top center",
        textfont=dict(size=10),
        hovertext=hover_texts,
        hoverinfo="text",
        showlegend=False
    ))

    fig.update_layout(
        title=dict(
            text="<b>障害発生タイムライン</b><br><sub>時系列での障害発生パターン</sub>",
            font=dict(size=18)
        ),
        xaxis=dict(
            title="時間",
            showgrid=True,
            gridcolor='lightgray',
            type='date'
        ),
        yaxis=dict(
            showticklabels=False,
            showgrid=False,
            range=[0.5, 1.5]
        ),
        height=300,
        margin=dict(l=50, r=50, t=80, b=50),
        paper_bgcolor='white',
        plot_bgcolor='#F8F9FA',
        hovermode='closest'
    )

    return fig


def create_component_history_chart(timeline_data: dict) -> go.Figure:
    """Create component history stacked bar chart."""
    component_history = timeline_data.get("component_history", {})

    if not component_history:
        fig = go.Figure()
        fig.add_annotation(
            text="コンポーネント履歴データがありません",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    # Sort components by occurrence count
    sorted_components = sorted(
        component_history.items(),
        key=lambda x: x[1]["occurrences"],
        reverse=True
    )[:10]  # Top 10

    # Group by component and cause category
    component_names = []
    category_counts = {}

    for comp_name, comp_data in sorted_components:
        component_names.append(comp_name[:30])  # Truncate long names

        # Count by category
        for incident in comp_data.get("incidents", []):
            category = incident.get("cause_category", "unknown")
            if category not in category_counts:
                category_counts[category] = []

            # Pad with zeros
            while len(category_counts[category]) < len(component_names) - 1:
                category_counts[category].append(0)

            # Add count for this component
            if len(category_counts[category]) < len(component_names):
                category_counts[category].append(1)
            else:
                category_counts[category][-1] += 1

    # Pad all categories to same length
    for category in category_counts:
        while len(category_counts[category]) < len(component_names):
            category_counts[category].append(0)

    # Create stacked bar chart
    fig = go.Figure()

    for category, counts in category_counts.items():
        fig.add_trace(go.Bar(
            name=category.replace("reason/", ""),
            x=component_names,
            y=counts,
            marker_color=CATEGORY_COLORS.get(category, "#CCCCCC"),
            hovertemplate="<b>%{x}</b><br>%{y} incidents<extra></extra>"
        ))

    fig.update_layout(
        title=dict(
            text="<b>コンポーネント別障害履歴</b><br><sub>各コンポーネントの障害発生回数</sub>",
            font=dict(size=16)
        ),
        xaxis_title="コンポーネント",
        yaxis_title="障害回数",
        barmode='stack',
        height=400,
        margin=dict(l=50, r=50, t=80, b=100),
        paper_bgcolor='white',
        plot_bgcolor='#F8F9FA',
        legend=dict(
            title="原因カテゴリ",
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02
        ),
        xaxis=dict(tickangle=-45)
    )

    return fig


def create_similarity_heatmap(similarity_data: dict) -> go.Figure:
    """Create similarity matrix heatmap."""
    episode_names = similarity_data.get("episode_names", [])
    matrix = similarity_data.get("matrix", [])
    patterns = similarity_data.get("patterns", [])

    if not episode_names or not matrix:
        fig = go.Figure()
        fig.add_annotation(
            text="類似度データがありません",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    # Truncate episode names for display
    display_names = [name[:40] + "..." if len(name) > 40 else name for name in episode_names]

    # Create hover text with LLM analysis
    hover_texts = []
    for i, row in enumerate(matrix):
        hover_row = []
        for j, sim_value in enumerate(row):
            if i == j:
                hover_text = f"<b>{display_names[i]}</b><br>Self-similarity: 1.0"
            elif sim_value > 0:
                # Find pattern for this pair
                pattern_info = None
                for pattern in patterns:
                    eps = pattern.get("similar_episodes", [])
                    if len(eps) >= 2:
                        # Check if this matches the current pair
                        names_in_pattern = [ep.get("name", "") for ep in eps]
                        if episode_names[i] in names_in_pattern and episode_names[j] in names_in_pattern:
                            pattern_info = pattern
                            break

                hover_text = f"<b>{display_names[i]}</b><br>↔<br><b>{display_names[j]}</b><br><br>"
                hover_text += f"Embedding Similarity: {sim_value:.3f}<br>"

                if pattern_info:
                    hover_text += f"LLM Similarity: {pattern_info.get('llm_similarity_score', 0.0):.3f}<br>"
                    hover_text += f"Common Pattern:<br>{pattern_info.get('common_pattern', 'N/A')[:100]}"
            else:
                hover_text = f"{display_names[i]} ↔ {display_names[j]}<br>No similarity detected"

            hover_row.append(hover_text)
        hover_texts.append(hover_row)

    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=display_names,
        y=display_names,
        colorscale='YlOrRd',
        text=hover_texts,
        hoverinfo='text',
        colorbar=dict(title="類似度")
    ))

    fig.update_layout(
        title=dict(
            text="<b>エピソード類似度マトリクス</b><br><sub>Embedding類似度のヒートマップ（ホバーでLLM分析を表示）</sub>",
            font=dict(size=16)
        ),
        xaxis=dict(
            tickangle=-45,
            side='bottom'
        ),
        yaxis=dict(
            tickangle=0
        ),
        height=600,
        margin=dict(l=250, r=50, t=100, b=200),
        paper_bgcolor='white',
    )

    return fig


def create_recurrence_network(advanced_patterns: dict, timeline_data: dict) -> go.Figure:
    """Create recurrence pattern network graph."""
    patterns = advanced_patterns.get("recurring_patterns", [])
    timeline = timeline_data.get("timeline", [])

    if not patterns:
        fig = go.Figure()
        fig.add_annotation(
            text="再発パターンが検出されませんでした",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    # Build nodes and edges
    nodes = {}  # uuid -> {name, category, x, y}
    edges = []  # [{source, target, similarity}]

    # Add all episodes as nodes
    for i, ep in enumerate(timeline):
        uuid = ep.get("episode_uuid")
        nodes[uuid] = {
            "name": ep.get("episode_name", "Unknown"),
            "category": ep.get("cause_category", "unknown"),
            "index": i
        }

    # Add edges from patterns
    for pattern in patterns:
        similar_eps = pattern.get("similar_episodes", [])
        if len(similar_eps) >= 2:
            ep1_uuid = similar_eps[0]["uuid"]
            ep2_uuid = similar_eps[1]["uuid"]
            similarity = pattern.get("embedding_similarity", 0.0)

            if ep1_uuid in nodes and ep2_uuid in nodes:
                edges.append({
                    "source": ep1_uuid,
                    "target": ep2_uuid,
                    "similarity": similarity,
                    "llm_score": pattern.get("llm_similarity_score", 0.0),
                    "common_pattern": pattern.get("common_pattern", ""),
                })

    # Calculate positions (simple circular layout)
    import math
    n = len(nodes)
    node_list = list(nodes.items())

    for i, (uuid, node_data) in enumerate(node_list):
        angle = 2 * math.pi * i / n
        node_data["x"] = math.cos(angle)
        node_data["y"] = math.sin(angle)

    # Create edge traces
    edge_traces = []
    for edge in edges:
        source_node = nodes[edge["source"]]
        target_node = nodes[edge["target"]]

        # Edge line
        edge_trace = go.Scatter(
            x=[source_node["x"], target_node["x"], None],
            y=[source_node["y"], target_node["y"], None],
            mode='lines',
            line=dict(
                width=edge["similarity"] * 10,  # Width based on similarity
                color='rgba(125, 125, 125, 0.5)'
            ),
            hoverinfo='text',
            text=f"Embedding: {edge['similarity']:.3f}<br>LLM: {edge['llm_score']:.3f}<br>{edge['common_pattern'][:80]}",
            showlegend=False
        )
        edge_traces.append(edge_trace)

    # Create node trace
    node_x = [node_data["x"] for node_data in nodes.values()]
    node_y = [node_data["y"] for node_data in nodes.values()]
    node_colors = [CATEGORY_COLORS.get(node_data["category"], "#CCCCCC") for node_data in nodes.values()]
    node_texts = [node_data["name"][:30] for node_data in nodes.values()]

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode='markers+text',
        marker=dict(
            size=30,
            color=node_colors,
            line=dict(width=2, color='white')
        ),
        text=node_texts,
        textposition="top center",
        textfont=dict(size=9),
        hoverinfo='text',
        hovertext=[f"<b>{node_data['name']}</b><br>Category: {node_data['category']}" for node_data in nodes.values()],
        showlegend=False
    )

    # Create figure
    fig = go.Figure(data=edge_traces + [node_trace])

    fig.update_layout(
        title=dict(
            text="<b>再発パターンネットワーク</b><br><sub>類似するエピソード間の関係（エッジの太さ=類似度）</sub>",
            font=dict(size=16)
        ),
        showlegend=False,
        hovermode='closest',
        height=600,
        margin=dict(l=50, r=50, t=100, b=50),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        paper_bgcolor='white',
        plot_bgcolor='#F8F9FA'
    )

    return fig


def create_llm_results_table(advanced_patterns: dict) -> go.Figure:
    """Create LLM judgment results table."""
    patterns = advanced_patterns.get("recurring_patterns", [])

    if not patterns:
        fig = go.Figure()
        fig.add_annotation(
            text="LLM判定結果がありません",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    # Prepare table data
    episode1_names = []
    episode2_names = []
    embedding_sims = []
    llm_sims = []
    common_patterns = []
    llm_analyses = []

    for pattern in patterns:
        similar_eps = pattern.get("similar_episodes", [])
        if len(similar_eps) >= 2:
            episode1_names.append(similar_eps[0]["name"][:40])
            episode2_names.append(similar_eps[1]["name"][:40])
            embedding_sims.append(f"{pattern.get('embedding_similarity', 0.0):.3f}")
            llm_sims.append(f"{pattern.get('llm_similarity_score', 0.0):.3f}")
            common_patterns.append(pattern.get('common_pattern', 'N/A')[:60])
            llm_analyses.append(pattern.get('llm_analysis', 'N/A')[:80])

    # Create table
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=['<b>Episode 1</b>', '<b>Episode 2</b>', '<b>Embed Sim</b>',
                    '<b>LLM Sim</b>', '<b>Common Pattern</b>', '<b>LLM Analysis</b>'],
            fill_color='#4ECDC4',
            align='left',
            font=dict(color='white', size=12)
        ),
        cells=dict(
            values=[episode1_names, episode2_names, embedding_sims,
                    llm_sims, common_patterns, llm_analyses],
            fill_color='white',
            align='left',
            font=dict(size=11),
            height=30
        )
    )])

    fig.update_layout(
        title=dict(
            text="<b>LLM判定結果詳細</b><br><sub>類似パターンのLLM分析結果</sub>",
            font=dict(size=16)
        ),
        height=400,
        margin=dict(l=20, r=20, t=80, b=20),
        paper_bgcolor='white',
    )

    return fig


def create_category_timeline(timeline_data: dict) -> go.Figure:
    """Create stacked area chart showing cause category distribution over time."""
    episodes = timeline_data.get("timeline", [])

    # Prepare time-series data by category
    category_counts: dict[str, dict] = {}
    for episode in episodes:
        date = episode.get("date", "Unknown")
        category = episode.get("cause_category", "unknown")

        if date not in category_counts:
            category_counts[date] = {}

        category_counts[date][category] = category_counts[date].get(category, 0) + 1

    # Sort dates chronologically
    sorted_dates = sorted(category_counts.keys())

    # Get all unique categories
    all_categories = set()
    for counts in category_counts.values():
        all_categories.update(counts.keys())

    # Create traces for each category
    fig = go.Figure()

    for category in sorted(all_categories):
        counts = [category_counts[date].get(category, 0) for date in sorted_dates]
        color = CATEGORY_COLORS.get(category, CATEGORY_COLORS["unknown"])

        fig.add_trace(go.Scatter(
            x=sorted_dates,
            y=counts,
            mode='lines',
            stackgroup='one',
            name=category,
            line=dict(width=0.5, color=color),
            fillcolor=color,
            hovertemplate=f'<b>{category}</b><br>Date: %{{x}}<br>Count: %{{y}}<extra></extra>'
        ))

    fig.update_layout(
        title="Cause Category Distribution Over Time",
        xaxis=dict(title="Date", tickangle=-45),
        yaxis=dict(title="Number of Incidents"),
        hovermode='x unified',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400,
        margin=dict(l=50, r=50, t=80, b=80)
    )

    return fig


def create_causality_sankey(timeline_data: dict) -> go.Figure:
    """Create Sankey diagram showing causality flow: Causes → Components → Impacts."""
    episodes = timeline_data.get("timeline", [])

    # Build node and link data
    nodes_set = set()
    links = []

    for episode in episodes:
        category = episode.get("cause_category", "unknown")
        chains = episode.get("causality_chains", [])  # Fixed: was "causality_chain"

        if not chains:
            continue

        # Add category as source node
        nodes_set.add(f"cause:{category}")

        # Process causality chain
        for chain_item in chains:
            # Extract entities from the chain structure
            from_entity = chain_item.get("from_entity", "Unknown")
            to_entity = chain_item.get("to_entity", "Unknown")

            # Add component nodes
            nodes_set.add(f"component:{from_entity}")
            nodes_set.add(f"component:{to_entity}")

            # Create links: cause -> from_entity -> to_entity
            links.append((f"cause:{category}", f"component:{from_entity}"))
            links.append((f"component:{from_entity}", f"component:{to_entity}"))

    # Convert to indexed lists
    nodes_list = sorted(list(nodes_set))
    node_index = {node: i for i, node in enumerate(nodes_list)}

    # Count link occurrences
    link_counts: dict[tuple, int] = {}
    for link in links:
        link_counts[link] = link_counts.get(link, 0) + 1

    # Prepare Sankey data
    source_indices = []
    target_indices = []
    values = []

    for (src, tgt), count in link_counts.items():
        source_indices.append(node_index[src])
        target_indices.append(node_index[tgt])
        values.append(count)

    # Assign colors to nodes
    node_colors = []
    for node in nodes_list:
        if node.startswith("cause:"):
            category = node.replace("cause:", "")
            node_colors.append(CATEGORY_COLORS.get(category, CATEGORY_COLORS["unknown"]))
        elif node.startswith("component:"):
            node_colors.append("#95A5A6")  # Gray for components
        elif node.startswith("impact:"):
            node_colors.append("#E74C3C")  # Red for impacts
        else:
            node_colors.append("#BDC3C7")  # Light gray default

    # Format node labels (remove prefixes)
    node_labels = [node.split(":", 1)[1] if ":" in node else node for node in nodes_list]

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="white", width=0.5),
            label=node_labels,
            color=node_colors,
        ),
        link=dict(
            source=source_indices,
            target=target_indices,
            value=values,
            color="rgba(200, 200, 200, 0.4)"
        )
    )])

    fig.update_layout(
        title="Causality Flow: Causes → Components → Impacts",
        font=dict(size=12),
        height=600,
        margin=dict(l=20, r=20, t=60, b=20)
    )

    return fig


def main():
    """Main function to generate visualizations."""
    print("=" * 80)
    print("時系列因果関係追跡 & 再発障害検出 可視化")
    print("=" * 80)
    print()

    # Step 1: Fetch data
    print("Step 1: APIからデータ取得中...")
    try:
        timeline_data = fetch_timeline_data()
        basic_patterns = fetch_recurring_patterns_basic()
        advanced_patterns = fetch_recurring_patterns_advanced()
        similarity_data = calculate_similarity_matrix(timeline_data, advanced_patterns)
        print("✅ データ取得完了\n")
    except Exception as e:
        print(f"❌ エラー: {e}")
        print("APIサーバーが起動していることを確認してください")
        return

    # Step 2: Create visualizations
    print("Step 2: 可視化作成中...")

    # Create all individual charts
    print("  - サマリーカード作成中...")
    summary_fig = create_summary_cards(timeline_data, advanced_patterns)

    print("  - タイムラインチャート作成中...")
    timeline_fig = create_timeline_chart(timeline_data)

    print("  - コンポーネント履歴チャート作成中...")
    component_fig = create_component_history_chart(timeline_data)

    print("  - カテゴリタイムラインチャート作成中...")
    category_fig = create_category_timeline(timeline_data)

    print("  - 類似度ヒートマップ作成中...")
    heatmap_fig = create_similarity_heatmap(similarity_data)

    print("  - 再発ネットワークグラフ作成中...")
    network_fig = create_recurrence_network(advanced_patterns, timeline_data)

    print("  - LLM判定結果テーブル作成中...")
    llm_table_fig = create_llm_results_table(advanced_patterns)

    print("  - 因果関係Sankeyダイアグラム作成中...")
    sankey_fig = create_causality_sankey(timeline_data)

    print("✅ 全チャート作成完了\n")

    # Step 3: Integrate into unified dashboard
    print("Step 3: ダッシュボード統合中...")

    from plotly.subplots import make_subplots

    # Create dashboard with subplots
    # Layout: 9 charts arranged in a vertical layout
    dashboard = make_subplots(
        rows=9,
        cols=1,
        row_heights=[0.08, 0.12, 0.12, 0.10, 0.15, 0.15, 0.12, 0.08, 0.08],
        subplot_titles=(
            "📊 Summary Indicators",
            "⏱️ Incident Timeline",
            "🔧 Component History",
            "📈 Category Distribution Over Time",
            "🔥 Similarity Heatmap (Embedding-based)",
            "🔗 Recurrence Network",
            "🤖 LLM Judgment Results",
            "🌊 Causality Flow (Sankey)",
            ""
        ),
        specs=[
            [{"type": "indicator"}],  # Summary cards
            [{"type": "scatter"}],    # Timeline
            [{"type": "bar"}],        # Component history
            [{"type": "scatter"}],    # Category timeline
            [{"type": "heatmap"}],    # Similarity heatmap
            [{"type": "scatter"}],    # Recurrence network
            [{"type": "table"}],      # LLM table
            [{"type": "sankey"}],     # Sankey
            [{"type": "scatter"}]     # Placeholder for future
        ],
        vertical_spacing=0.03
    )

    # Add traces from each chart to the dashboard
    # Note: For figures with multiple traces, we need to add each trace individually

    # Row 1: Summary cards (indicators)
    for trace in summary_fig.data:
        dashboard.add_trace(trace, row=1, col=1)

    # Row 2: Timeline
    for trace in timeline_fig.data:
        dashboard.add_trace(trace, row=2, col=1)

    # Row 3: Component history
    for trace in component_fig.data:
        dashboard.add_trace(trace, row=3, col=1)

    # Row 4: Category timeline
    for trace in category_fig.data:
        dashboard.add_trace(trace, row=4, col=1)

    # Row 5: Similarity heatmap
    for trace in heatmap_fig.data:
        dashboard.add_trace(trace, row=5, col=1)

    # Row 6: Recurrence network
    for trace in network_fig.data:
        dashboard.add_trace(trace, row=6, col=1)

    # Row 7: LLM table
    for trace in llm_table_fig.data:
        dashboard.add_trace(trace, row=7, col=1)

    # Row 8: Sankey
    for trace in sankey_fig.data:
        dashboard.add_trace(trace, row=8, col=1)

    # Update layout
    dashboard.update_layout(
        title={
            'text': "時系列因果関係追跡 & 再発障害検出ダッシュボード<br><sub>Temporal Causality Tracking & Recurrence Detection Dashboard</sub>",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 24}
        },
        showlegend=True,
        height=4000,  # Total height for all charts
        margin=dict(l=50, r=50, t=120, b=50),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(size=11)
    )

    # Update x-axes and y-axes for specific subplots
    dashboard.update_xaxes(title_text="Date", row=2, col=1, tickangle=-45)
    dashboard.update_yaxes(title_text="Episodes", row=2, col=1)

    dashboard.update_xaxes(title_text="Component", row=3, col=1, tickangle=-45)
    dashboard.update_yaxes(title_text="Count", row=3, col=1)

    dashboard.update_xaxes(title_text="Date", row=4, col=1, tickangle=-45)
    dashboard.update_yaxes(title_text="Count", row=4, col=1)

    print("✅ ダッシュボード統合完了\n")

    # Step 4: Save to HTML
    output_file = "temporal_recurrence_dashboard.html"
    print(f"Step 4: ファイル保存中: {output_file}")

    dashboard.write_html(output_file, include_plotlyjs="cdn")
    print(f"✅ ファイル保存完了: {output_file}\n")

    # Print summary
    print("=" * 80)
    print("📊 分析結果サマリー")
    print("=" * 80)
    print(f"総エピソード数: {timeline_data.get('total_episodes', 0)}")
    print(f"再発パターン検出数: {advanced_patterns.get('total_patterns', 0)}")
    print(f"コンポーネント数: {len(timeline_data.get('component_history', {}))}")
    print(f"\n✨ 全9チャートを含むダッシュボードが生成されました: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
