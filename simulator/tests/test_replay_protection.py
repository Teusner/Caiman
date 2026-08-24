from __future__ import annotations

from caiman_sim.crypto_layer import ReplayWindow
from caiman_sim.models import MessageType


def test_replay_window_distinguishes_duplicates_and_stale_packets():
    window = ReplayWindow(window_size=4)
    assert window.accept("R1", 1) == "accept"
    assert window.accept("R1", 1) == "duplicate"
    for seq in range(2, 8):
        assert window.accept("R1", seq) == "accept"
    assert window.accept("R1", 1) == "replay"


def test_network_detects_replayed_source_sequence(chain_sim):
    frame = chain_sim._frame("BASE", "R1", MessageType.PING, {"test": True})
    assert chain_sim.network.transmit(frame, 0.0, chain_sim._handle_delivery)
    assert not chain_sim.network.transmit(frame, 1.0, chain_sim._handle_delivery)
    assert chain_sim.robots["R1"].security.duplicate_drops == 1

