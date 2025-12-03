#!/usr/bin/env python3
"""
Visualize Incident Progression Analysis (CVR-style).

This analysis applies marketing conversion rate (CVR) concepts to incident management,
providing insights into how incidents escalate and propagate through systems.

Terminology Mapping (CVR → SRE):
- Conversion Rate → Escalation Rate
- Funnel Analysis → Incident Progression Analysis
- Drop-off Rate → Containment Rate
- Purchase → SLO Violation
- Action → Severe Incident
- Awareness → Incident Detection
- Lead Quality → Component Risk Score
- Conversion Funnel → Impact Propagation Flow
- Customer Journey → Incident Lifecycle
- Touchpoint → Component Involvement
- Engagement Rate → Impact Rate
"""

import json
from pathlib import Path
import urllib.request
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from collections import defaultdict

# API base URL
import os
if os.path.exists("/.dockerenv"):
    API_BASE = "http://host.docker.internal:30547"
else:
    API_BASE = "http://localhost:30547"


def fetch_api_data(endpoint: str) -> dict:
    """Fetch data from Graphiti API endpoint."""
    url = f"{API_BASE}{endpoint}"
    print(f"Fetching data from: {url}")

    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
        return data
    except Exception as e:
        print(f"❌ Error fetching {endpoint}: {e}")
        return {}


def create_component_impact_chart(data: dict) -> go.Figure:
    """Create Chart 1: Component Impact Distribution by Cause Category.

    Shows which components are affected by each cause category.
    Stacked bar chart with contribution rates.

    SRE Term: Component Impact Distribution
    CVR Term: Market Share by Category
    """
    analysis_results = data.get("analysis_results", [])

    if not analysis_results:
        fig = go.Figure()
        fig.add_annotation(
            text="コンポーネント影響データがありません",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    # Organize data by cause category
    categories = {}
    for result in analysis_results:
        category = result["cause_category"]
        if category not in categories:
            categories[category] = []
        categories[category].append(result)

    # Create stacked bar chart
    fig = go.Figure()

    # Get unique components across all categories
    all_components = set()
    for results in categories.values():
        for result in results:
            all_components.add(result["component"])

    # Create color palette for components
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
              '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B739', '#52BE80',
              '#EC7063', '#5DADE2', '#F39C12', '#AF7AC5', '#48C9B0']

    component_colors = {comp: colors[i % len(colors)]
                       for i, comp in enumerate(sorted(all_components))}

    # Add traces for each component
    for component in sorted(all_components):
        x_categories = []
        y_values = []
        hover_texts = []

        for category in sorted(categories.keys()):
            # Find this component in this category
            comp_data = next((r for r in categories[category]
                            if r["component"] == component), None)

            if comp_data:
                x_categories.append(category.replace("reason/", ""))
                y_values.append(comp_data["contribution_rate"])
                hover_texts.append(
                    f"<b>{component}</b><br>"
                    f"Category: {category}<br>"
                    f"Contribution Rate: {comp_data['contribution_rate']:.1%}<br>"
                    f"Severity Weighted: {comp_data['severity_weighted_rate']:.3f}<br>"
                    f"Incident Count: {comp_data['incident_count']}<br>"
                    f"Severe: {comp_data['severe_incident_count']}"
                )
            else:
                x_categories.append(category.replace("reason/", ""))
                y_values.append(0)
                hover_texts.append("")

        fig.add_trace(go.Bar(
            name=component,
            x=x_categories,
            y=y_values,
            marker_color=component_colors[component],
            hovertext=hover_texts,
            hoverinfo='text',
            text=[f"{v:.0%}" if v > 0 else "" for v in y_values],
            textposition='inside'
        ))

    fig.update_layout(
        title=dict(
            text="Component Impact Distribution by Cause Category<br>"
                 "<sub>コンポーネント影響分布（原因カテゴリ別）- CVR: Contribution Rate</sub>",
            font=dict(size=16)
        ),
        xaxis_title="Cause Category (原因カテゴリ)",
        yaxis_title="Contribution Rate (貢献率)",
        barmode='stack',
        height=400,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            font=dict(size=10)
        ),
        margin=dict(l=50, r=200, t=80, b=50),
        paper_bgcolor='white',
        plot_bgcolor='rgba(240,240,240,0.5)',
    )

    return fig


