from __future__ import annotations

from caiman_sim.models import CommandStatus, CommandType, MessageType
from caiman_sim.config import CommunicationProfile, SimulationConfig
from caiman_sim.models import Position
from caiman_sim.simulation import Simulation


def test_delivers_packet_over_three_hops(chain_sim):
    frame = chain_sim._frame("BASE", "R3", MessageType.MISSION_START, {"hello": "mesh"})
    assert chain_sim.network.transmit(frame, 0.0, chain_sim._handle_delivery)
    route = chain_sim.network.recent_routes[-1]["path"]
    assert route == ["BASE", "R1", "R2", "R3"]
    assert chain_sim.network.metrics.relays >= 2


def test_duplicate_is_not_forwarded_twice(chain_sim):
    frame = chain_sim._frame("BASE", "R3", MessageType.MISSION_START, {})
    assert chain_sim.network.transmit(frame, 0.0, chain_sim._handle_delivery)
    relays = chain_sim.network.metrics.relays
    assert not chain_sim.network.transmit(frame, 1.0, chain_sim._handle_delivery)
    assert chain_sim.network.metrics.relays == relays


def test_ttl_exhaustion_is_counted(chain_sim):
    frame = chain_sim._frame("BASE", "R3", MessageType.MISSION_START, {})
    from dataclasses import replace
    from caiman_sim.packets import PacketFrame
    import hashlib, hmac
    short = replace(frame, ttl=2, initial_ttl=2, route_mac=b"")
    short = replace(short, route_mac=hmac.new(chain_sim.base.keys.get().route, short.routing_data(), hashlib.sha256).digest())
    assert not chain_sim.network.transmit(short, 0.0, chain_sim._handle_delivery)
    assert sum(robot.security.ttl_drops for robot in chain_sim.robots.values()) >= 1


def test_ack_returns_through_relays(chain_sim):
    command = chain_sim.send_command("R3", CommandType.HOLD_POSITION)
    assert command.status == CommandStatus.ACKNOWLEDGED
    command_route = next(route for route in chain_sim.network.recent_routes if route["path"][-1] == "R3")
    ack_route = next(route for route in chain_sim.network.recent_routes if route["path"][0] == "R3")
    assert command_route["path"] == ["BASE", "R1", "R2", "R3"]
    assert ack_route["path"] == ["R3", "R2", "R1", "BASE"]


def test_nrf24_has_no_link_when_either_node_is_submerged():
    config = SimulationConfig(
        robot_count=3,
        communication_profile=CommunicationProfile.NRF24_SURFACE,
        communication_range=250,
        packet_loss=0,
    )
    sim = Simulation(config)
    sim.base.position = Position(0, 0, 0)
    sim.robots["R1"].position = Position(10, 0, 5)
    assert "R1" not in sim.network.neighbors("BASE")
    sim.robots["R1"].position.depth = 0.0
    assert "R1" in sim.network.neighbors("BASE")
