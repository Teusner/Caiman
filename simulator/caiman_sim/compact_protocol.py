"""Compact, independently authenticated 32-byte nRF24 wire frames."""

from __future__ import annotations

import hashlib
import json
import math
import struct
import zlib
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from .crypto_layer import KeyMaterial
from .models import MessageType


FRAME_BYTES = 32
HEADER_BYTES = 8
CHUNK_BYTES = 8
AEAD_TAG_BYTES = 16
MAX_FRAGMENTS = 16

MESSAGE_CODES = {
    MessageType.TELEMETRY: 0, MessageType.COMMAND: 1, MessageType.ACK: 2,
    MessageType.PING: 3, MessageType.PONG: 4, MessageType.ALERT: 5,
    MessageType.KEY_ROTATE: 6, MessageType.MISSION_START: 7, MessageType.MISSION_STOP: 8,
}


def _node_code(node_id: str) -> int:
    if node_id == "BASE":
        return 0
    if node_id.startswith("R") and node_id[1:].isdigit():
        return min(254, int(node_id[1:]))
    return 255


def _clamp(value: Any, scale: float, maximum: int) -> int:
    return max(0, min(maximum, int(round(float(value or 0.0) * scale))))


def _telemetry_payload(payload: dict[str, Any]) -> bytes:
    """Pack navigation essentials into 64 bits without weakening the AEAD tag."""
    fields = (
        (_clamp(payload.get("x"), 10, 0x3FFF), 14),
        (_clamp(payload.get("y"), 10, 0x3FFF), 14),
        (_clamp(payload.get("depth"), 100, 0x7FF), 11),
        (_clamp(payload.get("seafloor_depth"), 100, 0x7FF), 11),
        (_clamp(payload.get("battery"), 2, 0xFF), 8),
        (_clamp(payload.get("link_quality"), 15, 0x0F), 4),
        (1 if payload.get("leak") else 0, 1),
        (1 if payload.get("gnss_available") else 0, 1),
    )
    packed = 0
    for value, bits in fields:
        packed = (packed << bits) | value
    return packed.to_bytes(8, "big")


def _compact_payload(message_type: MessageType, payload: dict[str, Any], ack_for: str | None) -> bytes:
    if message_type == MessageType.TELEMETRY and {"x", "y", "depth", "battery"} <= payload.keys():
        return _telemetry_payload(payload)
    if message_type == MessageType.TELEMETRY:
        return struct.pack(
            ">BHHHH", 1,
            _clamp(payload.get("map_revision", payload.get("cycle", 0)), 1, 0xFFFF),
            _clamp(float(payload.get("onboard_coverage", 0)), 10_000, 0xFFFF),
            _clamp(payload.get("mapped_cells", payload.get("buffered_samples", 0)), 1, 0xFFFF),
            _clamp(payload.get("deepest"), 100, 0xFFFF),
        )
    if message_type == MessageType.MISSION_START:
        role = 1 if payload.get("role") == "COURIER" else 0
        region_hash = hashlib.blake2s(json.dumps(payload.get("survey_region", []), sort_keys=True).encode(), digest_size=4).digest()
        return struct.pack(
            ">BBBBH4s", role,
            _clamp(payload.get("depth_min"), 1, 0xFF),
            _clamp(payload.get("depth_limit"), 1, 0xFF),
            _clamp(payload.get("next_cycle"), 1, 0xFF),
            _clamp(payload.get("map_revision"), 1, 0xFFFF), region_hash,
        )
    if message_type == MessageType.ACK:
        reference = hashlib.blake2s((ack_for or str(payload.get("command_id", ""))).encode(), digest_size=6).digest()
        status = 1 if str(payload.get("status", "")).lower() in {"ok", "acknowledged", "success"} else 0
        return bytes((status, int(payload.get("key_id", 0)) & 0xFF)) + reference

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    compressed = zlib.compress(encoded, level=9)
    body = b"\x80" + compressed if len(compressed) < len(encoded) else b"\x00" + encoded
    if len(body) > MAX_FRAGMENTS * CHUNK_BYTES:
        raise ValueError("compact payload exceeds the 16-frame nRF24 message limit")
    return body