def create_severity_escalation_chart(data: dict) -> go.Figure:
    """Create Chart 2: Component Severity Escalation Rate.

    Shows which components have high escalation rates from involvement to severe incidents.
    Horizontal bar chart sorted by escalation rate.

    SRE Term: Escalation Rate
    CVR Term: Conversion Rate (Action → Purchase)
    """
    analysis_results = data.get("analysis_results", [])

    if not analysis_results:
        fig = go.Figure()
        fig.add_annotation(
            text="重大度エスカレーションデータがありません",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    # Sort by severity_conversion_rate descending
    sorted_results = sorted(analysis_results,
                           key=lambda x: x["severity_conversion_rate"],
                           reverse=True)

    # Take top 15 components
    top_results = sorted_results[:15]

    components = [r["component"] for r in top_results]
    rates = [r["severity_conversion_rate"] for r in top_results]

    # Color based on rate (green → yellow → red)
    colors = []
    for rate in rates:
        if rate <= 0.3:
            colors.append('#52BE80')  # Green (low risk)
        elif rate <= 0.7:
            colors.append('#F39C12')  # Yellow (medium risk)
        else:
            colors.append('#E74C3C')  # Red (high risk)

    # Hover text
    hover_texts = [
        f"<b>{r['component']}</b><br>"
        f"Escalation Rate: {r['severity_conversion_rate']:.1%}<br>"
        f"Total Incidents: {r['total_incidents']}<br>"
        f"Severe Incidents: {r['severe_incidents']}<br>"
        f"Non-Severe: {r['non_severe_incidents']}<br>"
        f"Samples: {', '.join(r['sample_severe_episodes'][:2])}"
        for r in top_results
    ]

    fig = go.Figure(data=[
        go.Bar(
            x=rates,
            y=components,
            orientation='h',
            marker=dict(color=colors),
            text=[f"{r:.1%}" for r in rates],
            textposition='auto',
            hovertext=hover_texts,
            hoverinfo='text'
        )
    ])

    fig.update_layout(
        title=dict(
            text="Component Severity Escalation Rate<br>"
                 "<sub>コンポーネント別重大度エスカレーション率 - CVR: Conversion Rate</sub>",
            font=dict(size=16)
        ),
        xaxis=dict(
            title="Escalation Rate (エスカレーション率)",
            tickformat='.0%',
            range=[0, 1.0]
        ),
        yaxis=dict(
            title="Component (コンポーネント)"
        ),
        height=500,
        margin=dict(l=200, r=50, t=80, b=50),
        paper_bgcolor='white',
        plot_bgcolor='rgba(240,240,240,0.5)',
    )

    # Add reference lines
    fig.add_vline(x=0.3, line_dash="dash", line_color="green",
                  annotation_text="Low Risk Threshold", annotation_position="top")
    fig.add_vline(x=0.7, line_dash="dash", line_color="orange",
                  annotation_text="High Risk Threshold", annotation_position="top")

    return fig


def create_progression_flow_sankey(data: dict) -> go.Figure:
    """Create Chart 3: Incident Progression Flow (Sankey Diagram).

    Shows the flow from cause categories → components → impact levels.

    SRE Term: Impact Propagation Flow
    CVR Term: Multi-channel Conversion Funnel
    """
    flow_metrics = data.get("flow_metrics", [])

    if not flow_metrics:
        fig = go.Figure()
        fig.add_annotation(
            text="フローデータがありません",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    # Build nodes and links
    node_labels = []
    node_colors = []
    node_index = {}

    # Color palette for cause categories
    cause_colors = {
        "reason/canary": "rgba(255,107,107,0.8)",
        "reason/config": "rgba(78,205,196,0.8)",
        "reason/capacity": "rgba(69,183,209,0.8)",
        "reason/thirdparty": "rgba(255,160,122,0.8)",
        "reason/maintenance": "rgba(152,216,200,0.8)",
    }

    # Layer 1: Cause categories
    cause_categories = sorted(set(f["cause_category"] for f in flow_metrics))
    for category in cause_categories:
        node_index[f"cause:{category}"] = len(node_labels)
        node_labels.append(category.replace("reason/", ""))
        node_colors.append(cause_colors.get(category, "rgba(200,200,200,0.8)"))

    # Layer 2: Components
    components = sorted(set(f["component"] for f in flow_metrics))
    for component in components:
        node_index[f"comp:{component}"] = len(node_labels)
        node_labels.append(component)
        node_colors.append("rgba(150,150,150,0.6)")

    # Layer 3: Impact levels
    impact_labels = ["Severe Incident", "SLO Violation"]
    for impact in impact_labels:
        node_index[f"impact:{impact}"] = len(node_labels)
        node_labels.append(impact)
        node_colors.append("rgba(231,76,60,0.7)")

    # Build links
    link_sources = []
    link_targets = []
    link_values = []
    link_colors = []
    link_labels = []

    # Links: Cause → Component
    for flow in flow_metrics:
        category = flow["cause_category"]
        component = flow["component"]
        total_flows = flow["total_flows"]

        source_idx = node_index[f"cause:{category}"]
        target_idx = node_index[f"comp:{component}"]

        link_sources.append(source_idx)
        link_targets.append(target_idx)
        link_values.append(total_flows)
        link_colors.append(cause_colors.get(category, "rgba(200,200,200,0.4)"))
        link_labels.append(
            f"{category} → {component}<br>"
            f"Total Flows: {total_flows}<br>"
            f"Severe: {flow['severe_flows']}<br>"
            f"SLO Violations: {flow['slo_violation_flows']}"
        )

    # Links: Component → Severe Incident (if severe_flows > 0)
    for flow in flow_metrics:
        component = flow["component"]
        severe_flows = flow["severe_flows"]

        if severe_flows > 0:
            source_idx = node_index[f"comp:{component}"]
            target_idx = node_index["impact:Severe Incident"]

            link_sources.append(source_idx)
            link_targets.append(target_idx)
            link_values.append(severe_flows)
            link_colors.append("rgba(231,76,60,0.3)")
            link_labels.append(
                f"{component} → Severe<br>"
                f"Count: {severe_flows}<br>"
                f"Rate: {flow['component_to_severe_rate']:.1%}"
            )

    # Links: Component → SLO Violation (if slo_violation_flows > 0)
    for flow in flow_metrics:
        component = flow["component"]
        slo_flows = flow["slo_violation_flows"]

        if slo_flows > 0:
            source_idx = node_index[f"comp:{component}"]
            target_idx = node_index["impact:SLO Violation"]

            link_sources.append(source_idx)
            link_targets.append(target_idx)
            link_values.append(slo_flows)
            link_colors.append("rgba(192,57,43,0.5)")
            link_labels.append(
                f"{component} → SLO Violation<br>"
                f"Count: {slo_flows}<br>"
                f"End-to-End CVR: {flow['end_to_end_cvr']:.1%}"
            )

    # Create Sankey diagram
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="white", width=0.5),
            label=node_labels,
            color=node_colors
        ),
        link=dict(
            source=link_sources,
            target=link_targets,
            value=link_values,
            color=link_colors,
            customdata=link_labels,
            hovertemplate='%{customdata}<extra></extra>'
        )
    )])

    fig.update_layout(
        title=dict(
            text="Incident Progression Flow: Cause → Component → Impact<br>"
                 "<sub>障害進行フロー - CVR: Conversion Funnel</sub>",
            font=dict(size=16)
        ),
        height=600,
        margin=dict(l=50, r=50, t=80, b=50),
        paper_bgcolor='white',
    )

    return fig


