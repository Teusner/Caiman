"""Underwater robot movement, battery, sensors and command execution."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .crypto_layer import KeyStore, ReplayWindow
from .models import CommandType, Position, RobotState, SecurityCounters, Telemetry
from .telemetry import generate_telemetry


@dataclass
class Robot:
    robot_id: str
    position: Position
    home: Position
    mission_id: str
    mode: str = "lawnmower"
    speed: float = 2.0
    heading: float = 0.0
    battery: float = 100.0
    state: RobotState = RobotState.PROVISIONED
    waypoint: Position | None = None
    path_index: int = 0
    trajectory: list[Position] = field(default_factory=list)
    telemetry_history: list[Telemetry] = field(default_factory=list)
    leak: bool = False
    forced_offline: bool = False
    captured: bool = False
    temporary_offline_until: float = 0.0
    last_packet_received: float | None = None
    current_draw: float = 0.3
    sequence: int = 0
    telemetry_interval: float = 5.0
    last_telemetry_at: float = -1e9
    keys: KeyStore = field(init=False)
    replay: ReplayWindow = field(default_factory=ReplayWindow)
    security: SecurityCounters = field(default_factory=SecurityCounters)
    role: str = "ON_DECK"
    deployed: bool = False
    assigned_waypoints: list[Position] = field(default_factory=list)
    assigned_waypoint_index: int = 0
    route_revision: int = 0
    route_complete: bool = False
    latest_bottom_depth: float | None = None
    unsynced_samples: int = 0
    battery_capacity_ah: float = 56.0
    nominal_voltage: float = 12.0
    mean_motor_current: float = 15.0
    operational_idle_seconds: float = 0.0

    def __post_init__(self) -> None:
        self.keys = KeyStore(self.mission_id)
        self.trajectory.append(Position(self.position.x, self.position.y, self.position.depth))

    @property
    def online(self) -> bool:
        return not self.captured and not self.forced_offline and self.state not in {RobotState.OFFLINE, RobotState.CAPTURED}

    def next_sequence(self) -> int:
        value = self.sequence
        self.sequence += 1
        return value

    def choose_waypoint(self, width: float, height: float, rng: np.random.Generator) -> None:
        if self.mode == "random_waypoint":
            self.waypoint = Position(float(rng.uniform(50, width - 50)), float(rng.uniform(50, height - 50)), float(rng.uniform(8, 45)))
            return
        lane_spacing = max(45.0, height / 10)
        lane = (self.path_index + int(self.robot_id[1:])) % max(1, int(height / lane_spacing))
        x = width - 55.0 if self.path_index % 2 == 0 else 55.0
        self.waypoint = Position(x, 55.0 + lane * lane_spacing, 18.0 + int(self.robot_id[1:]) * 2.0)
        self.path_index += 1

    def assign_route(self, waypoints: list[Position]) -> None:
        self.route_revision += 1
        self.assigned_waypoints = waypoints
        self.assigned_waypoint_index = 0
        self.route_complete = False
        self.waypoint = waypoints[0] if waypoints else None

    def update(self, dt: float, width: float, height: float, rng: np.random.Generator, peers: list["Robot"]) -> None:
        if not self.online or self.state in {RobotState.HOLDING, RobotState.EMERGENCY}:
            self.current_draw = 1.5
            self._drain_battery(dt)
            return
        if self.state == RobotState.SURFACING:
            self.position.depth = max(0.0, self.position.depth - 1.5 * dt)
            self.current_draw = self.mean_motor_current
            self._drain_battery(dt)
            return
        if self.state == RobotState.RETURNING_HOME:
            self.waypoint = Position(self.home.x, self.home.y, 0.0)
            if self.position.distance_to(self.waypoint) < 3.0:
                self.position = Position(self.home.x, self.home.y, 0.0)
                self.state = RobotState.HOLDING
                self.current_draw = 1.5
                self._drain_battery(dt)
                return
        reach_threshold = 8.0
        if self.waypoint is not None and (self.assigned_waypoints or self.role == "COURIER"):
            reach_threshold = 0.45 if self.waypoint.depth <= 0.5 else 3.0
        if self.state != RobotState.RETURNING_HOME and (self.waypoint is None or self.position.distance_to(self.waypoint) < reach_threshold):
            if self.role in {"RELAY", "COURIER"}:
                self.current_draw = 1.5
                self._drain_battery(dt)
                return
            if self.assigned_waypoints:
                self.assigned_waypoint_index += 1
                if self.assigned_waypoint_index >= len(self.assigned_waypoints):
                    self.route_complete = True
                    self.state = RobotState.HOLDING
                    self.current_draw = 0.25
                    self._drain_battery(dt)
                    return
                self.waypoint = self.assigned_waypoints[self.assigned_waypoint_index]
            else:
                self.choose_waypoint(width, height, rng)
        assert self.waypoint is not None
        dx, dy, dz = self.waypoint.x - self.position.x, self.waypoint.y - self.position.y, self.waypoint.depth - self.position.depth
        planar = math.hypot(dx, dy)
        self.heading = math.degrees(math.atan2(dy, dx)) % 360 if planar else self.heading
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        step = min(self.speed * dt, distance)
        if distance > 0:
            vx, vy, vz = dx / distance, dy / distance, dz / distance
            # Repulsive correction keeps robots from occupying almost the same point.
            for peer in peers if self.state != RobotState.RETURNING_HOME else []:
                if peer.robot_id == self.robot_id or not peer.online:
                    continue
                separation = self.position.distance_to(peer.position)
                if 0.01 < separation < 18.0:
                    vx += (self.position.x - peer.position.x) / separation * 0.8
                    vy += (self.position.y - peer.position.y) / separation * 0.8
            norm = math.sqrt(vx * vx + vy * vy + vz * vz) or 1.0
            self.position.x = min(width, max(0.0, self.position.x + step * vx / norm))
            self.position.y = min(height, max(0.0, self.position.y + step * vy / norm))
            self.position.depth = min(80.0, max(0.0, self.position.depth + step * vz / norm))
        if self.state == RobotState.RETURNING_HOME:
            self.state = RobotState.RETURNING_HOME
        elif self.role in {"RELAY", "COURIER"}:
            self.state = RobotState.RELAYING
        else:
            self.state = RobotState.EXPLORING
        self.current_draw = self.mean_motor_current
        self._drain_battery(dt)
        self.trajectory.append(Position(self.position.x, self.position.y, self.position.depth))
        self.trajectory = self.trajectory[-300:]
        if self.battery <= 15.0 and self.state != RobotState.RETURNING_HOME:
            self.state = RobotState.RETURNING_HOME

    def _drain_battery(self, dt: float) -> None:
        used_ah = self.current_draw * dt / 3600.0
        self.battery = max(0.0, self.battery - used_ah / self.battery_capacity_ah * 100.0)
        if self.battery <= 0:
            self.state = RobotState.OFFLINE

    def telemetry(self, now: float, rng: np.random.Generator, neighbors: int, quality: float) -> Telemetry:
        sample = generate_telemetry(self, now, rng, neighbors, quality)
        self.telemetry_history.append(sample)
        self.telemetry_history = self.telemetry_history[-1000:]
        self.last_telemetry_at = now
        return sample

    def execute_command(self, command: str, parameters: dict[str, Any]) -> None:
        kind = CommandType(command)
        if kind == CommandType.SET_WAYPOINT:
            self.waypoint = Position(float(parameters["x"]), float(parameters["y"]), float(parameters.get("depth", self.position.depth)))
            self.state = RobotState.EXPLORING
        elif kind == CommandType.HOLD_POSITION:
            self.state = RobotState.HOLDING
        elif kind == CommandType.RESUME_MISSION:
            self.state = RobotState.EXPLORING
        elif kind == CommandType.SURFACE:
            self.state = RobotState.SURFACING
        elif kind == CommandType.RETURN_HOME:
            self.state = RobotState.RETURNING_HOME
        elif kind == CommandType.EMERGENCY_STOP:
            self.state = RobotState.EMERGENCY
        elif kind == CommandType.SET_TELEMETRY_RATE:
            self.telemetry_interval = max(1.0, float(parameters.get("seconds", 5.0)))
        elif kind == CommandType.CHANGE_EXPLORATION_MODE:
            self.mode = str(parameters.get("mode", "lawnmower"))
            self.waypoint = None
