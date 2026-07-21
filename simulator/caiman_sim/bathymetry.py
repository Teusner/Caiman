"""Deterministic coastal bathymetry and coordinated survey planning."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .models import Position


@dataclass(frozen=True)
class BathymetrySample:
    x: float
    y: float
    depth: float


class BathymetryMap:
    """A bounded, smooth coastal seabed for a 10–20 metre operating envelope."""

    def __init__(self, width: float, height: float, seed: int, grid_x: int = 72, grid_y: int = 50) -> None:
        self.width = width
        self.height = height
        self.seed = seed
        self.polygon: list[tuple[float, float]] = [
            (145.0, 165.0),
            (310.0, 112.0),
            (585.0, 126.0),
            (875.0, 168.0),
            (930.0, 474.0),
            (760.0, 572.0),
            (430.0, 585.0),
            (175.0, 520.0),
        ]
        # Generate a distinct but reproducible seabed for each mission seed.
        # Previously, the seed changed only a low-amplitude ripple while the
        # main trench stayed fixed, so every mission had nearly the same map.
        terrain_rng = np.random.default_rng(np.random.SeedSequence([seed, 0xCA1A]))

        def random_point_inside() -> tuple[float, float]:
            for _ in range(100):
                candidate_x = float(terrain_rng.uniform(175.0, 930.0))
                candidate_y = float(terrain_rng.uniform(125.0, 585.0))
                if self.contains(candidate_x, candidate_y):
                    return candidate_x, candidate_y
            return self.width / 2.0, self.height / 2.0

        primary_x, primary_y = random_point_inside()
        secondary_x, secondary_y = random_point_inside()
        for _ in range(20):
            if math.hypot(secondary_x - primary_x, secondary_y - primary_y) >= 220.0:
                break
            secondary_x, secondary_y = random_point_inside()
        shoal_x, shoal_y = random_point_inside()
        self._slope_angle = float(terrain_rng.uniform(-0.65, 0.65))
        self._phase_x = float(terrain_rng.uniform(0.0, math.tau))
        self._phase_y = float(terrain_rng.uniform(0.0, math.tau))
        self._basins = (
            (
                primary_x,
                primary_y,
                float(terrain_rng.uniform(90.0, 175.0)),
                float(terrain_rng.uniform(70.0, 140.0)),
                float(terrain_rng.uniform(3.2, 4.2)),
            ),
            (
                secondary_x,
                secondary_y,
                float(terrain_rng.uniform(120.0, 230.0)),
                float(terrain_rng.uniform(90.0, 170.0)),
                float(terrain_rng.uniform(1.3, 2.2)),
            ),
        )
        self._shoal = (
            shoal_x,
            shoal_y,
            float(terrain_rng.uniform(90.0, 180.0)),
            float(terrain_rng.uniform(70.0, 145.0)),
            float(terrain_rng.uniform(0.9, 1.7)),
        )
        self._channel_slope = float(terrain_rng.uniform(-0.35, 0.45))
        self._channel_offset = float(terrain_rng.uniform(180.0, 470.0))
        self._channel_width = float(terrain_rng.uniform(45.0, 90.0))
        self._channel_strength = float(terrain_rng.uniform(0.35, 0.85))
        self.x_values = np.linspace(0.0, width, grid_x)
        self.y_values = np.linspace(0.0, height, grid_y)
        # Reused by every sonar observation and sync. Building these arrays for
        # every robot tick dominated the hot path during accelerated playback.
        self.grid_xx, self.grid_yy = np.meshgrid(self.x_values, self.y_values)
        self.depth_grid = np.array([[self.depth_at(float(x), float(y)) for x in self.x_values] for y in self.y_values])
        self.inside_mask = np.array([[self.contains(float(x), float(y)) for x in self.x_values] for y in self.y_values])
        self.observed_mask = np.zeros_like(self.inside_mask, dtype=bool)
        self.sampled_mask = np.zeros_like(self.inside_mask, dtype=bool)
        self.measured_grid = np.full_like(self.depth_grid, np.nan, dtype=float)
        self.base_observed_mask = np.zeros_like(self.inside_mask, dtype=bool)
        self.base_measured_grid = np.full_like(self.depth_grid, np.nan, dtype=float)
        self.sample_count = 0
        self.samples: list[BathymetrySample] = []
        self.base_samples: list[BathymetrySample] = []
        self.deepest_sample: BathymetrySample | None = None
        self.base_deepest_sample: BathymetrySample | None = None
        valid = np.where(self.inside_mask, self.depth_grid, np.nan)
        max_index = np.unravel_index(int(np.nanargmax(valid)), valid.shape)
        self.true_deepest = BathymetrySample(
            float(self.x_values[max_index[1]]), float(self.y_values[max_index[0]]), float(valid[max_index])
        )

    def contains(self, x: float, y: float) -> bool:
        inside = False
        previous = self.polygon[-1]
        for current in self.polygon:
            x1, y1 = previous
            x2, y2 = current
            if (y1 > y) != (y2 > y):
                crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
                if x < crossing_x:
                    inside = not inside
            previous = current
        return inside

    def depth_at(self, x: float, y: float) -> float:
        """Synthetic but geographically plausible shallow coastal bathymetry."""
        normalized_x = x / self.width - 0.5
        normalized_y = y / self.height - 0.5
        slope_axis = normalized_x * math.cos(self._slope_angle) + normalized_y * math.sin(self._slope_angle)
        terrain = -1.15 + 1.15 * slope_axis
        for center_x, center_y, scale_x, scale_y, strength in self._basins:
            terrain += strength * math.exp(-(((x - center_x) / scale_x) ** 2 + ((y - center_y) / scale_y) ** 2))
        shoal_x, shoal_y, shoal_scale_x, shoal_scale_y, shoal_strength = self._shoal
        terrain -= shoal_strength * math.exp(
            -(((x - shoal_x) / shoal_scale_x) ** 2 + ((y - shoal_y) / shoal_scale_y) ** 2)
        )
        channel_axis = self._channel_slope * (x - self.width / 2.0) + self._channel_offset
        terrain += self._channel_strength * math.exp(-((y - channel_axis) / self._channel_width) ** 2)
        terrain += 0.22 * math.sin(x / 74.0 + self._phase_x) * math.cos(y / 61.0 + self._phase_y)
        # A logistic mapping avoids artificial flat clipping while keeping the
        # seabed strictly inside 13-20 m (vehicle target depth remains 10-17 m).
        return 13.0 + 7.0 / (1.0 + math.exp(-terrain))

    def vehicle_depth_at(self, x: float, y: float) -> float:
        return max(10.0, min(20.0, self.depth_at(x, y) - 3.0))

    def observe(self, x: float, y: float, radius: float, rng: np.random.Generator) -> BathymetrySample | None:
        if not self.contains(x, y):
            return None
        measurement = float(min(20.0, max(10.0, self.depth_at(x, y) + rng.normal(0.0, 0.06))))
        self.sample_count += 1
        sample = BathymetrySample(x, y, measurement)
        self.samples.append(sample)
        if self.deepest_sample is None or measurement > self.deepest_sample.depth:
            self.deepest_sample = sample
        x_index = int(np.abs(self.x_values - x).argmin())
        y_index = int(np.abs(self.y_values - y).argmin())
        self.sampled_mask[y_index, x_index] = True
        self.measured_grid[y_index, x_index] = measurement
        # Reconnaissance coverage means a cell has a nearby measured track;
        # it is not the much smaller physical single-beam footprint.
        supported = (
            (self.grid_xx - x) ** 2 + (self.grid_yy - y) ** 2 <= max(26.0, radius) ** 2
        ) & self.inside_mask
        self.observed_mask |= supported
        return sample

    @property
    def coverage(self) -> float:
        total = int(self.inside_mask.sum())
        return float((self.observed_mask & self.inside_mask).sum() / total) if total else 0.0

    @property
    def base_coverage(self) -> float:
        total = int(self.inside_mask.sum())
        return float((self.base_observed_mask & self.inside_mask).sum() / total) if total else 0.0

    def sync_to_base(self, sample_limit: int | None = None) -> None:
        """Commit the data physically carried to a surface RF contact."""
        self.base_samples = list(self.samples[:sample_limit])
        self.base_observed_mask[:] = False
        for sample in self.base_samples:
            self.base_observed_mask |= (
                ((self.grid_xx - sample.x) ** 2 + (self.grid_yy - sample.y) ** 2) <= 26.0**2
            ) & self.inside_mask
        self.base_measured_grid[:] = np.nan
        if self.base_samples:
            sample_x = np.array([sample.x for sample in self.base_samples])
            sample_y = np.array([sample.y for sample in self.base_samples])
            sample_depth = np.array([sample.depth for sample in self.base_samples])
            for y_index, y in enumerate(self.y_values):
                for x_index, x in enumerate(self.x_values):
                    if not self.inside_mask[y_index, x_index]:
                        continue
                    distances_sq = (sample_x - x) ** 2 + (sample_y - y) ** 2
                    nearest = np.argpartition(distances_sq, min(7, len(distances_sq) - 1))[: min(8, len(distances_sq))]
                    if float(np.sqrt(distances_sq[nearest].min())) > 60.0:
                        continue
                    weights = 1.0 / np.maximum(distances_sq[nearest], 0.25)
                    self.base_measured_grid[y_index, x_index] = float(np.sum(weights * sample_depth[nearest]) / np.sum(weights))
        self.base_deepest_sample = max(self.base_samples, key=lambda sample: sample.depth, default=None)

    @staticmethod
    def sonar_footprint_radius(altitude_above_bottom: float) -> float:
        """Ping single-beam footprint radius for the documented 25 degree cone."""
        return max(0.2, altitude_above_bottom * math.tan(math.radians(12.5)))

    def horizontal_bounds(self, y: float) -> tuple[float, float]:
        intersections: list[float] = []
        previous = self.polygon[-1]
        for current in self.polygon:
            x1, y1 = previous
            x2, y2 = current
            if (y1 <= y < y2) or (y2 <= y < y1):
                intersections.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
            previous = current
        if len(intersections) < 2:
            raise ValueError(f"survey lane y={y} does not intersect mission region")
        intersections.sort()
        return intersections[0] + 12.0, intersections[-1] - 12.0

    def build_survey_routes(self, robot_ids: list[str]) -> dict[str, list[Position]]:
        """Create synchronized boustrophedon transects for the survey subgroup."""
        if not robot_ids:
            return {}
        lane_count = len(robot_ids) * 4
        lane_ys = np.linspace(155.0, 545.0, lane_count)
        routes = {robot_id: [] for robot_id in robot_ids}
        for batch in range(4):
            reverse = bool(batch % 2)
            for offset, robot_id in enumerate(robot_ids):
                y = float(lane_ys[batch * len(robot_ids) + offset])
                left, right = self.horizontal_bounds(y)
                start_x, end_x = (right, left) if reverse else (left, right)
                routes[robot_id].extend(
                    [
                        Position(start_x, y, self.vehicle_depth_at(start_x, y)),
                        Position(end_x, y, self.vehicle_depth_at(end_x, y)),
                    ]
                )
        return routes

    def build_survey_batches(
        self, robot_ids: list[str], rendezvous_positions: list[Position]
    ) -> list[dict[str, list[Position]]]:
        """Parallel sweeps ending at moving surface rendezvous points."""
        if not robot_ids:
            return []
        batch_count = len(rendezvous_positions)
        lane_ys = np.linspace(140.0, 560.0, len(robot_ids) * batch_count)
        batches: list[dict[str, list[Position]]] = []
        for batch_index in range(batch_count):
            rendezvous = rendezvous_positions[batch_index]
            reverse = bool(batch_index % 2)
            routes: dict[str, list[Position]] = {}
            for offset, robot_id in enumerate(robot_ids):
                y = float(lane_ys[batch_index * len(robot_ids) + offset])
                left, right = self.horizontal_bounds(y)
                start_x, end_x = (right, left) if reverse else (left, right)
                angle = math.tau * offset / len(robot_ids)
                rendezvous_slot = Position(
                    rendezvous.x + 30.0 * math.cos(angle),
                    rendezvous.y + 30.0 * math.sin(angle),
                    0.0,
                )
                routes[robot_id] = [
                    Position(start_x, y, self.vehicle_depth_at(start_x, y)),
                    Position(end_x, y, self.vehicle_depth_at(end_x, y)),
                    rendezvous_slot,
                ]
            batches.append(routes)
        return batches
