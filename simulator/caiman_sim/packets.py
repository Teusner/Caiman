"""Serializable encrypted packet and mutable authenticated relay frame."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import asdict, dataclass, replace
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from .crypto_layer import KeyMaterial, build_nonce
from .compact_protocol import build_wire_frames, rewrite_route
from .models import MessageType


def canonical_json(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class ImmutableHeader:
    version: int
    mission_id: str
    key_id: int
    src_id: str
    dst_id: str
    seq: int

    def aad(self) -> bytes:
        return canonical_json(asdict(self))


@dataclass(frozen=True)
class PacketFrame:
    header: ImmutableHeader
    previous_hop: str
    ttl: int
    initial_ttl: int
    hop_count: int
    packet_id: str
    nonce: bytes
    ciphertext: bytes
    route_mac: bytes
    path: tuple[str, ...]
    wire_frames: tuple[bytes, ...] = ()
    wire_payload_bytes: int = 0
    wire_ciphertext_bytes: int = 0

    @property
    def size_bytes(self) -> int:
        return len(self.nonce) + len(self.ciphertext) + len(self.route_mac) + len(self.header.aad()) + 48

    @property
    def wire_size_bytes(self) -> int:
        return sum(len(frame) for frame in self.wire_frames) or self.size_bytes

    @property
    def fragment_count(self) -> int:
        return len(self.wire_frames) or 1

    def routing_data(self) -> bytes:
        return canonical_json(
            {
                "packet_id": self.packet_id,
                "previous_hop": self.previous_hop,
                "ttl": self.ttl,
                "initial_ttl": self.initial_ttl,
                "hop_count": self.hop_count,
                "path": list(self.path),
                "header": asdict(self.header),
                "ciphertext_hash": hashlib.sha256(self.ciphertext).hexdigest(),
            }
        )

    def verify_route(self, key: KeyMaterial) -> bool:
        expected = hmac.new(key.route, self.routing_data(), hashlib.sha256).digest()
        return hmac.compare_digest(expected, self.route_mac)

    def forwarded(self, relay_id: str, key: KeyMaterial) -> "PacketFrame":
        if self.ttl <= 0:
            raise ValueError("cannot forward a frame with exhausted TTL")
        updated = replace(
            self,
            previous_hop=relay_id,
            ttl=self.ttl - 1,
            hop_count=self.hop_count + 1,
            path=self.path + (relay_id,),
            route_mac=b"",
        )
        return replace(
            updated,
            route_mac=hmac.new(key.route, updated.routing_data(), hashlib.sha256).digest(),
            wire_frames=rewrite_route(self.wire_frames, updated.ttl, updated.hop_count, key.route),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "header": asdict(self.header),
            "previous_hop": self.previous_hop,
            "ttl": self.ttl,
            "initial_ttl": self.initial_ttl,
            "hop_count": self.hop_count,
            "packet_id": self.packet_id,
            "nonce": base64.b64encode(self.nonce).decode(),
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "route_mac": base64.b64encode(self.route_mac).decode(),
            "path": list(self.path),
            "wire_frames": [base64.b64encode(frame).decode() for frame in self.wire_frames],
        }


def create_frame(
    *,
    mission_id: str,
    nonce_prefix: bytes,
    key: KeyMaterial,
    src_id: str,
    dst_id: str,
    seq: int,
    message_type: MessageType,
    timestamp: float,
    payload: dict[str, Any],
    ttl: int = 8,
    ack_for: str | None = None,
) -> PacketFrame:
    if ttl < 0:
        raise ValueError("TTL cannot be negative")
    header = ImmutableHeader(1, mission_id, key.key_id, src_id, dst_id, seq)
    inner = {
        "message_type": message_type.value,
        "created_at": timestamp,
        "payload": payload,
        "ack_for": ack_for,
    }
    nonce = build_nonce(nonce_prefix, src_id, seq)
    ciphertext = ChaCha20Poly1305(key.enc).encrypt(nonce, canonical_json(inner), header.aad())
    wire_frames, wire_payload_bytes, wire_ciphertext_bytes = build_wire_frames(
        key=key, nonce=nonce, src_id=src_id, dst_id=dst_id, seq=seq,
        message_type=message_type, timestamp=timestamp, payload=payload, ttl=ttl, ack_for=ack_for,
    )
    unsigned = PacketFrame(
        header=header,
        previous_hop=src_id,
        ttl=ttl,
        initial_ttl=ttl,
        hop_count=0,
        packet_id=uuid.uuid5(uuid.NAMESPACE_URL, f"{mission_id}/{src_id}/{seq}").hex[:16],
        nonce=nonce,
        ciphertext=ciphertext,
        route_mac=b"",
        path=(src_id,),
        wire_frames=wire_frames,
        wire_payload_bytes=wire_payload_bytes,
        wire_ciphertext_bytes=wire_ciphertext_bytes,
    )
    return replace(unsigned, route_mac=hmac.new(key.route, unsigned.routing_data(), hashlib.sha256).digest())


def decrypt_frame(frame: PacketFrame, key: KeyMaterial) -> dict[str, Any]:
    """Authenticate and decrypt, translating only AEAD failures."""
    try:
        plaintext = ChaCha20Poly1305(key.enc).decrypt(frame.nonce, frame.ciphertext, frame.header.aad())
    except InvalidTag as exc:
        raise ValueError("packet authentication failed") from exc
    result = json.loads(plaintext.decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("invalid encrypted payload")
    return result
