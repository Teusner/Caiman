"""Mission group-key derivation, AEAD and replay protection."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def _derive(master: bytes, mission_id: str, label: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=mission_id.encode("utf-8"), info=b"caiman/" + label
    ).derive(master)


@dataclass(frozen=True)
class KeyMaterial:
    key_id: int
    master: bytes
    enc: bytes
    route: bytes
    fingerprint_key: bytes

    @classmethod
    def create(cls, mission_id: str, key_id: int = 1, master: bytes | None = None) -> "KeyMaterial":
        raw = master if master is not None else secrets.token_bytes(32)
        if len(raw) != 32:
            raise ValueError("K_mission must contain exactly 32 bytes")
        return cls(
            key_id=key_id,
            master=raw,
            enc=_derive(raw, mission_id, b"encryption"),
            route=_derive(raw, mission_id, b"routing"),
            fingerprint_key=_derive(raw, mission_id, b"fingerprint"),
        )

    @property
    def fingerprint(self) -> str:
        return hmac.new(self.fingerprint_key, b"key-id", hashlib.sha256).hexdigest()[:16]


class KeyStore:
    """Node-local key ring; old keys remain available during rotation grace."""

    def __init__(self, mission_id: str) -> None:
        self.mission_id = mission_id
        self.keys: dict[int, KeyMaterial] = {}
        self.current_key_id = 0

    def provision(self, master: bytes, key_id: int) -> KeyMaterial:
        material = KeyMaterial.create(self.mission_id, key_id, master)
        self.keys[key_id] = material
        self.current_key_id = max(self.current_key_id, key_id)
        return material

    def get(self, key_id: int | None = None) -> KeyMaterial:
        selected = self.current_key_id if key_id is None else key_id
        if selected not in self.keys:
            raise KeyError(f"unknown key_id {selected}")
        return self.keys[selected]


def source_numeric_id(src_id: str) -> int:
    if src_id == "BASE":
        return 0
    if src_id.startswith("R") and src_id[1:].isdigit():
        return int(src_id[1:]) & 0xFFFF
    return int.from_bytes(hashlib.sha256(src_id.encode()).digest()[:2], "big")


def build_nonce(prefix: bytes, src_id: str, sequence_number: int) -> bytes:
    """Build the deterministic 4+2+6 byte nonce required by the protocol."""
    if len(prefix) != 4:
        raise ValueError("mission nonce prefix must be four bytes")
    if not 0 <= sequence_number < 2**48:
        raise ValueError("sequence number is outside the 48-bit nonce range")
    return prefix + source_numeric_id(src_id).to_bytes(2, "big") + sequence_number.to_bytes(6, "big")


class ReplayWindow:
    """Bounded per-source sliding window with duplicate and stale distinction."""

    def __init__(self, window_size: int = 256) -> None:
        self.window_size = window_size
        self.highest: dict[str, int] = {}
        self.seen: set[tuple[str, int]] = set()

    def check(self, src_id: str, seq: int) -> str:
        key = (src_id, seq)
        if key in self.seen:
            return "duplicate"
        high = self.highest.get(src_id, -1)
        if high >= 0 and seq <= high - self.window_size:
            return "replay"
        return "accept"

    def accept(self, src_id: str, seq: int) -> str:
        result = self.check(src_id, seq)
        if result != "accept":
            return result
        self.seen.add((src_id, seq))
        self.highest[src_id] = max(seq, self.highest.get(src_id, -1))
        cutoff = self.highest[src_id] - self.window_size
        self.seen = {item for item in self.seen if item[0] != src_id or item[1] > cutoff}
        return "accept"

