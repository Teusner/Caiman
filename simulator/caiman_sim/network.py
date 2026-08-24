"""Distance-limited controlled flooding over abstract underwater transports."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import replace
from typing import Any, Callable, Protocol

import numpy as np

from .config import CommunicationProfile, SimulationConfig
from .models import NetworkMetrics, Position, RobotState
from .packets import PacketFrame, decrypt_frame


class NetworkNode(Protocol):
    position: Position
    keys: Any
    replay: Any
    security: Any
    last_packet_received: float | None

    @property
    def online(self) -> bool: ...


class TransportModel(ABC):
    """Replaceable link abstraction for simulated, UDP, serial or hardware transports."""

    @abstractmethod
    def quality(self, distance: float) -> float: ...

    @abstractmethod
    def latency(self, distance: float, size_bytes: int, rng: np.random.Generator) -> float: ...

    @abstractmethod
    def packet_lost(self, distance: float, size_bytes: int, rng: np.random.Generator) -> bool: ...


class UnderwaterTransport(TransportModel):
    def __init__(self, config: SimulationConfig) -> None:
        self.config = config

    def quality(self, distance: float) -> float:
        ratio = min(1.0, distance / self.config.communication_range)
        return max(0.0, 1.0 - ratio**1.7)

    def latency(self, distance: float, size_bytes: int, rng: np.random.Generator) -> float:
        acoustic = self.config.communication_profile in {
            CommunicationProfile.ACOUSTIC_OOK,
            CommunicationProfile.ACOUSTIC_BFSK,
        }
        propagation = distance / 1500.0 if acoustic else distance / 200_000_000.0
        transmission = size_bytes * 8.0 / float(self.config.bitrate)
        jitter = max(0.0, float(rng.normal(0.0, float(self.config.jitter))))
        return float(self.config.base_latency) + propagation + transmission + jitter

    def packet_lost(self, distance: float, size_bytes: int, rng: np.random.Generator) -> bool:
        ratio = min(1.0, distance / self.config.communication_range)
        probability = min(0.98, float(self.config.packet_loss) * (0.4 + 0.9 * ratio**2))
        if self.config.communication_profile == CommunicationProfile.NRF24_SURFACE:
            # The firmware uses 32-byte nRF payloads and hardware Auto-ACK/retry.
            fragments = max(1, math.ceil(size_bytes / 32))
            residual_fragment_loss = probability * 0.15
            probability = 1.0 - (1.0 - residual_fragment_loss) ** fragments
        return bool(rng.random() < probability)


class Network:
    """Synchronous event abstraction; a call returns the modeled delivery latency."""

    def __init__(self, config: SimulationConfig, rng: np.random.Generator) -> None:
        self.config = config
        self.rng = rng
        self.transport: TransportModel = UnderwaterTransport(config)
        self.nodes: dict[str, NetworkNode] = {}
        self.metrics = NetworkMetrics()
        self.packet_log: list[dict[str, Any]] = []
        self.recent_routes: list[dict[str, Any]] = []
        self.interrupted_links: set[frozenset[str]] = set()
        self.forwarded_cache: set[tuple[str, str, int]] = set()

    def register(self, node_id: str, node: NetworkNode) -> None:
        self.nodes[node_id] = node

    def neighbors(self, node_id: str) -> list[str]:
        source = self.nodes[node_id]
        if not source.online:
            return []
        result: list[str] = []
        for other_id, other in self.nodes.items():
            if other_id == node_id or not other.online:
                continue
            if frozenset((node_id, other_id)) in self.interrupted_links:
                continue
            if self.config.communication_profile == CommunicationProfile.NRF24_SURFACE:
                if source.position.depth > 0.5 or other.position.depth > 0.5:
                    continue
            if source.position.distance_to(other.position) <= self.config.communication_range:
                result.append(other_id)
        return sorted(result)

    def topology_links(self) -> list[dict[str, Any]]:
        links: list[dict[str, Any]] = []
        ids = sorted(self.nodes)
        for index, left in enumerate(ids):
            for right in ids[index + 1 :]:
                if right in self.neighbors(left):
                    distance = self.nodes[left].position.distance_to(self.nodes[right].position)
                    links.append({"source": left, "target": right, "distance": distance, "quality": self.transport.quality(distance)})
        return links

    def connected_to_base(self) -> set[str]:
        seen = {"BASE"}
        queue = deque(["BASE"])
        while queue:
            current = queue.popleft()
            for neighbor in self.neighbors(current):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        return seen

    def transmit(
        self,
        frame: PacketFrame,
        now: float,
        on_delivery: Callable[[PacketFrame, dict[str, Any], float], None],
        *,
        attempt: int = 1,
    ) -> bool:
        """Flood a frame and call the destination handler once on valid delivery."""
        self.metrics.packets_sent += 1
        if frame.header.src_id not in self.nodes or frame.header.dst_id not in self.nodes:
            self._log(frame, now, "failed", "unknown node", 0.0, attempt)
            return False
        if not self.nodes[frame.header.src_id].online:
            self._log(frame, now, "failed", "source offline", 0.0, attempt)
            return False

        queue: deque[tuple[str, PacketFrame, float]] = deque([(frame.header.src_id, frame, 0.0)])
        visited_this_flood: set[tuple[str, str, int]] = set()
        while queue:
            sender_id, outgoing, elapsed = queue.popleft()
            for receiver_id in self.neighbors(sender_id):
                cache_key = (receiver_id, outgoing.header.src_id, outgoing.header.seq)
                if cache_key in visited_this_flood:
                    continue
                visited_this_flood.add(cache_key)
                receiver = self.nodes[receiver_id]
                distance = self.nodes[sender_id].position.distance_to(receiver.position)
                wire_size = outgoing.wire_size_bytes if self.config.communication_profile == CommunicationProfile.NRF24_SURFACE else outgoing.size_bytes
                hop_latency = self.transport.latency(distance, wire_size, self.rng)
                arrival_latency = elapsed + hop_latency
                if self.transport.packet_lost(distance, wire_size, self.rng):
                    self.metrics.packets_lost += 1
                    self._log(outgoing, now, "lost", f"link loss {sender_id}->{receiver_id}", arrival_latency, attempt)
                    continue
                try:
                    route_key = receiver.keys.get(outgoing.header.key_id)
                except KeyError:
                    receiver.security.invalid_route_mac += 1
                    self._log(outgoing, now, "dropped", "unknown key id", arrival_latency, attempt)
                    continue
                if not outgoing.verify_route(route_key):
                    receiver.security.invalid_route_mac += 1
                    self._log(outgoing, now, "dropped", "invalid route MAC", arrival_latency, attempt)
                    continue
                if outgoing.ttl <= 0:
                    receiver.security.ttl_drops += 1
                    self._log(outgoing, now, "dropped", "TTL exhausted", arrival_latency, attempt)
                    continue
                if receiver_id == outgoing.header.dst_id:
                    replay_result = receiver.replay.check(outgoing.header.src_id, outgoing.header.seq)
                    if replay_result == "duplicate":
                        receiver.security.duplicate_drops += 1
                        self._log(outgoing, now, "dropped", "duplicate packet", arrival_latency, attempt)
                        return False
                    if replay_result == "replay":
                        receiver.security.replay_drops += 1
                        self._log(outgoing, now, "dropped", "replay outside window", arrival_latency, attempt)
                        return False
                    try:
                        inner = decrypt_frame(outgoing, route_key)
                    except ValueError:
                        receiver.security.authentication_failures += 1
                        self._log(outgoing, now, "dropped", "authentication failure", arrival_latency, attempt)
                        return False
                    receiver.replay.accept(outgoing.header.src_id, outgoing.header.seq)
                    receiver.security.decrypt_success += 1
                    receiver.last_packet_received = now + arrival_latency
                    delivered = replace(
                        outgoing,
                        previous_hop=sender_id,
                        hop_count=outgoing.hop_count + 1,
                        path=outgoing.path + (receiver_id,),
                    )
                    self.metrics.packets_delivered += 1
                    self.metrics.total_hops += delivered.hop_count
                    self.metrics.total_latency += arrival_latency
                    self.recent_routes.append({"packet_id": delivered.packet_id, "path": list(delivered.path), "latency": arrival_latency})
                    self.recent_routes = self.recent_routes[-30:]
                    self._log(delivered, now, "delivered", "", arrival_latency, attempt, inner.get("message_type"))
                    on_delivery(delivered, inner, arrival_latency)
                    return True
                if outgoing.ttl <= 1:
                    receiver.security.ttl_drops += 1
                    self._log(outgoing, now, "dropped", "TTL exhausted before relay", arrival_latency, attempt)
                    continue
                persistent_key = (receiver_id, outgoing.header.src_id, outgoing.header.seq)
                if persistent_key in self.forwarded_cache:
                    receiver.security.duplicate_drops += 1
                    continue
                self.forwarded_cache.add(persistent_key)
                forwarded = outgoing.forwarded(receiver_id, route_key)
                self.metrics.relays += 1
                if hasattr(receiver, "state") and receiver.state == RobotState.EXPLORING:
                    receiver.state = RobotState.RELAYING
                self._log(forwarded, now, "relayed", "", arrival_latency, attempt)
                queue.append((receiver_id, forwarded, arrival_latency))
        self._log(frame, now, "failed", "no route or all copies lost", 0.0, attempt)
        return False

    def _log(
        self,
        frame: PacketFrame,
        now: float,
        status: str,
        reason: str,
        latency: float,
        attempt: int,
        message_type: str | None = None,
    ) -> None:
        self.packet_log.append(
            {
                "timestamp": now,
                "packet_id": frame.packet_id,
                "type": message_type or "RELAY" if status == "relayed" else message_type or "ENCRYPTED",
                "src": frame.header.src_id,
                "dst": frame.header.dst_id,
                "previous_hop": frame.previous_hop,
                "path": " -> ".join(frame.path),
                "seq": frame.header.seq,
                "initial_ttl": frame.initial_ttl,
                "ttl": frame.ttl,
                "hops": frame.hop_count,
                "logical_size": frame.size_bytes,
                "size": frame.wire_size_bytes if self.config.communication_profile == CommunicationProfile.NRF24_SURFACE else frame.size_bytes,
                "payload_bytes": frame.wire_payload_bytes,
                "ciphertext_bytes": frame.wire_ciphertext_bytes,
                "fragments": frame.fragment_count if self.config.communication_profile == CommunicationProfile.NRF24_SURFACE else 1,
                "encrypted": True,
                "key_id": frame.header.key_id,
                "status": status,
                "drop_reason": reason,
                "latency": latency,
                "attempt": attempt,
            }
        )
        self.packet_log = self.packet_log[-5000:]
