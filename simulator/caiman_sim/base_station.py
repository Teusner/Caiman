"""Central computer state, provisioning and command ledger."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, field
from typing import Any

from .crypto_layer import KeyMaterial, KeyStore, ReplayWindow
from .models import Command, CommandStatus, CommandType, Position, SecurityCounters


@dataclass
class BaseStation:
    mission_id: str
    position: Position
    nonce_prefix: bytes
    sequence: int = 0
    last_packet_received: float | None = None
    telemetry_by_robot: dict[str, dict[str, Any]] = field(default_factory=dict)
    telemetry_history_by_robot: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    commands: dict[str, Command] = field(default_factory=dict)
    key_rotation_status: dict[str, bool] = field(default_factory=dict)
    replay: ReplayWindow = field(default_factory=ReplayWindow)
    security: SecurityCounters = field(default_factory=SecurityCounters)
    keys: KeyStore = field(init=False)

    def __post_init__(self) -> None:
        self.keys = KeyStore(self.mission_id)

    @property
    def online(self) -> bool:
        return True

    def generate_mission_key(self) -> KeyMaterial:
        return self.keys.provision(secrets.token_bytes(32), 1)

    def next_sequence(self) -> int:
        value = self.sequence
        self.sequence += 1
        return value

    def record_telemetry(self, robot_id: str, payload: dict[str, Any]) -> None:
        """Store only information that physically reached the vessel computer."""
        snapshot = dict(payload)
        self.telemetry_by_robot[robot_id] = snapshot
        history = self.telemetry_history_by_robot.setdefault(robot_id, [])
        by_timestamp = {float(item.get("timestamp", -1.0)): dict(item) for item in history}
        by_timestamp[float(snapshot.get("timestamp", -1.0))] = snapshot
        self.telemetry_history_by_robot[robot_id] = [by_timestamp[key] for key in sorted(by_timestamp)][-1000:]

    def merge_telemetry_history(self, robot_id: str, payloads: list[dict[str, Any]]) -> None:
        """Merge a delayed onboard log received during rendezvous or recovery."""
        history = self.telemetry_history_by_robot.setdefault(robot_id, [])
        by_timestamp = {float(item.get("timestamp", -1.0)): dict(item) for item in history}
        for payload in payloads:
            by_timestamp[float(payload.get("timestamp", -1.0))] = dict(payload)
        merged = [by_timestamp[key] for key in sorted(by_timestamp)]
        self.telemetry_history_by_robot[robot_id] = merged[-1000:]

    def create_command(
        self,
        target_id: str,
        kind: CommandType,
        now: float,
        parameters: dict[str, Any] | None = None,
        timeout: float = 4.0,
        max_attempts: int = 3,
    ) -> Command:
        command = Command(
            command_id=uuid.uuid4().hex[:12],
            target_id=target_id,
            command=kind,
            created_at=now,
            parameters=parameters or {},
            timeout=timeout,
            max_attempts=max_attempts,
        )
        self.commands[command.command_id] = command
        return command

    def acknowledge(self, command_id: str, now: float) -> None:
        command = self.commands.get(command_id)
        if command is None:
            return
        command.status = CommandStatus.ACKNOWLEDGED
        command.acknowledged_at = now
        command.latency = now - command.created_at

    def prepare_rotation(self, robot_ids: list[str]) -> KeyMaterial:
        next_id = self.keys.current_key_id + 1
        new_key = self.keys.provision(secrets.token_bytes(32), next_id)
        self.key_rotation_status = {robot_id: False for robot_id in robot_ids}
        return new_key
