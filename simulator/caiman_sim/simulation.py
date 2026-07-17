"""Deterministic mission orchestrator joining robots, crypto, network and control."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import replace
from itertools import permutations
from typing import Any

import numpy as np

from .base_station import BaseStation
from .bathymetry import BathymetryMap
from .config import CommunicationProfile, SimulationConfig
from .logging_utils import EventLog
from .mission import export_mission
from .models import Command, CommandStatus, CommandType, MessageType, Position, RobotState
from .network import Network
from .packets import PacketFrame, create_frame
from .robot import Robot


class Simulation:
    """A complete step-driven Caiman swarm mission; no background loop is required."""

    def __init__(self, config: SimulationConfig | None = None) -> None:
        self.config = config or SimulationConfig()
        self.rng = np.random.default_rng(self.config.seed)
        self.mission_id = f"CAIMAN-{self.config.seed:08X}"
        self.nonce_prefix = hashlib.sha256(self.mission_id.encode()).digest()[:4]
        self.time = 0.0
        self.running = False
        self.deployed = False
        self.mission_phase = "ON_DECK"
        self.events = EventLog()
        self.base = BaseStation(self.mission_id, Position(70.0, self.config.height / 2, 0.0), self.nonce_prefix)
        self.vessel_origin = Position(self.base.position.x, self.base.position.y, 0.0)
        self.vessel_target: Position | None = None
        self.vessel_speed = 6.0
        self.vessel_trajectory = [Position(self.base.position.x, self.base.position.y, 0.0)]
        self.bathymetry = BathymetryMap(self.config.width, self.config.height, self.config.seed)
        self.robots: dict[str, Robot] = {}
        self.network = Network(self.config, self.rng)
        self.sent_frames: list[PacketFrame] = []
        self.alerted_battery: set[str] = set()
        self.rendezvous_positions = [
            # Batch 1 transects end on the east side; batch 2 ends west.
            # Moving the contacts with the sweep avoids backtracking.
            Position(760.0, self.config.height * 0.46, 0.0),
            Position(360.0, self.config.height * 0.56, 0.0),
        ]
        self.rendezvous_position = self.rendezvous_positions[0]
        self.sync_position = self._surface_standoff(self.rendezvous_position)
        self.survey_batches: list[dict[str, list[Position]]] = []
        self.current_survey_cycle = 0
        self.courier_id: str | None = None
        self.data_mule_history: list[str] = []
        self.fleet_backbone_history: list[list[str]] = []
        self.fleet_sync_pending: set[str] = set()
        self.fleet_sync_attempts: dict[str, int] = {}
        self.batch_arrived: set[str] = set()
        self.cleanup_passes = 0
        self.data_sync_count = 0
        self.sync_attempts = 0
        self.pending_status_sync: dict[str, dict[str, Any]] = {}
        self.pending_telemetry_sync: dict[str, list[dict[str, Any]]] = {}
        # Vessel-side dead-reckoning anchors. A new route starts from the
        # previous estimate at the instant it is issued, never from an old RF
        # fix with the full accumulated outage time applied again.
        self.estimator_anchors: dict[str, dict[str, Any]] = {}
        self.pending_sample_count = 0
        # Small coastal exclusion zones stay outside the planned transects.
        self.obstacles = [
            {"x0": 92.0, "x1": 132.0, "y0": 108.0, "y1": 172.0},
            {"x0": 940.0, "x1": 978.0, "y0": 505.0, "y1": 575.0},
        ] if self.config.obstacles_enabled else []
        self._initialize()

    def _initialize(self) -> None:
        self.events.add(0.0, "security", "Mission key generated")
        mission_key = self.base.generate_mission_key()
        for index in range(1, self.config.robot_count + 1):
            robot_id = f"R{index}"
            # All vehicles are physically on the survey vessel until DEPLOY.
            position = Position(self.base.position.x, self.base.position.y, 0.0)
            robot = Robot(
                robot_id=robot_id,
                position=position,
                home=Position(self.base.position.x, self.base.position.y, 0.0),
                mission_id=self.mission_id,
                mode=self.config.movement_mode,
                telemetry_interval=self.config.telemetry_interval,
                battery_capacity_ah=self.config.battery_capacity_ah,
                nominal_voltage=self.config.nominal_voltage,
                mean_motor_current=self.config.mean_motor_current,
            )
            robot.keys.provision(mission_key.master, mission_key.key_id)
            self.robots[robot_id] = robot
            self.base.record_telemetry(robot_id, self._status_snapshot(robot, timestamp=0.0))
            self.events.add(0.0, "security", f"Robot {robot_id} provisioned", f"key_id={mission_key.key_id}")
        self.events.add(0.0, "security", "All robots provisioned", f"count={len(self.robots)}")
        self.network.register("BASE", self.base)
        for robot_id, robot in self.robots.items():
            self.network.register(robot_id, robot)
        self.events.add(0.0, "mission", "Robots secured on survey vessel", "Awaiting deploy")

    def _surface_standoff(self, rendezvous: Position) -> Position:
        """Place the vessel near a rendezvous while keeping the AUV area clear."""
        dx = self.vessel_origin.x - rendezvous.x
        dy = self.vessel_origin.y - rendezvous.y
        distance = float(np.hypot(dx, dy))
        if distance <= 1e-9:
            return Position(rendezvous.x, rendezvous.y, 0.0)
        # Near the RF edge, so the closest AUVs provide real multi-hop paths
        # for peers on the far side of the rendezvous cluster.
        offset = min(distance, self.config.communication_range * 0.92)
        return Position(
            rendezvous.x + dx / distance * offset,
            rendezvous.y + dy / distance * offset,
            0.0,
        )

    def _update_vessel(self, dt: float) -> None:
        """Move the survey vessel continuously toward the next RF standoff."""
        if self.vessel_target is None:
            return
        distance = self.base.position.distance_to(self.vessel_target)
        if distance <= 1e-9:
            return
        step = min(self.vessel_speed * dt, distance)
        ratio = step / distance
        self.base.position = Position(
            self.base.position.x + (self.vessel_target.x - self.base.position.x) * ratio,
            self.base.position.y + (self.vessel_target.y - self.base.position.y) * ratio,
            0.0,
        )
        self.vessel_trajectory.append(Position(self.base.position.x, self.base.position.y, 0.0))
        self.vessel_trajectory = self.vessel_trajectory[-1000:]

    def apply_runtime_config(self, desired: SimulationConfig) -> None:
        """Apply controls that are safe to change without rebuilding the fleet."""
        runtime_fields = (
            "simulation_speed", "communication_profile", "communication_range", "packet_loss",
            "bitrate", "base_latency", "jitter", "default_ttl", "telemetry_interval",
            "obstacles_enabled", "temporary_offline_probability",
        )
        for field in runtime_fields:
            setattr(self.config, field, getattr(desired, field))
        for robot in self.robots.values():
            robot.telemetry_interval = desired.telemetry_interval
        self.obstacles = [
            {"x0": 92.0, "x1": 132.0, "y0": 108.0, "y1": 172.0},
            {"x0": 940.0, "x1": 978.0, "y0": 505.0, "y1": 575.0},
        ] if desired.obstacles_enabled else []
        self.sync_position = self._surface_standoff(self.rendezvous_position)
        if self.deployed and self.mission_phase != "RETURNING_TO_VESSEL":
            self.vessel_target = Position(self.sync_position.x, self.sync_position.y, 0.0)

    def deploy(self) -> None:
        """Launch five surveyors sharing store-carry-forward duty at rendezvous."""
        if self.deployed:
            if not self.running and self.mission_phase != "COMPLETE":
                self.start()
            return
        robot_ids = list(self.robots)
        self.courier_id = None
        self.vessel_target = Position(self.sync_position.x, self.sync_position.y, 0.0)
        self.survey_batches = self.bathymetry.build_survey_batches(robot_ids, self.rendezvous_positions)
        for robot_id in robot_ids:
            robot = self.robots[robot_id]
            robot.role = "SURVEY"
            robot.deployed = True
            robot.state = RobotState.EXPLORING
            self._assign_known_route(robot, self.survey_batches[0][robot_id])
        self.deployed = True
        self.running = True
        self.mission_phase = "DEPLOYING"
        self.events.add(self.time, "mission", "Fleet deployed", f"all-survey={robot_ids}; shared surface backbone")
        self.events.add(self.time, "mission", "Productive rendezvous survey started", "All AUVs map while the vessel pre-positions for fleet-wide surface sync")
        for robot_id, robot in self.robots.items():
            frame = self._frame(
                "BASE",
                robot_id,
                MessageType.MISSION_START,
                {"role": robot.role, "depth_min": 10.0, "depth_limit": 20.0, "survey_region": self.bathymetry.polygon},
            )
            self.network.transmit(frame, self.time, self._handle_delivery)

    def start(self) -> None:
        if not self.deployed:
            self.events.add(self.time, "mission", "Start ignored", "Deploy the robots first", "warning")
            return
        if not self.running and self.mission_phase != "COMPLETE":
            self.running = True
            self.events.add(self.time, "mission", "Mission resumed")

    def pause(self) -> None:
        self.running = False
        self.events.add(self.time, "mission", "Mission paused")

    def step(self, force: bool = False) -> None:
        if not self.deployed or self.mission_phase == "COMPLETE":
            return
        if not self.running and not force:
            return
        dt = self.config.tick_seconds * self.config.simulation_speed
        self.time += dt
        self._update_vessel(dt)
        peers = list(self.robots.values())
        for robot in peers:
            if robot.temporary_offline_until and self.time >= robot.temporary_offline_until and not robot.forced_offline:
                robot.temporary_offline_until = 0.0
                robot.state = RobotState.RELAYING if robot.role == "COURIER" else RobotState.EXPLORING
                self.events.add(self.time, "network", "Temporary outage ended", robot.robot_id)
            elif (
                robot.online
                and self.config.temporary_offline_probability > 0
                and self.rng.random() < self.config.temporary_offline_probability * dt
            ):
                robot.temporary_offline_until = self.time + float(self.rng.uniform(3.0, 12.0))
                robot.state = RobotState.OFFLINE
                self.events.add(self.time, "network", "Temporary outage", robot.robot_id, "warning")
            previous = Position(robot.position.x, robot.position.y, robot.position.depth)
            robot.update(dt, self.config.width, self.config.height, self.rng, peers)
            if robot.state == RobotState.HOLDING and self.mission_phase not in {"RETURNING_TO_VESSEL", "COMPLETE"}:
                robot.operational_idle_seconds += dt
            if self._inside_obstacle(robot.position):
                robot.position = previous
                self.events.add(self.time, "mission", "Obstacle avoided", robot.robot_id)
            if robot.role == "SURVEY":
                bottom = self.bathymetry.depth_at(robot.position.x, robot.position.y)
                altitude = max(0.0, bottom - robot.position.depth)
                beam_radius = self.bathymetry.sonar_footprint_radius(altitude)
                sample = self.bathymetry.observe(robot.position.x, robot.position.y, beam_radius, self.rng)
            else:
                sample = None
            if sample is not None:
                robot.latest_bottom_depth = sample.depth
            if robot.battery <= 15.0 and robot.robot_id not in self.alerted_battery:
                self.alerted_battery.add(robot.robot_id)
                self.events.add(self.time, "alert", "Critical battery", robot.robot_id, "warning")
                self._send_from_robot(robot, MessageType.ALERT, "BASE", {"reason": "critical_battery", "battery": robot.battery})
        for robot in peers:
            if robot.online and self.time - robot.last_telemetry_at >= robot.telemetry_interval:
                neighbors = self.network.neighbors(robot.robot_id)
                quality = max((self.network.transport.quality(robot.position.distance_to(self.network.nodes[n].position)) for n in neighbors), default=0.0)
                sample = robot.telemetry(self.time, self.rng, len(neighbors), quality)
                connected = self.network.connected_to_base()
                if robot.robot_id in connected:
                    payload = sample.to_dict()
                    payload["route_waypoint_index"] = robot.assigned_waypoint_index
                    payload["route_revision"] = robot.route_revision
                    self._send_from_robot(robot, MessageType.TELEMETRY, "BASE", payload)
                else:
                    robot.unsynced_samples += 1
        self._process_command_timeouts()
        survey_robots = [robot for robot in peers if robot.role == "SURVEY"]
        if self.mission_phase == "DEPLOYING" and survey_robots and all(robot.assigned_waypoint_index > 0 for robot in survey_robots):
            self.mission_phase = "SURVEYING"
            self.events.add(self.time, "mission", "Survey robots submerged", "RF and GNSS unavailable until surfacing")
        self._advance_store_and_forward_cycle(survey_robots)

    def step_many(self, count: int, force: bool = True) -> None:
        for _ in range(max(0, int(count))):
            if self.mission_phase == "COMPLETE":
                break
            self.step(force=force)

    def _advance_store_and_forward_cycle(self, survey_robots: list[Robot]) -> None:
        if not survey_robots:
            return
        if self.mission_phase == "RETURNING_TO_VESSEL":
            if all(robot.position.distance_to(self.base.position) < 3.0 for robot in self.robots.values()):
                self._complete_survey(survey_robots, survey_robots[0])
            return
        if self.mission_phase in {"DEPLOYING", "SURVEYING"}:
            # An early arrival keeps moving on a small echosounder patrol instead
            # of holding at a predictable surface point.
            for robot in survey_robots:
                if robot.route_complete:
                    first_arrival = robot.robot_id not in self.batch_arrived
                    self.batch_arrived.add(robot.robot_id)
                    self._assign_rendezvous_patrol(robot)
                    if first_arrival:
                        self.events.add(self.time, "mission", "AUV entered active rendezvous patrol", robot.robot_id)
            if len(self.batch_arrived) == len(survey_robots):
                final_cycle = self.current_survey_cycle + 1 >= len(self.survey_batches)
                if final_cycle and self.bathymetry.coverage < 1.0 and self.cleanup_passes < 3:
                    if self._launch_cooperative_cleanup(survey_robots):
                        return
                self._begin_fleet_mesh_sync(survey_robots)
            return
        if self.mission_phase != "SYNCING_WITH_VESSEL":
            return
        self._advance_fleet_mesh_sync(survey_robots)

    def _advance_fleet_mesh_sync(self, survey_robots: list[Robot]) -> None:
        """Let every surfaced AUV deliver its own replicated mission shard."""
        for robot_id in sorted(self.fleet_sync_pending):
            robot = self.robots[robot_id]
            attempt = self.fleet_sync_attempts.get(robot_id, 0) + 1
            self.fleet_sync_attempts[robot_id] = attempt
            payload = {
                "map_revision": self.data_sync_count + 1,
                "onboard_coverage": self.bathymetry.coverage,
                "mapped_cells": int(self.bathymetry.observed_mask.sum()),
                "deepest": self.bathymetry.deepest_sample.depth if self.bathymetry.deepest_sample else None,
                "fleet_backbone_member": robot_id,
            }
            frame = self._frame(robot_id, "BASE", MessageType.TELEMETRY, payload)
            delivered = self.network.transmit(frame, self.time, self._handle_delivery, attempt=attempt)
            if delivered:
                self.base.merge_telemetry_history(
                    robot_id,
                    self.pending_telemetry_sync.get(robot_id, []) + [sample.to_dict() for sample in robot.telemetry_history],
                )
                self._record_position_report(
                    robot_id,
                    self._status_snapshot(robot, timestamp=self.time),
                )
                snapshot = self.pending_status_sync.get(robot_id, {})
                robot.unsynced_samples = max(0, robot.unsynced_samples - int(snapshot.get("buffered_samples", 0)))
                self.fleet_sync_pending.discard(robot_id)
            elif attempt % self.config.max_retries == 0:
                self.events.add(self.time, "network", "Fleet backbone retry window restarted", robot_id, "warning")

        if self.fleet_sync_pending:
            return

        self.bathymetry.sync_to_base(self.pending_sample_count)
        self.data_sync_count += 1
        self.pending_status_sync.clear()
        self.pending_telemetry_sync.clear()
        self.events.add(
            self.time,
            "mission",
            "Fleet mesh synchronized with vessel",
            f"revision={self.data_sync_count}; five active carriers; coverage={self.bathymetry.base_coverage:.1%}",
        )
        if self.current_survey_cycle + 1 >= len(self.survey_batches):
            self._begin_recovery()
            return
        next_cycle = self.current_survey_cycle + 1
        for robot in survey_robots:
            robot.speed = 2.0
            self._assign_known_route(robot, self.survey_batches[next_cycle][robot.robot_id])
            robot.state = RobotState.EXPLORING
        self.current_survey_cycle = next_cycle
        self.rendezvous_position = self.rendezvous_positions[next_cycle]
        self.sync_position = self._surface_standoff(self.rendezvous_position)
        self.vessel_target = Position(self.sync_position.x, self.sync_position.y, 0.0)
        self.batch_arrived.clear()
        self.mission_phase = "SURVEYING"
        self.events.add(self.time, "mission", "All AUVs resumed bathymetric survey", f"cycle={next_cycle + 1}")

    def _assign_rendezvous_patrol(self, robot: Robot) -> None:
        """Keep a surfaced early arrival mapping a small loop inside RF range."""
        index = int(robot.robot_id[1:]) - 1
        center = self.rendezvous_positions[self.current_survey_cycle]
        angle = index * 6.283185307179586 / len(self.robots)
        radius = 20.0 + 3.0 * (index % 2)
        points = [
            Position(center.x + radius * np.cos(angle + turn), center.y + radius * np.sin(angle + turn), 0.0)
            for turn in (0.0, 1.5707963267948966, 3.141592653589793, 4.71238898038469, 6.283185307179586)
        ]
        self._assign_known_route(robot, points)
        robot.state = RobotState.EXPLORING

    def _begin_fleet_mesh_sync(self, survey_robots: list[Robot]) -> None:
        """Start a redundant surface backbone with every AUV as a carrier."""
        ordered = sorted(survey_robots, key=lambda robot: robot.robot_id)
        members = [robot.robot_id for robot in ordered]
        self.courier_id = None
        self.fleet_backbone_history.append(members)
        self.fleet_sync_pending = set(members)
        self.fleet_sync_attempts = {robot_id: 0 for robot_id in members}
        self.pending_status_sync = {
            robot.robot_id: self._status_snapshot(robot, timestamp=self.time)
            for robot in ordered
        }
        self.pending_telemetry_sync = {
            robot.robot_id: [sample.to_dict() for sample in robot.telemetry_history]
            for robot in ordered
        }
        self.pending_sample_count = len(self.bathymetry.samples)
        self.mission_phase = "SYNCING_WITH_VESSEL"
        self.events.add(
            self.time,
            "mission",
            "Fleet-wide surface backbone formed",
            f"members={members}; vessel pre-positioned at ({self.base.position.x:.0f}, {self.base.position.y:.0f})",
        )

    def _launch_cooperative_cleanup(self, survey_robots: list[Robot]) -> bool:
        """Assign every remaining reconnaissance cell before final delivery."""
        missing = self.bathymetry.inside_mask & ~self.bathymetry.observed_mask
        indices = list(zip(*np.where(missing)))
        if not indices:
            return False
        targets = [
            Position(
                float(self.bathymetry.x_values[x_index]),
                float(self.bathymetry.y_values[y_index]),
                self.bathymetry.vehicle_depth_at(
                    float(self.bathymetry.x_values[x_index]),
                    float(self.bathymetry.y_values[y_index]),
                ),
            )
            for y_index, x_index in indices
        ]
        ordered = sorted(survey_robots, key=lambda robot: robot.robot_id)
        cluster_count = min(len(ordered), len(targets))
        centers = [np.array([targets[0].x, targets[0].y])]
        while len(centers) < cluster_count:
            candidate = max(
                targets,
                key=lambda target: min(np.linalg.norm(np.array([target.x, target.y]) - center) for center in centers),
            )
            centers.append(np.array([candidate.x, candidate.y]))
        labels = np.zeros(len(targets), dtype=int)
        for _ in range(12):
            labels = np.array([
                int(np.argmin([np.linalg.norm(np.array([target.x, target.y]) - center) for center in centers]))
                for target in targets
            ])
            updated = []
            for cluster_index, center in enumerate(centers):
                members = [np.array([target.x, target.y]) for index, target in enumerate(targets) if labels[index] == cluster_index]
                updated.append(np.mean(members, axis=0) if members else center)
            if all(np.allclose(left, right) for left, right in zip(centers, updated)):
                break
            centers = updated
        clusters = [[target for index, target in enumerate(targets) if labels[index] == cluster] for cluster in range(cluster_count)]
        robot_subset = ordered[:cluster_count]
        best_order = min(
            permutations(range(cluster_count)),
            key=lambda order: sum(
                robot_subset[index].position.distance_to(Position(float(centers[cluster][0]), float(centers[cluster][1]), 0.0))
                for index, cluster in enumerate(order)
            ),
        )
        assignments: dict[str, list[Position]] = {robot.robot_id: [] for robot in ordered}
        for robot_index, cluster_index in enumerate(best_order):
            robot = robot_subset[robot_index]
            remaining = list(clusters[cluster_index])
            cursor = Position(robot.position.x, robot.position.y, robot.position.depth)
            while remaining:
                nearest_index = min(range(len(remaining)), key=lambda index: cursor.distance_to(remaining[index]))
                target = remaining.pop(nearest_index)
                assignments[robot.robot_id].append(target)
                cursor = target
        center = self.rendezvous_positions[self.current_survey_cycle]
        for offset, robot in enumerate(ordered):
            angle = 6.283185307179586 * offset / len(ordered)
            slot = Position(center.x + 30.0 * np.cos(angle), center.y + 30.0 * np.sin(angle), 0.0)
            self._assign_known_route(robot, assignments[robot.robot_id] + [slot])
            robot.state = RobotState.EXPLORING
        self.cleanup_passes += 1
        self.batch_arrived.clear()
        self.events.add(
            self.time,
            "mission",
            "Cooperative gap-closing pass launched",
            f"pass={self.cleanup_passes}; remaining_cells={len(indices)}",
        )
        return True

    def _begin_recovery(self) -> None:
        self.mission_phase = "RETURNING_TO_VESSEL"
        self.vessel_target = None
        for robot in self.robots.values():
            if robot.online:
                robot.home = Position(self.base.position.x, self.base.position.y, 0.0)
                self._assign_known_route(
                    robot,
                    [Position(self.base.position.x, self.base.position.y, 0.0)],
                )
                robot.state = RobotState.RETURNING_HOME
        self.events.add(self.time, "mission", "Final map secured", "All surfaced robots returning to survey vessel")

    def _complete_survey(self, survey_robots: list[Robot], courier: Robot) -> None:
        self.mission_phase = "COMPLETE"
        self.running = False
        # Physical recovery permits a full wired/high-speed offload, including
        # measurements collected after the last RF handoff.
        self.bathymetry.sync_to_base()
        for robot in self.robots.values():
            self.base.merge_telemetry_history(
                robot.robot_id,
                [sample.to_dict() for sample in robot.telemetry_history],
            )
            self._record_position_report(robot.robot_id, self._status_snapshot(robot, timestamp=self.time))
        for robot in self.robots.values():
            if robot.online:
                robot.state = RobotState.HOLDING
                robot.unsynced_samples = 0
        deepest = self.bathymetry.base_deepest_sample
        detail = f"base coverage={self.bathymetry.base_coverage:.1%}"
        if deepest:
            detail += f"; deepest={deepest.depth:.2f} m at ({deepest.x:.0f}, {deepest.y:.0f})"
        self.events.add(self.time, "mission", "Bathymetric survey complete", detail)
        self.events.add(self.time, "mission", "Dockside data offload complete", f"samples={len(self.bathymetry.base_samples)}")
        self.events.add(self.time, "mission", "All robots recovered by survey vessel")

    def _inside_obstacle(self, position: Position) -> bool:
        return any(zone["x0"] <= position.x <= zone["x1"] and zone["y0"] <= position.y <= zone["y1"] for zone in self.obstacles)

    def _status_snapshot(self, robot: Robot, *, timestamp: float) -> dict[str, Any]:
        """Status record that can be carried to the PC in a later surface sync."""
        return {
            "robot_id": robot.robot_id,
            "timestamp": timestamp,
            "x": robot.position.x,
            "y": robot.position.y,
            "depth": robot.position.depth,
            "speed": robot.speed,
            "battery": robot.battery,
            "state": robot.state.value,
            "seafloor_depth": robot.latest_bottom_depth,
            "neighbors": len(self.network.neighbors(robot.robot_id)) if robot.robot_id in self.network.nodes else 0,
            "link_quality": 0.0,
            "buffered_samples": robot.unsynced_samples,
            "gnss_available": robot.position.depth <= 0.5,
            "route_waypoint_index": robot.assigned_waypoint_index,
            "route_revision": robot.route_revision,
        }

    def _frame(
        self,
        src_id: str,
        dst_id: str,
        message_type: MessageType,
        payload: dict[str, Any],
        *,
        ack_for: str | None = None,
        key_id: int | None = None,
    ) -> PacketFrame:
        node = self.network.nodes[src_id]
        seq = node.next_sequence()
        frame = create_frame(
            mission_id=self.mission_id,
            nonce_prefix=self.nonce_prefix,
            key=node.keys.get(key_id),
            src_id=src_id,
            dst_id=dst_id,
            seq=seq,
            message_type=message_type,
            timestamp=self.time,
            payload=payload,
            ttl=self.config.default_ttl,
            ack_for=ack_for,
        )
        self.sent_frames.append(frame)
        self.sent_frames = self.sent_frames[-1000:]
        return frame

    def _send_from_robot(self, robot: Robot, message_type: MessageType, dst_id: str, payload: dict[str, Any]) -> bool:
        frame = self._frame(robot.robot_id, dst_id, message_type, payload)
        return self.network.transmit(frame, self.time, self._handle_delivery)

    def send_command(
        self, target_id: str, kind: CommandType | str, parameters: dict[str, Any] | None = None
    ) -> Command:
        command_type = kind if isinstance(kind, CommandType) else CommandType(kind)
        command = self.base.create_command(
            target_id,
            command_type,
            self.time,
            parameters,
            self.config.ack_timeout,
            self.config.max_retries,
        )
        self._send_command_attempt(command)
        return command

    def _send_command_attempt(self, command: Command) -> bool:
        command.attempts += 1
        command.last_attempt_at = self.time
        payload = {"command_id": command.command_id, "command": command.command.value, "parameters": command.parameters, "ack_requested": command.ack_requested}
        frame = self._frame("BASE", command.target_id, MessageType.COMMAND, payload)
        delivered = self.network.transmit(frame, self.time, self._handle_delivery, attempt=command.attempts)
        if delivered and command.status == CommandStatus.PENDING:
            command.status = CommandStatus.DELIVERED
        return delivered

    def _send_ack(self, src_id: str, dst_id: str, reference: str, payload: dict[str, Any], key_id: int | None = None) -> None:
        frame = self._frame(src_id, dst_id, MessageType.ACK, payload, ack_for=reference, key_id=key_id)
        self.network.transmit(frame, self.time, self._handle_delivery)

    def _handle_delivery(self, frame: PacketFrame, inner: dict[str, Any], latency: float) -> None:
        message_type = MessageType(inner["message_type"])
        payload = inner.get("payload", {})
        destination = frame.header.dst_id
        if destination == "BASE":
            if message_type == MessageType.TELEMETRY:
                # Aggregate map-sync summaries have no position and must not
                # overwrite the last known vehicle fix.
                if {"x", "y", "depth"} <= payload.keys():
                    self._record_position_report(frame.header.src_id, payload)
            elif message_type == MessageType.ACK:
                reference = inner.get("ack_for")
                if payload.get("rotation"):
                    self.base.key_rotation_status[frame.header.src_id] = True
                    self.events.add(self.time + latency, "security", "Key rotation ACK", frame.header.src_id)
                elif reference:
                    self.base.acknowledge(reference, self.time + latency)
                    self.events.add(self.time + latency, "network", "ACK received", f"{reference} via {' -> '.join(frame.path)}")
            elif message_type == MessageType.ALERT:
                self.events.add(self.time + latency, "alert", "Robot alert", f"{frame.header.src_id}: {payload}", "warning")
            return
        robot = self.robots[destination]
        if message_type == MessageType.COMMAND:
            robot.execute_command(payload["command"], payload.get("parameters", {}))
            self.events.add(self.time + latency, "command", "Command delivered", f"{payload['command']} to {destination}")
            if payload.get("ack_requested", True):
                self._send_ack(destination, "BASE", payload["command_id"], {"status": "ok", "robot_id": destination})
        elif message_type == MessageType.KEY_ROTATE:
            old_key_id = frame.header.key_id
            new_id = int(payload["key_id"])
            robot.keys.provision(base64.b64decode(payload["key_material"]), new_id)
            self.events.add(self.time + latency, "security", "Robot key updated", f"{destination} -> key_id={new_id}")
            self._send_ack(destination, "BASE", f"rotation-{new_id}", {"rotation": True, "key_id": new_id}, key_id=old_key_id)
        elif message_type == MessageType.PING:
            pong = self._frame(destination, frame.header.src_id, MessageType.PONG, {"ping": frame.packet_id})
            self.network.transmit(pong, self.time, self._handle_delivery)

    def _process_command_timeouts(self) -> None:
        for command in self.base.commands.values():
            if command.status == CommandStatus.ACKNOWLEDGED or command.last_attempt_at is None:
                continue
            if self.time - command.last_attempt_at < command.timeout:
                continue
            if command.attempts < command.max_attempts:
                command.status = CommandStatus.PENDING
                self.network.metrics.retries += 1
                self.events.add(self.time, "network", "Retransmission", f"{command.command_id} attempt {command.attempts + 1}", "warning")
                self._send_command_attempt(command)
            else:
                command.status = CommandStatus.FAILED
                self.events.add(self.time, "network", "Command failed", command.command_id, "error")

    def rotate_key(self) -> int:
        if self.config.communication_profile == CommunicationProfile.NRF24_SURFACE:
            connected = self.network.connected_to_base() - {"BASE"}
            if connected != set(self.robots):
                self.events.add(
                    self.time,
                    "security",
                    "Key rotation deferred",
                    "All robots must be surfaced inside the vessel RF mesh",
                    "warning",
                )
                return self.base.keys.current_key_id
        old_id = self.base.keys.current_key_id
        new_key = self.base.prepare_rotation(list(self.robots))
        payload = {"key_id": new_key.key_id, "key_material": base64.b64encode(new_key.master).decode()}
        self.events.add(self.time, "security", "Mission key rotation started", f"{old_id} -> {new_key.key_id}")
        for robot_id in self.robots:
            for attempt in range(1, self.config.max_retries + 1):
                frame = self._frame("BASE", robot_id, MessageType.KEY_ROTATE, payload, key_id=old_id)
                self.network.transmit(frame, self.time, self._handle_delivery, attempt=attempt)
                if self.base.key_rotation_status[robot_id]:
                    break
                if attempt < self.config.max_retries:
                    self.network.metrics.retries += 1
                    self.events.add(self.time, "security", "Key rotation retransmission", f"{robot_id} attempt {attempt + 1}", "warning")
        return new_key.key_id

    def inject_tampered_ciphertext(self, target_id: str = "R1") -> bool:
        frame = self._frame("BASE", target_id, MessageType.PING, {"attack": "ciphertext"})
        changed = bytearray(frame.ciphertext)
        changed[0] ^= 1
        tampered = replace(frame, ciphertext=bytes(changed))
        # Re-sign routing data so the exercise reaches AEAD authentication.
        import hashlib as _hashlib, hmac as _hmac
        tampered = replace(tampered, route_mac=_hmac.new(self.base.keys.get(frame.header.key_id).route, tampered.routing_data(), _hashlib.sha256).digest())
        self.events.add(self.time, "security", "Tampered ciphertext injected", target_id, "warning")
        return self.network.transmit(tampered, self.time, self._handle_delivery)

    def inject_tampered_tag(self, target_id: str = "R1") -> bool:
        frame = self._frame("BASE", target_id, MessageType.PING, {"attack": "tag"})
        changed = bytearray(frame.ciphertext)
        changed[-1] ^= 1
        tampered = replace(frame, ciphertext=bytes(changed))
        import hashlib as _hashlib, hmac as _hmac
        tampered = replace(tampered, route_mac=_hmac.new(self.base.keys.get(frame.header.key_id).route, tampered.routing_data(), _hashlib.sha256).digest())
        self.events.add(self.time, "security", "Tampered AEAD tag injected", target_id, "warning")
        return self.network.transmit(tampered, self.time, self._handle_delivery)

    def inject_invalid_route_mac(self, target_id: str = "R1") -> bool:
        frame = self._frame("BASE", target_id, MessageType.PING, {"attack": "route_mac"})
        tampered = replace(frame, route_mac=b"\x00" * len(frame.route_mac))
        self.events.add(self.time, "security", "Invalid route MAC injected", target_id, "warning")
        return self.network.transmit(tampered, self.time, self._handle_delivery)

    def replay_last_packet(self) -> bool:
        delivered_ids = {row["packet_id"] for row in self.network.packet_log if row["status"] == "delivered"}
        frame = next((candidate for candidate in reversed(self.sent_frames) if candidate.packet_id in delivered_ids), None)
        if frame is None:
            frame = self._frame("BASE", "R1", MessageType.MISSION_START, {"replay_probe": True})
            if not self.network.transmit(frame, self.time, self._handle_delivery):
                return False
        self.events.add(self.time, "security", "Old packet replayed", frame.packet_id, "warning")
        return self.network.transmit(frame, self.time, self._handle_delivery)

    def set_robot_offline(self, robot_id: str, offline: bool = True) -> None:
        robot = self.robots[robot_id]
        robot.forced_offline = offline
        if offline:
            robot.state = RobotState.OFFLINE
            self.events.add(self.time, "fault", "Robot disconnected", robot_id, "warning")
        else:
            robot.state = RobotState.EXPLORING
            self.events.add(self.time, "fault", "Robot restored", robot_id)

    def force_critical_battery(self, robot_id: str) -> None:
        self.robots[robot_id].battery = 10.0
        self.events.add(self.time, "fault", "Critical battery injected", robot_id, "warning")

    def set_leak(self, robot_id: str, leak: bool = True) -> None:
        robot = self.robots[robot_id]
        robot.leak = leak
        if leak:
            robot.state = RobotState.EMERGENCY
        self.events.add(self.time, "fault", "Leak state changed", f"{robot_id}={leak}", "warning" if leak else "info")

    def interrupt_link(self, left: str, right: str, interrupted: bool = True) -> None:
        link = frozenset((left, right))
        if interrupted:
            self.network.interrupted_links.add(link)
        else:
            self.network.interrupted_links.discard(link)
        self.events.add(self.time, "fault", "Link state changed", f"{left}<->{right} interrupted={interrupted}")

    def isolate_robot(self, robot_id: str) -> None:
        for neighbor in self.network.neighbors(robot_id):
            self.network.interrupted_links.add(frozenset((robot_id, neighbor)))
        self.events.add(self.time, "fault", "Robot isolated from mesh", robot_id, "warning")

    def restore_all_links(self) -> None:
        self.network.interrupted_links.clear()
        self.events.add(self.time, "fault", "All interrupted links restored")

    def robot_rows(self) -> list[dict[str, Any]]:
        connected = self.network.connected_to_base()
        rows: list[dict[str, Any]] = []
        for robot in self.robots.values():
            report = self.base.telemetry_by_robot.get(robot.robot_id, {})
            report_time = report.get("timestamp")
            age = self.time - float(report_time) if report_time is not None else None
            live = robot.robot_id in connected and age is not None and age <= max(2.0, robot.telemetry_interval + 1.0)
            if not self.deployed:
                position_status = "ON DECK"
            elif live:
                position_status = "LIVE RF"
            else:
                position_status = "LAST KNOWN"
            estimate, uncertainty = self.estimated_position(robot.robot_id)
            rows.append({
                "robot_id": robot.robot_id,
                "role": robot.role,
                "is_data_mule": robot.robot_id == self.courier_id and self.mission_phase == "SYNCING_WITH_VESSEL",
                "deployed": robot.deployed,
                "state": report.get("state", "UNKNOWN"),
                "x": report.get("x"),
                "y": report.get("y"),
                "depth": report.get("depth"),
                "battery": report.get("battery"),
                "speed": report.get("speed"),
                "neighbors": report.get("neighbors"),
                "connected": live,
                "position_status": position_status,
                "position_age_s": age,
                "estimated_x": estimate.x,
                "estimated_y": estimate.y,
                "estimated_depth": estimate.depth,
                "estimate_uncertainty_m": uncertainty,
                "last_contact": report_time,
                "key_id": robot.keys.current_key_id,
                "seafloor_depth": report.get("seafloor_depth"),
                "route_progress": report.get("route_progress"),
                "buffered_samples": report.get("buffered_samples"),
                "operational_idle_s": robot.operational_idle_seconds,
            })
        return rows

    def estimated_position(self, robot_id: str) -> tuple[Position, float]:
        """Propagate the vessel's last fix along the known plan without truth access."""
        robot = self.robots[robot_id]
        report = self.base.telemetry_by_robot.get(robot_id, {})
        report_position = Position(
            float(report.get("x", self.base.position.x)),
            float(report.get("y", self.base.position.y)),
            float(report.get("depth", 0.0)),
        )
        report_timestamp = float(report.get("timestamp", self.time))
        anchor = self.estimator_anchors.get(robot_id)
        report_matches_plan = int(report.get("route_revision", -1)) == robot.route_revision
        anchor_matches_plan = anchor is not None and int(anchor["route_revision"]) == robot.route_revision
        use_report = report_matches_plan and (
            not anchor_matches_plan
            or report_timestamp > float(anchor.get("accepted_report_timestamp", -1.0))
        )
        if use_report:
            position = report_position
            timestamp = report_timestamp
            start_index = int(report.get("route_waypoint_index", 0))
            starting_uncertainty = 3.0
            speed = max(0.0, float(report.get("speed", robot.speed) or robot.speed))
        elif anchor_matches_plan:
            anchor_position = anchor["position"]
            position = Position(anchor_position.x, anchor_position.y, anchor_position.depth)
            timestamp = float(anchor["timestamp"])
            start_index = int(anchor.get("route_waypoint_index", 0))
            starting_uncertainty = float(anchor.get("uncertainty", 3.0))
            speed = max(0.0, float(anchor.get("speed", robot.speed)))
        else:
            # Compatibility fallback for missions created before estimator
            # anchors existed. It is replaced at the next vessel-known replan.
            position = report_position
            timestamp = report_timestamp
            start_index = 0
            starting_uncertainty = 3.0
            speed = max(0.0, float(report.get("speed", robot.speed) or robot.speed))

        age = max(0.0, self.time - timestamp)
        travel_budget = speed * age
        if robot.assigned_waypoints:
            start_index = min(max(0, start_index), len(robot.assigned_waypoints))
            planned_targets = robot.assigned_waypoints[start_index:]
        elif robot.waypoint is not None:
            # Courier and recovery targets are commands issued by the vessel,
            # therefore they are known even when progress is not.
            planned_targets = [robot.waypoint]
        else:
            planned_targets = []

        travelled = 0.0
        for target in planned_targets:
            segment = position.distance_to(target)
            if segment <= 1e-9:
                position = Position(target.x, target.y, target.depth)
                continue
            step = min(travel_budget, segment)
            ratio = step / segment
            position = Position(
                position.x + (target.x - position.x) * ratio,
                position.y + (target.y - position.y) * ratio,
                position.depth + (target.depth - position.depth) * ratio,
            )
            travel_budget -= step
            travelled += step
            if travel_budget <= 1e-9:
                break
        # Illustrative 2-sigma envelope: initial fix error + plan/speed drift.
        # It is deliberately labelled as an estimate, not a containment bound.
        uncertainty = min(
            (self.config.width**2 + self.config.height**2) ** 0.5,
            starting_uncertainty + 0.03 * travelled + 0.05 * age,
        )
        return position, uncertainty

    def _assign_known_route(self, robot: Robot, waypoints: list[Position]) -> None:
        """Issue a vessel-known route without discontinuity in its PC estimate."""
        anchor_position, uncertainty = self.estimated_position(robot.robot_id)
        robot.assign_route(waypoints)
        self.estimator_anchors[robot.robot_id] = {
            "timestamp": self.time,
            "position": Position(anchor_position.x, anchor_position.y, anchor_position.depth),
            "route_revision": robot.route_revision,
            "route_waypoint_index": 0,
            "uncertainty": uncertainty,
            "speed": robot.speed,
            "accepted_report_timestamp": float(
                self.base.telemetry_by_robot.get(robot.robot_id, {}).get("timestamp", -1.0)
            ),
        }

    def _record_position_report(self, robot_id: str, payload: dict[str, Any]) -> None:
        """Assimilate a received fix without drawing it as physical motion."""
        robot = self.robots[robot_id]
        predicted, uncertainty = self.estimated_position(robot_id)
        self.base.record_telemetry(robot_id, payload)
        if int(payload.get("route_revision", -1)) != robot.route_revision:
            return
        measured = Position(float(payload["x"]), float(payload["y"]), float(payload["depth"]))
        correction_distance = predicted.distance_to(measured)
        max_correction = max(
            0.5,
            robot.speed * self.config.tick_seconds * self.config.simulation_speed,
        )
        ratio = min(1.0, max_correction / correction_distance) if correction_distance > 1e-9 else 1.0
        corrected = Position(
            predicted.x + (measured.x - predicted.x) * ratio,
            predicted.y + (measured.y - predicted.y) * ratio,
            predicted.depth + (measured.depth - predicted.depth) * ratio,
        )
        self.estimator_anchors[robot_id] = {
            "timestamp": self.time,
            "position": corrected,
            "route_revision": robot.route_revision,
            "route_waypoint_index": int(payload.get("route_waypoint_index", 0)),
            "uncertainty": max(2.0, min(uncertainty, 3.0 + correction_distance)),
            "speed": max(0.0, float(payload.get("speed", robot.speed) or robot.speed)),
            "accepted_report_timestamp": float(payload.get("timestamp", self.time)),
        }

    def pc_position(self, robot_id: str) -> Position:
        report = self.base.telemetry_by_robot.get(robot_id, {})
        return Position(float(report.get("x", self.base.position.x)), float(report.get("y", self.base.position.y)), float(report.get("depth", 0.0)))

    def pc_topology_links(self) -> list[dict[str, Any]]:
        """Return only links whose endpoints have current vessel-visible fixes."""
        live = {"BASE"} | {
            row["robot_id"] for row in self.robot_rows() if row["position_status"] == "LIVE RF"
        }
        visible: list[dict[str, Any]] = []
        for link in self.network.topology_links():
            if link["source"] not in live or link["target"] not in live:
                continue
            left = self.base.position if link["source"] == "BASE" else self.pc_position(link["source"])
            right = self.base.position if link["target"] == "BASE" else self.pc_position(link["target"])
            distance = left.distance_to(right)
            visible.append({**link, "distance": distance, "quality": self.network.transport.quality(distance)})
        return visible

    def summary(self) -> dict[str, Any]:
        connected = self.network.connected_to_base()
        active = [robot for robot in self.robots.values() if robot.online]
        security = [self.base.security] + [robot.security for robot in self.robots.values()]
        operational_idle = sum(robot.operational_idle_seconds for robot in self.robots.values())
        available_work_time = self.time * len(self.robots)
        return {
            "mission_time": self.time,
            "mission_phase": self.mission_phase,
            "deployed": self.deployed,
            "survey_coverage": self.bathymetry.base_coverage,
            "onboard_coverage": self.bathymetry.coverage,
            "deepest_observed": self.bathymetry.base_deepest_sample.depth if self.bathymetry.base_deepest_sample else None,
            "onboard_deepest": self.bathymetry.deepest_sample.depth if self.bathymetry.deepest_sample else None,
            "data_syncs": self.data_sync_count,
            "buffered_samples": sum(robot.unsynced_samples for robot in self.robots.values()),
            "depth_limit": self.config.maximum_operating_depth,
            "depth_minimum": self.config.minimum_operating_depth,
            "battery_capacity_ah": self.config.battery_capacity_ah,
            "nominal_voltage": self.config.nominal_voltage,
            "mean_motor_current": self.config.mean_motor_current,
            "ideal_motor_endurance_hours": self.config.battery_capacity_ah / self.config.mean_motor_current,
            "operational_idle_seconds": operational_idle,
            "productive_utilization": 1.0 - operational_idle / available_work_time if available_work_time else 1.0,
            "data_mule_history": list(self.data_mule_history),
            "fleet_backbone_history": [list(members) for members in self.fleet_backbone_history],
            "active_robots": len(active),
            "connected_robots": len(connected - {"BASE"}),
            "offline_robots": len(self.robots) - len(active),
            "packets_sent": self.network.metrics.packets_sent,
            "packets_delivered": self.network.metrics.packets_delivered,
            "delivery_rate": self.network.metrics.delivery_rate,
            "average_hops": self.network.metrics.average_hops,
            "average_latency": self.network.metrics.average_latency,
            "relays": self.network.metrics.relays,
            "retries": self.network.metrics.retries,
            "authentication_failures": sum(item.authentication_failures for item in security),
            "invalid_route_mac": sum(item.invalid_route_mac for item in security),
            "replay_drops": sum(item.replay_drops for item in security),
            "duplicate_drops": sum(item.duplicate_drops for item in security),
            "decrypt_success": sum(item.decrypt_success for item in security),
            "average_battery": sum(robot.battery for robot in self.robots.values()) / len(self.robots),
            "key_id": self.base.keys.current_key_id,
            "fingerprint": self.base.keys.get().fingerprint,
            "nonces_generated": sum(node.sequence for node in [self.base, *self.robots.values()]),
        }

    def export(self, output_dir: str = "exports") -> dict[str, Any]:
        return export_mission(self, output_dir)
