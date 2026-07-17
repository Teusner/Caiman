from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from caiman_sim.config import CommunicationProfile, SimulationConfig
from caiman_sim.models import Position
from caiman_sim.simulation import Simulation


@pytest.fixture
def lossless_config() -> SimulationConfig:
    return SimulationConfig(
        robot_count=3,
        seed=7,
        communication_profile=CommunicationProfile.IDEAL_MESH,
        communication_range=115.0,
        packet_loss=0.0,
        bitrate=50_000,
        base_latency=0.0,
        jitter=0.0,
        telemetry_interval=10_000,
        default_ttl=8,
    )


@pytest.fixture
def chain_sim(lossless_config: SimulationConfig) -> Simulation:
    sim = Simulation(lossless_config)
    sim.base.position = Position(0, 100, 0)
    sim.robots["R1"].position = Position(100, 100, 0)
    sim.robots["R2"].position = Position(200, 100, 0)
    sim.robots["R3"].position = Position(300, 100, 0)
    return sim