def create_risk_assessment_matrix(impact_data: dict, severity_data: dict, flow_data: dict) -> go.Figure:
    """Create Chart 4: Component Risk Assessment Matrix.

    Combines 3 metrics into a heatmap:
    1. Impact Frequency (from impact_data)
    2. Escalation Rate (from severity_data)
    3. End-to-End Risk (from flow_data)

    SRE Term: Risk Assessment Matrix
    CVR Term: Customer Segment Performance Matrix
    """
    # Extract component data from all sources
    component_metrics = {}

    # From impact_data: Impact Frequency
    impact_results = impact_data.get("analysis_results", [])
    for result in impact_results:
        comp = result["component"]
        if comp not in component_metrics:
            component_metrics[comp] = {"impact_freq": 0, "escalation_rate": 0, "end_to_end_risk": 0}
        component_metrics[comp]["impact_freq"] = result["severity_weighted_rate"]

    # From severity_data: Escalation Rate
    severity_results = severity_data.get("analysis_results", [])
    for result in severity_results:
        comp = result["component"]
        if comp not in component_metrics:
            component_metrics[comp] = {"impact_freq": 0, "escalation_rate": 0, "end_to_end_risk": 0}
        component_metrics[comp]["escalation_rate"] = result["severity_conversion_rate"]

    # From flow_data: End-to-End Risk (average end_to_end_cvr for this component)
    flow_metrics = flow_data.get("flow_metrics", [])
    component_flow_cvrs = defaultdict(list)
    for flow in flow_metrics:
        comp = flow["component"]
        component_flow_cvrs[comp].append(flow["end_to_end_cvr"])

    for comp, cvrs in component_flow_cvrs.items():
        if comp not in component_metrics:
            component_metrics[comp] = {"impact_freq": 0, "escalation_rate": 0, "end_to_end_risk": 0}
        component_metrics[comp]["end_to_end_risk"] = sum(cvrs) / len(cvrs) if cvrs else 0

    if not component_metrics:
        fig = go.Figure()
        fig.add_annotation(
            text="リスク評価データがありません",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    # Build matrix
    components = sorted(component_metrics.keys(),
                       key=lambda c: sum(component_metrics[c].values()),
                       reverse=True)[:15]  # Top 15

    metric_labels = [
        "Impact Frequency\n(影響頻度)",
        "Escalation Rate\n(エスカレーション率)",
        "End-to-End Risk\n(総合リスク)"
    ]

    matrix = []
    hover_texts = []

    for comp in components:
        metrics = component_metrics[comp]
        row = [
            metrics["impact_freq"],
            metrics["escalation_rate"],
            metrics["end_to_end_risk"]
        ]
        matrix.append(row)

        hover_row = [
            f"<b>{comp}</b><br>Impact Frequency: {metrics['impact_freq']:.3f}",
            f"<b>{comp}</b><br>Escalation Rate: {metrics['escalation_rate']:.1%}",
            f"<b>{comp}</b><br>End-to-End Risk: {metrics['end_to_end_risk']:.1%}"
        ]
        hover_texts.append(hover_row)

    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=metric_labels,
        y=components,
        colorscale='RdYlGn_r',  # Red = High Risk, Green = Low Risk
        text=hover_texts,
        hoverinfo='text',
        colorbar=dict(title="Risk Score<br>(リスクスコア)")
    ))

    fig.update_layout(
        title=dict(
            text="Component Risk Assessment Matrix<br>"
                 "<sub>コンポーネントリスク評価マトリクス - 3つのメトリクスの統合</sub>",
            font=dict(size=16)
        ),
        xaxis_title="Risk Metrics (リスクメトリクス)",
        yaxis_title="Component (コンポーネント)",
        height=500,
        margin=dict(l=200, r=100, t=80, b=100),
        paper_bgcolor='white',
    )

    return fig