def _fragment_nonce(nonce: bytes, seq: int, fragment_index: int) -> bytes:
    # mission prefix(4) + source(2) + message sequence(5) + fragment(1)
    return nonce[:6] + seq.to_bytes(5, "big") + bytes((fragment_index,))


def build_wire_frames(
    *, key: KeyMaterial, nonce: bytes, src_id: str, dst_id: str, seq: int,
    message_type: MessageType, timestamp: float, payload: dict[str, Any], ttl: int,
    ack_for: str | None = None,
) -> tuple[tuple[bytes, ...], int, int]:
    del timestamp, ttl  # ordering comes from seq; hop limits are local mesh policy
    if not 0 <= seq < 2**24:
        raise ValueError("nRF24 wire sequence must fit in 24 bits")
    plaintext = _compact_payload(message_type, payload, ack_for)
    fragments = max(1, math.ceil(len(plaintext) / CHUNK_BYTES))
    control = (1 << 6) | (MESSAGE_CODES[message_type] << 2) | (2 if ack_for else 0) | 1
    common = bytes((control, _node_code(src_id), _node_code(dst_id))) + seq.to_bytes(3, "big")
    frames: list[bytes] = []
    for index in range(fragments):
        chunk = plaintext[index * CHUNK_BYTES : (index + 1) * CHUNK_BYTES]
        valid_bytes = len(chunk)
        padded = chunk.ljust(CHUNK_BYTES, b"\x00")
        fragment = ((index & 0x0F) << 4) | ((fragments - 1) & 0x0F)
        header = common + bytes((fragment, valid_bytes))
        protected = ChaCha20Poly1305(key.enc).encrypt(_fragment_nonce(nonce, seq, index), padded, header)
        frames.append(header + protected)
    return tuple(frames), len(plaintext), fragments * (CHUNK_BYTES + AEAD_TAG_BYTES)


def rewrite_route(frames: tuple[bytes, ...], ttl: int, hop_count: int, route_key: bytes) -> tuple[bytes, ...]:
    """Wire frames are immutable; relays only cache and retransmit them."""
    del ttl, hop_count, route_key
    return frames


def frame_layout() -> list[dict[str, Any]]:
    return [
        {"bytes": "0", "size": 1, "field": "Control", "content": "version(2) | type(4) | ACK | encrypted"},
        {"bytes": "1", "size": 1, "field": "Source", "content": "BASE=0, R1..Rn=1..n"},
        {"bytes": "2", "size": 1, "field": "Destination", "content": "numeric node ID"},
        {"bytes": "3–5", "size": 3, "field": "Sequence", "content": "monotonic uint24 / replay protection"},
        {"bytes": "6", "size": 1, "field": "Fragment", "content": "index(4) | count-1(4)"},
        {"bytes": "7", "size": 1, "field": "Valid bytes", "content": "useful bytes in encrypted block (0–8)"},
        {"bytes": "8–15", "size": 8, "field": "Ciphertext", "content": "compact encrypted payload"},
        {"bytes": "16–31", "size": 16, "field": "AEAD tag", "content": "full Poly1305 128-bit authentication tag"},
    ]


def decode_frame_header(frame: bytes) -> dict[str, Any]:
    if len(frame) != FRAME_BYTES:
        raise ValueError("nRF24 frame must contain exactly 32 bytes")
    control = frame[0]
    return {
        "version": control >> 6, "type_code": (control >> 2) & 0x0F,
        "ack": bool(control & 2), "encrypted": bool(control & 1),
        "src": frame[1], "dst": frame[2], "seq": int.from_bytes(frame[3:6], "big"),
        "fragment_index": frame[6] >> 4, "fragment_count": (frame[6] & 0x0F) + 1,
        "valid_payload_bytes": frame[7], "ciphertext_hex": frame[8:16].hex(),
        "aead_tag_hex": frame[16:32].hex(),
    }
