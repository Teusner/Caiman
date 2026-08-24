"""Coherent, movement-coupled simulated sensor generation."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from .models import Telemetry

if TYPE_CHECKING:
    from .robot import Robot


def generate_telemetry(
    robot: "Robot", timestamp: float, rng: np.random.Generator, neighbors: int, link_quality: float
) -> Telemetry:
    noise = rng.normal
    depth = robot.position.depth
    moving = robot.speed > 0.05
    return Telemetry(
        robot_id=robot.robot_id,
        timestamp=timestamp,
        x=robot.position.x,
        y=robot.position.y,
        depth=depth,
        speed=robot.speed,
        heading=robot.heading,
        roll=float(noise(0, 0.8)),
        pitch=float(noise(0, 0.6)),
        yaw=(robot.heading + float(noise(0, 0.5))) % 360,
        external_temperature=12.0 - depth * 0.015 + float(noise(0, 0.08)),
        internal_temperature=24.0 + (1.8 if moving else 0.4) + float(noise(0, 0.1)),
        external_pressure=101.325 + depth * 9.80665,
        internal_pressure=101.4 + float(noise(0, 0.08)),
        magnetometer_x=32.0 * math.cos(math.radians(robot.heading)) + float(noise(0, 0.3)),
        magnetometer_y=32.0 * math.sin(math.radians(robot.heading)) + float(noise(0, 0.3)),
        magnetometer_z=18.0 + float(noise(0, 0.3)),
        acceleration_x=(0.08 if moving else 0.0) + float(noise(0, 0.02)),
        acceleration_y=float(noise(0, 0.02)),
        acceleration_z=9.80665 + float(noise(0, 0.02)),
        angular_velocity_x=float(noise(0, 0.03)),
        angular_velocity_y=float(noise(0, 0.03)),
        angular_velocity_z=float(noise(0, 0.08)),
        battery=robot.battery,
        current=robot.current_draw,
        voltage=robot.nominal_voltage * (0.92 + 0.08 * robot.battery / 100.0),
        leak=robot.leak,
        link_quality=link_quality,
        neighbors=neighbors,
        last_packet_received=robot.last_packet_received,
        state=robot.state.value,
        gnss_available=depth <= 0.5,
        seafloor_depth=robot.latest_bottom_depth,
        altitude_above_bottom=(robot.latest_bottom_depth - depth) if robot.latest_bottom_depth is not None else None,
    )
