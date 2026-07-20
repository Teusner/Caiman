"""Shared enums and serializable domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class RobotState(str, Enum):
    IDLE = "IDLE"
    PROVISIONED = "PROVISIONED"
    EXPLORING = "EXPLORING"
    HOLDING = "HOLDING"
    RELAYING = "RELAYING"
    RETURNING_HOME = "RETURNING_HOME"
    SURFACING = "SURFACING"
    EMERGENCY = "EMERGENCY"
    OFFLINE = "OFFLINE"
    CAPTURED = "CAPTURED"


class MessageType(str, Enum):
    TELEMETRY = "TELEMETRY"
    COMMAND = "COMMAND"
    ACK = "ACK"
    PING = "PING"
    PONG = "PONG"
    ALERT = "ALERT"
    KEY_ROTATE = "KEY_ROTATE"
    MISSION_START = "MISSION_START"
    MISSION_STOP = "MISSION_STOP"


class CommandType(str, Enum):
    SET_WAYPOINT = "SET_WAYPOINT"
    HOLD_POSITION = "HOLD_POSITION"
    RESUME_MISSION = "RESUME_MISSION"
    SURFACE = "SURFACE"
    RETURN_HOME = "RETURN_HOME"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    SET_TELEMETRY_RATE = "SET_TELEMETRY_RATE"
    CHANGE_EXPLORATION_MODE = "CHANGE_EXPLORATION_MODE"
    ROTATE_KEY = "ROTATE_KEY"


class CommandStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"


@dataclass
class Position:
    x: float
    y: float
    depth: float = 0.0

    def distance_to(self, other: "Position") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.depth - other.depth) ** 2) ** 0.5


@dataclass
class Telemetry:
    robot_id: str
    timestamp: float
    x: float
    y: float
    depth: float
    speed: float
    heading: float
    roll: float
    pitch: float
    yaw: float
    external_temperature: float
    internal_temperature: float
    external_pressure: float
    internal_pressure: float
    magnetometer_x: float
    magnetometer_y: float
    magnetometer_z: float
    acceleration_x: float
    acceleration_y: float
    acceleration_z: float
    angular_velocity_x: float
    angular_velocity_y: float
    angular_velocity_z: float
    battery: float
    current: float
    voltage: float
    leak: bool
    link_quality: float
    neighbors: int
    last_packet_received: float | None
    state: str
    gnss_available: bool
    seafloor_depth: float | None = None
    altitude_above_bottom: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Command:
    command_id: str
    target_id: str
    command: CommandType
    created_at: float
    parameters: dict[str, Any] = field(default_factory=dict)
    ack_requested: bool = True
    timeout: float = 4.0
    max_attempts: int = 3
    status: CommandStatus = CommandStatus.PENDING
    attempts: int = 0
    acknowledged_at: float | None = None
    last_attempt_at: float | None = None
    latency: float | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["command"] = self.command.value
        result["status"] = self.status.value
        return result


@dataclass
class SecurityCounters:
    duplicate_drops: int = 0
    replay_drops: int = 0
    authentication_failures: int = 0
    ttl_drops: int = 0
    invalid_route_mac: int = 0
    decrypt_success: int = 0


@dataclass
class NetworkMetrics:
    packets_sent: int = 0
    packets_delivered: int = 0
    packets_lost: int = 0
    relays: int = 0
    retries: int = 0
    total_hops: int = 0
    total_latency: float = 0.0

    @property
    def delivery_rate(self) -> float:
        return self.packets_delivered / self.packets_sent if self.packets_sent else 0.0

    @property
    def average_hops(self) -> float:
        return self.total_hops / self.packets_delivered if self.packets_delivered else 0.0

    @property
    def average_latency(self) -> float:
        return self.total_latency / self.packets_delivered if self.packets_delivered else 0.0
