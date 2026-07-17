from caiman_sim.compact_protocol import decode_frame_header
from caiman_sim.crypto_layer import KeyMaterial
from caiman_sim.models import MessageType
from caiman_sim.packets import create_frame


def test_telemetry_is_one_exact_nrf24_frame() -> None:
    frame = create_frame(
        mission_id="test",
        nonce_prefix=b"ABCD",
        key=KeyMaterial.create("test", 1, b"k" * 32),
        src_id="R2",
        dst_id="BASE",
        seq=7,
        message_type=MessageType.TELEMETRY,
        timestamp=42.0,
        payload={
            "x": 123.4, "y": 456.7, "depth": 14.25, "seafloor_depth": 17.25,
            "battery": 87.5, "heading": 90.0, "link_quality": 0.75,
            "leak": False, "gnss_available": False,
        },
    )

    assert frame.wire_payload_bytes == 8
    assert frame.wire_ciphertext_bytes == 24
    assert frame.fragment_count == 1
    assert all(len(part) == 32 for part in frame.wire_frames)
    assert decode_frame_header(frame.wire_frames[0])["fragment_count"] == 1


def test_forwarding_keeps_authenticated_wire_frame_immutable() -> None:
    key = KeyMaterial.create("test", 1, b"k" * 32)
    frame = create_frame(
        mission_id="test", nonce_prefix=b"ABCD", key=key, src_id="R1", dst_id="BASE",
        seq=1, message_type=MessageType.PING, timestamp=1.0, payload={"ping": 1}, ttl=8,
    )
    forwarded = frame.forwarded("R2", key)

    assert forwarded.wire_frames == frame.wire_frames
