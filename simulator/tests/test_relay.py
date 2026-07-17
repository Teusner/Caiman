from __future__ import annotations

from caiman_sim.models import MessageType


def test_relay_keeps_ciphertext_unchanged(chain_sim):
    frame = chain_sim._frame("BASE", "R3", MessageType.PING, {"immutable": True})
    forwarded = frame.forwarded("R1", chain_sim.robots["R1"].keys.get())
    forwarded_again = forwarded.forwarded("R2", chain_sim.robots["R2"].keys.get())
    assert forwarded_again.ciphertext == frame.ciphertext
    assert forwarded_again.nonce == frame.nonce
    assert forwarded_again.header == frame.header
    assert forwarded_again.ttl == frame.ttl - 2

