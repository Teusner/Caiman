from __future__ import annotations

import hashlib
import hmac
from dataclasses import replace

import pytest

from caiman_sim.crypto_layer import KeyMaterial, build_nonce
from caiman_sim.models import MessageType
from caiman_sim.packets import create_frame, decrypt_frame


def packet():
    mission_id = "TEST-MISSION"
    key = KeyMaterial.create(mission_id, 1, b"k" * 32)
    frame = create_frame(
        mission_id=mission_id,
        nonce_prefix=b"ABCD",
        key=key,
        src_id="R1",
        dst_id="BASE",
        seq=9,
        message_type=MessageType.TELEMETRY,
        timestamp=12.0,
        payload={"depth": 22.5},
    )
    return key, frame


def resign(frame, key):
    return replace(frame, route_mac=hmac.new(key.route, frame.routing_data(), hashlib.sha256).digest())


def test_encrypt_and_decrypt_valid_packet():
    key, frame = packet()
    decoded = decrypt_frame(frame, key)
    assert decoded["message_type"] == "TELEMETRY"
    assert decoded["payload"]["depth"] == 22.5
    assert frame.verify_route(key)


def test_reject_tampered_ciphertext():
    key, frame = packet()
    content = bytearray(frame.ciphertext)
    content[0] ^= 0x80
    tampered = resign(replace(frame, ciphertext=bytes(content)), key)
    with pytest.raises(ValueError, match="authentication"):
        decrypt_frame(tampered, key)


def test_reject_tampered_tag():
    key, frame = packet()
    content = bytearray(frame.ciphertext)
    content[-1] ^= 0x01
    tampered = resign(replace(frame, ciphertext=bytes(content)), key)
    with pytest.raises(ValueError, match="authentication"):
        decrypt_frame(tampered, key)


def test_reject_invalid_route_mac():
    key, frame = packet()
    assert not replace(frame, route_mac=b"x" * 32).verify_route(key)


def test_nonce_unique_for_sequences_and_sources():
    values = {build_nonce(b"ABCD", source, seq) for source in ("BASE", "R1", "R2") for seq in range(100)}
    assert len(values) == 300
    assert all(len(value) == 12 for value in values)

