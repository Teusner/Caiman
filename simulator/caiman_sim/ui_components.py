"""Plotly and Streamlit presentation helpers, kept outside simulation logic."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from PIL import Image

from .models import RobotState


STATE_COLORS = {
    RobotState.EXPLORING.value: "#30d5f2",
    RobotState.RELAYING.value: "#f2cc60",
    RobotState.OFFLINE.value: "#5b6670",
    RobotState.EMERGENCY.value: "#ff4b5c",
    RobotState.RETURNING_HOME.value: "#ff9f43",
    RobotState.SURFACING.value: "#8ee3ff",
    RobotState.HOLDING.value: "#a78bfa",
}


@lru_cache(maxsize=1)
def _ocean_texture() -> Image.Image:
    return Image.open(Path(__file__).resolve().parents[1] / "assets" / "ocean_texture.png")


def mission_map(simulation: Any, show_trajectories: bool = True, show_links: bool = True, show_ids: bool = True) -> go.Figure:
    fig = go.Figure()
    rows = simulation.robot_rows()
    live_rows = [row for row in rows if row["position_status"] != "LAST KNOWN"]
    stale_rows = [row for row in rows if row["position_status"] == "LAST KNOWN"]
    fig.add_layout_image(
        dict(
            source=_ocean_texture(), xref="x", yref="y", x=0, y=simulation.config.height,
            sizex=simulation.config.width, sizey=simulation.config.height, sizing="stretch", opacity=0.38, layer="below",
        )
    )
    polygon = simulation.bathymetry.polygon + [simulation.bathymetry.polygon[0]]
    fig.add_trace(
        go.Scatter(
            x=[point[0] for point in polygon], y=[point[1] for point in polygon], mode="lines",
            fill="toself", fillcolor="rgba(29,171,199,.06)", line={"color": "#52d8ee", "width": 2, "dash": "dash"},
            name="Survey region", hovertemplate="Delimited bathymetric survey region<extra></extra>",
        )
    )
    if simulation.bathymetry.base_observed_mask.any():
        fig.add_trace(
            go.Contour(
                x=simulation.bathymetry.x_values,
                y=simulation.bathymetry.y_values,
                z=simulation.bathymetry.base_measured_grid,
                zmin=10,
                zmax=20,
                colorscale=[[0, "#55d6d0"], [0.45, "#1686a0"], [1, "#03152c"]],
                contours={"start": 10, "end": 20, "size": 1, "coloring": "heatmap", "showlabels": True, "labelfont": {"color": "#e8fbff", "size": 9}},
                line={"color": "rgba(210,249,255,.72)", "width": 1.1},
                connectgaps=False,
                opacity=0.72,
                colorbar={"title": "Bottom<br>depth (m)", "thickness": 12},
                hovertemplate="PC contour %{z:.2f} m<br>E %{x:.0f} m · N %{y:.0f} m<extra></extra>",
                name="Synced depth contours",
            )
        )
    if simulation.deployed:
        rendezvous_markers = simulation.rendezvous_positions + [simulation.sync_position]
        fig.add_trace(
            go.Scatter(
                x=[position.x for position in rendezvous_markers],
                y=[position.y for position in rendezvous_markers],
                mode="markers+text",
                text=["FLEET RV 1", "FLEET RV 2", "VESSEL STANDOFF"],
                textposition="bottom center",
                marker={"symbol": ["star", "star", "hourglass"], "size": [13, 13, 12], "color": ["#ffcf66", "#ffcf66", "#9effc7"]},
                name="Fleet surface backbone contacts",
            )
        )
        for row in stale_rows:
            radius = row["estimate_uncertainty_m"]
            fig.add_shape(
                type="circle",
                x0=row["estimated_x"] - radius,
                x1=row["estimated_x"] + radius,
                y0=row["estimated_y"] - radius,
                y1=row["estimated_y"] + radius,
                fillcolor="rgba(255,207,102,.035)",
                line={"color": "rgba(255,207,102,.32)", "width": 1, "dash": "dot"},
                layer="below",
            )
            fig.add_trace(go.Scatter(
                x=[row["x"], row["estimated_x"]],
                y=[row["y"], row["estimated_y"]],
                mode="lines",
                line={"color": "rgba(255,207,102,.55)", "width": 1.3, "dash": "dot"},
                hoverinfo="skip",
                showlegend=False,
            ))
        if stale_rows:
            fig.add_trace(go.Scatter(
                x=[row["estimated_x"] for row in stale_rows],
                y=[row["estimated_y"] for row in stale_rows],
                mode="markers+text" if show_ids else "markers",
                text=[f"~{row['robot_id']}" for row in stale_rows],
                textposition="bottom center",
                marker={"size": 13, "symbol": "diamond-open", "color": "#ffcf66", "line": {"width": 2}},
                customdata=[[row["robot_id"], row["estimated_depth"], row["estimate_uncertainty_m"], row["position_age_s"]] for row in stale_rows],
                hovertemplate="<b>Predicted %{customdata[0]}</b><br>Plan-propagated depth %{customdata[1]:.1f} m<br>Illustrative uncertainty ±%{customdata[2]:.0f} m<br>No RF for %{customdata[3]:.0f} s<extra></extra>",
                name="Dead-reckoning prediction",
            ))
    if show_links:
        for link in simulation.pc_topology_links():
            left = simulation.base.position if link["source"] == "BASE" else simulation.pc_position(link["source"])
            right = simulation.base.position if link["target"] == "BASE" else simulation.pc_position(link["target"])
            fig.add_trace(go.Scatter(x=[left.x, right.x], y=[left.y, right.y], mode="lines", line={"color": "rgba(42,173,210,.26)", "width": 1}, hoverinfo="skip", showlegend=False))
    for zone in simulation.obstacles:
        fig.add_shape(type="rect", x0=zone["x0"], x1=zone["x1"], y0=zone["y0"], y1=zone["y1"], fillcolor="rgba(255,93,93,.15)", line={"color": "#ff6b6b", "dash": "dot"})
    if show_trajectories:
        for robot_id in simulation.robots:
            reports = simulation.base.telemetry_history_by_robot.get(robot_id, [])
            fixes = [report for report in reports if {"x", "y"} <= report.keys()]
            if len(fixes) > 1:
                fig.add_trace(go.Scatter(x=[p["x"] for p in fixes], y=[p["y"] for p in fixes], mode="lines", line={"color": "rgba(48,213,242,.34)", "width": 1}, hoverinfo="skip", showlegend=False))
    if simulation.network.recent_routes:
        route = simulation.network.recent_routes[-1]["path"]
        points = [simulation.base.position if node == "BASE" else simulation.pc_position(node) for node in route]
        fig.add_trace(go.Scatter(x=[point.x for point in points], y=[point.y for point in points], mode="lines+markers", line={"color": "#ffd166", "width": 4}, marker={"size": 7}, name="Latest packet route", hovertext=route))
    if simulation.deployed:
        if live_rows:
            fig.add_trace(
                go.Scatter(
                    x=[row["estimated_x"] for row in live_rows], y=[row["estimated_y"] for row in live_rows], mode="markers+text" if show_ids else "markers",
                    text=[row["robot_id"] for row in live_rows], textposition="top center",
                    marker={"size": 16, "symbol": ["square" if row["is_data_mule"] else "circle" for row in live_rows], "color": ["#f2cc60" if row["is_data_mule"] else STATE_COLORS.get(row["state"], "#30d5f2") for row in live_rows], "line": {"color": "#d9f7ff", "width": 1.5}},
                    customdata=[[row["robot_id"], row["role"], row["estimated_depth"], row["seafloor_depth"], row["state"], row["battery"], row["position_status"], row["position_age_s"]] for row in live_rows],
                    hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>%{customdata[6]} · packet age %{customdata[7]:.0f}s<br>Filtered depth %{customdata[2]:.1f} m<br>Bottom %{customdata[3]}<br>State %{customdata[4]}<br>Battery %{customdata[5]:.1f}%<extra></extra>", name="Live RF tracking (filtered)",
                )
            )
        if stale_rows:
            fig.add_trace(
                go.Scatter(
                    x=[row["x"] for row in stale_rows], y=[row["y"] for row in stale_rows], mode="markers",
                    marker={"size": 8, "symbol": "x-open", "color": "rgba(190,205,214,.72)", "line": {"width": 1}},
                    customdata=[[row["robot_id"], row["depth"], row["position_age_s"]] for row in stale_rows],
                    hovertemplate="<b>Historical fix %{customdata[0]}</b><br>Last received depth %{customdata[1]:.1f} m<br>Fix age %{customdata[2]:.0f}s<extra></extra>",
                    name="Last received fix (historical)",
                )
            )
    vessel_label = "SURVEY VESSEL" if simulation.deployed else f"SURVEY VESSEL · {len(simulation.robots)} AUVs ON DECK"
    fig.add_trace(go.Scatter(x=[simulation.base.position.x], y=[simulation.base.position.y], mode="markers+text", text=[vessel_label] if show_ids else None, textposition="top center", marker={"symbol": "triangle-up", "size": 24, "color": "#24f0a5", "line": {"color": "white", "width": 1}}, name="Survey vessel"))
    fig.update_layout(
        height=650, margin={"l": 25, "r": 15, "t": 30, "b": 25}, paper_bgcolor="#071826", plot_bgcolor="#061826",
        xaxis={"range": [0, simulation.config.width], "title": "East (m)", "gridcolor": "rgba(255,255,255,.06)"},
        yaxis={"range": [0, simulation.config.height], "title": "North (m)", "gridcolor": "rgba(255,255,255,.06)", "scaleanchor": "x", "scaleratio": 1},
        legend={"orientation": "h", "y": 1.05},
    )
    return fig


def topology_figure(simulation: Any) -> go.Figure:
    fig = go.Figure()
    for link in simulation.pc_topology_links():
        left = simulation.base.position if link["source"] == "BASE" else simulation.pc_position(link["source"])
        right = simulation.base.position if link["target"] == "BASE" else simulation.pc_position(link["target"])
        fig.add_trace(go.Scatter(x=[left.x, right.x], y=[left.y, right.y], mode="lines", line={"width": 1 + link["quality"] * 4, "color": "rgba(48,213,242,.5)"}, hovertext=f"{link['distance']:.0f} m · Q {link['quality']:.0%}", hoverinfo="text", showlegend=False))
    rows = {row["robot_id"]: row for row in simulation.robot_rows()}
    for node_id, node in simulation.network.nodes.items():
        role = getattr(node, "role", "BASE")
        position = node.position if node_id == "BASE" else simulation.pc_position(node_id)
        stale = node_id != "BASE" and rows[node_id]["position_status"] != "LIVE RF"
        mule = node_id != "BASE" and rows[node_id]["is_data_mule"]
        symbol = "triangle-up" if node_id == "BASE" else ("square-open" if mule else "circle-open") if stale else "square" if mule else "circle"
        fig.add_trace(go.Scatter(x=[position.x], y=[position.y], mode="markers+text", text=[node_id + (" ?" if stale else "")], textposition="top center", marker={"size": 20 if node_id == "BASE" else 13, "symbol": symbol, "color": "#24f0a5" if node_id == "BASE" else "#f2cc60" if mule else "#30d5f2"}, name=node_id))
    fig.update_layout(height=520, paper_bgcolor="#071826", plot_bgcolor="#082235", margin={"l": 20, "r": 20, "t": 20, "b": 20}, showlegend=False, xaxis={"visible": False}, yaxis={"visible": False})
    return fig


def telemetry_history_figure(samples: Any) -> go.Figure:
    rows = [sample.to_dict() if hasattr(sample, "to_dict") else dict(sample) for sample in samples]
    fig = go.Figure()
    if rows:
        frame = pd.DataFrame(rows)
        fig.add_trace(go.Scatter(x=frame["timestamp"], y=frame["battery"], name="Battery %", yaxis="y"))
        fig.add_trace(go.Scatter(x=frame["timestamp"], y=frame["depth"], name="Depth m", yaxis="y2"))
        fig.add_trace(go.Scatter(x=frame["timestamp"], y=frame["link_quality"] * 100, name="Link quality %", yaxis="y"))
    fig.update_layout(height=360, paper_bgcolor="#071826", plot_bgcolor="#082235", margin={"l": 35, "r": 45, "t": 25, "b": 30}, yaxis2={"overlaying": "y", "side": "right", "autorange": "reversed", "title": "Depth"}, legend={"orientation": "h"})
    return fig
