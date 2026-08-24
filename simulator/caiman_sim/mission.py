"""Mission export helpers reusable by the Streamlit UI and scripts."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def export_mission(simulation: Any, output_dir: str | Path = "exports") -> dict[str, Path]:
    """Export all logs and a complete snapshot, returning the created paths."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    telemetry_rows = [sample.to_dict() for robot in simulation.robots.values() for sample in robot.telemetry_history]
    packets = list(simulation.network.packet_log)
    bathymetry_rows = [
        {
            "x": float(x),
            "y": float(y),
            "measured_depth": float(simulation.bathymetry.base_measured_grid[y_index, x_index]),
        }
        for y_index, y in enumerate(simulation.bathymetry.y_values)
        for x_index, x in enumerate(simulation.bathymetry.x_values)
        if simulation.bathymetry.base_observed_mask[y_index, x_index]
    ]
    summary = simulation.summary()
    payload = {
        "mission_id": simulation.mission_id,
        "simulated_time": simulation.time,
        "running": simulation.running,
        "config": simulation.config.to_dict(),
        "summary": summary,
        "robots": simulation.robot_rows(),
        "events": simulation.events.records,
        "packets": packets,
        "telemetry": telemetry_rows,
        "commands": [command.to_dict() for command in simulation.base.commands.values()],
        "bathymetry": {
            "region_polygon": simulation.bathymetry.polygon,
            "coverage": simulation.bathymetry.base_coverage,
            "deepest_observed": asdict(simulation.bathymetry.base_deepest_sample) if simulation.bathymetry.base_deepest_sample else None,
            "mapped_cells": bathymetry_rows,
        },
    }
    paths = {
        "telemetry": destination / f"telemetry_{stamp}.csv",
        "packets": destination / f"packets_{stamp}.csv",
        "mission": destination / f"mission_{stamp}.json",
        "config": destination / f"config_{stamp}.json",
        "summary": destination / f"summary_{stamp}.json",
        "bathymetry": destination / f"bathymetry_{stamp}.csv",
    }
    pd.DataFrame(telemetry_rows).to_csv(paths["telemetry"], index=False)
    pd.DataFrame(packets).to_csv(paths["packets"], index=False)
    pd.DataFrame(bathymetry_rows).to_csv(paths["bathymetry"], index=False)
    paths["mission"].write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    paths["config"].write_text(json.dumps(simulation.config.to_dict(), indent=2), encoding="utf-8")
    paths["summary"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return paths
