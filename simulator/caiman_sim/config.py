"""Configuration and abstract underwater channel profiles."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class CommunicationProfile(str, Enum):
    NRF24_SURFACE = "NRF24_SURFACE"
    IDEAL_MESH = "IDEAL_MESH"
    ACOUSTIC_OOK = "ACOUSTIC_OOK"
    ACOUSTIC_BFSK = "ACOUSTIC_BFSK"


@dataclass(frozen=True)
class ProfileDefaults:
    bitrate: float
    base_latency: float
    packet_loss: float
    jitter: float


PROFILE_DEFAULTS = {
    CommunicationProfile.NRF24_SURFACE: ProfileDefaults(1_000_000.0, 0.005, 0.03, 0.003),
    CommunicationProfile.IDEAL_MESH: ProfileDefaults(50_000.0, 0.02, 0.01, 0.005),
    CommunicationProfile.ACOUSTIC_OOK: ProfileDefaults(100.0, 0.15, 0.15, 0.12),
    CommunicationProfile.ACOUSTIC_BFSK: ProfileDefaults(300.0, 0.20, 0.08, 0.09),
}


@dataclass
class SimulationConfig:
    """All reproducible mission and transport settings."""

    width: float = 1000.0
    height: float = 700.0
    robot_count: int = 5
    seed: int = 42
    tick_seconds: float = 1.0
    simulation_speed: float = 1.0
    communication_profile: CommunicationProfile = CommunicationProfile.NRF24_SURFACE
    communication_range: float = 250.0
    packet_loss: float | None = None
    bitrate: float | None = None
    base_latency: float | None = None
    jitter: float | None = None
    default_ttl: int = 8
    ack_timeout: float = 4.0
    max_retries: int = 3
    telemetry_interval: float = 5.0
    movement_mode: str = "lawnmower"
    obstacles_enabled: bool = True
    temporary_offline_probability: float = 0.0
    battery_capacity_ah: float = 56.0
    nominal_voltage: float = 12.0
    mean_motor_current: float = 15.0
    minimum_operating_depth: float = 10.0
    maximum_operating_depth: float = 20.0

    def __post_init__(self) -> None:
        if isinstance(self.communication_profile, str):
            self.communication_profile = CommunicationProfile(self.communication_profile)
        self.robot_count = max(3, min(15, int(self.robot_count)))
        defaults = PROFILE_DEFAULTS[self.communication_profile]
        if self.packet_loss is None:
            self.packet_loss = defaults.packet_loss
        if self.bitrate is None:
            self.bitrate = defaults.bitrate
        if self.base_latency is None:
            self.base_latency = defaults.base_latency
        if self.jitter is None:
            self.jitter = defaults.jitter
        self.packet_loss = min(1.0, max(0.0, float(self.packet_loss)))

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["communication_profile"] = self.communication_profile.value
        return result