def create_overall_funnel_chart(data: dict) -> go.Figure:
    """Create Chart 5: Overall Incident Progression Funnel.

    Aggregated funnel showing progression from detection to SLO violation.

    SRE Term: Incident Progression Summary
    CVR Term: Conversion Funnel (Awareness → Purchase)
    """
    flow_metrics = data.get("flow_metrics", [])

    if not flow_metrics:
        fig = go.Figure()
        fig.add_annotation(
            text="ファネルデータがありません",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        return fig

    # Aggregate statistics
    total_flows = sum(f["total_flows"] for f in flow_metrics)
    total_severe = sum(f["severe_flows"] for f in flow_metrics)
    total_slo = sum(f["slo_violation_flows"] for f in flow_metrics)

    # Calculate stage values
    stage1_value = len(set(f["cause_category"] for f in flow_metrics))  # Unique causes detected
    stage2_value = total_flows  # Total component involvements
    stage3_value = total_severe  # Severe incidents
    stage4_value = total_slo  # SLO violations

    # Calculate conversion rates
    cvr_1_to_2 = stage2_value / stage1_value if stage1_value > 0 else 0
    cvr_2_to_3 = stage3_value / stage2_value if stage2_value > 0 else 0
    cvr_3_to_4 = stage4_value / stage3_value if stage3_value > 0 else 0

    # Funnel stages
    stages = [
        "Incident Detection<br>(障害検知)",
        "Component Involvement<br>(コンポーネント関与)",
        "Severe Incidents<br>(重大障害)",
        "SLO Violations<br>(SLO違反)"
    ]

    values = [stage1_value, stage2_value, stage3_value, stage4_value]

    # Text labels with conversion rates
    text_labels = [
        f"{stage1_value} causes detected",
        f"{stage2_value} involvements<br>CVR: {cvr_1_to_2:.1f}x",
        f"{stage3_value} escalated<br>CVR: {cvr_2_to_3:.1%}",
        f"{stage4_value} SLO breaches<br>CVR: {cvr_3_to_4:.1%}"
    ]

    fig = go.Figure(go.Funnel(
        y=stages,
        x=values,
        text=text_labels,
        textposition="inside",
        marker=dict(
            color=["#52BE80", "#F39C12", "#E67E22", "#E74C3C"]
        ),
        connector=dict(line=dict(color="gray", width=2))
    ))

    fig.update_layout(
        title=dict(
            text="Overall Incident Progression Funnel (Aggregated)<br>"
                 "<sub>全体の障害進行ファネル（統計サマリー）- CVR: Conversion Funnel</sub>",
            font=dict(size=16)
        ),
        height=500,
        margin=dict(l=150, r=150, t=80, b=50),
        paper_bgcolor='white',
    )

    # Add end-to-end CVR annotation
    end_to_end_cvr = stage4_value / stage1_value if stage1_value > 0 else 0
    fig.add_annotation(
        text=f"End-to-End CVR: {end_to_end_cvr:.1%}<br>(Detection → SLO Violation)",
        xref="paper", yref="paper",
        x=0.5, y=-0.15,
        showarrow=False,
        font=dict(size=14, color="red", weight="bold")
    )

    return fig


def main():
    """Main function to create incident progression dashboard."""
    print("=" * 80)
    print("Incident Progression Analysis (CVR-style) Visualization")
    print("=" * 80)
    print()

    # Fetch data from APIs
    print("Step 1: Fetching data from APIs...")
    try:
        impact_data = fetch_api_data("/graph/analysis/component-impact?min_incidents=1")
        severity_data = fetch_api_data("/graph/analysis/component-severity?min_incidents=1")
        flow_data = fetch_api_data("/graph/analysis/flow-metrics?min_flow_count=1")
        print("✅ Data fetched successfully\n")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Please ensure the API server is running")
        return

    # Create visualizations
    print("Step 2: Creating visualizations...")

    chart1 = create_component_impact_chart(impact_data)
    chart2 = create_severity_escalation_chart(severity_data)
    chart3 = create_progression_flow_sankey(flow_data)
    chart4 = create_risk_assessment_matrix(impact_data, severity_data, flow_data)
    chart5 = create_overall_funnel_chart(flow_data)

    print("✅ All charts created\n")

    # Create dashboard layout
    print("Step 3: Creating integrated dashboard...")

    fig = make_subplots(
        rows=2, cols=3,
        specs=[
            [{"type": "bar"}, {"type": "bar"}, {"type": "sankey"}],
            [{"type": "heatmap", "colspan": 2}, None, {"type": "funnel"}]
        ],
        subplot_titles=(
            "1. Component Impact Distribution by Cause",
            "2. Severity Escalation Rate by Component",
            "3. Incident Progression Flow (Cause → Component → Impact)",
            "4. Component Risk Assessment Matrix",
            "",  # colspan=2
            "5. Overall Incident Progression Funnel"
        ),
        row_heights=[0.5, 0.5],
        column_widths=[0.33, 0.33, 0.34],
        horizontal_spacing=0.08,
        vertical_spacing=0.15
    )

    # Add charts to dashboard
    for trace in chart1.data:
        fig.add_trace(trace, row=1, col=1)

    for trace in chart2.data:
        fig.add_trace(trace, row=1, col=2)

    for trace in chart3.data:
        fig.add_trace(trace, row=1, col=3)

    for trace in chart4.data:
        fig.add_trace(trace, row=2, col=1)

    for trace in chart5.data:
        fig.add_trace(trace, row=2, col=3)

    # Update layout
    fig.update_layout(
        title=dict(
            text="<b>Incident Progression Analysis Dashboard (CVR-style)</b><br>"
                 "<sub>障害進行分析ダッシュボード - マーケティングCVR分析手法を応用</sub>",
            font=dict(size=20),
            x=0.5,
            xanchor='center'
        ),
        height=1200,
        showlegend=True,
        paper_bgcolor='white',
        font=dict(family="Arial, sans-serif", size=11),
    )

    print("✅ Dashboard created\n")

    # Save to HTML
    output_file = "incident_progression_dashboard.html"
    print(f"Step 4: Saving to {output_file}...")
    fig.write_html(output_file, include_plotlyjs="cdn")
    print(f"✅ Saved to: {Path(output_file).absolute()}\n")

    # Print summary
    print("=" * 80)
    print("📊 Analysis Summary")
    print("=" * 80)
    print(f"Component-Category Pairs: {impact_data.get('total_pairs', 0)}")
    print(f"Components Analyzed: {severity_data.get('total_components', 0)}")
    print(f"Flow Paths: {flow_data.get('total_flows', 0)}")
    print(f"Cause Categories: {len(flow_data.get('category_totals', {}))}")
    print()
    print("📈 5 Charts Created:")
    print("  1. Component Impact Distribution - Stacked Bar Chart")
    print("  2. Severity Escalation Rate - Horizontal Bar Chart")
    print("  3. Incident Progression Flow - Sankey Diagram")
    print("  4. Risk Assessment Matrix - Heatmap")
    print("  5. Overall Progression Funnel - Funnel Chart")
    print()
    print(f"Output file: {Path(output_file).absolute()}")
    print("Open in browser to view interactive dashboard.")
    print()
    print("📚 Terminology:")
    print("  CVR (Marketing) → SRE Terms:")
    print("  - Conversion Rate → Escalation Rate")
    print("  - Funnel Analysis → Incident Progression Analysis")
    print("  - Drop-off Rate → Containment Rate")
    print("=" * 80)


if __name__ == "__main__":
    main()
