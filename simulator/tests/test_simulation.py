from __future__ import annotations

import numpy as np

from caiman_sim.config import CommunicationProfile, SimulationConfig
from caiman_sim.bathymetry import BathymetryMap
from caiman_sim.models import CommandStatus, CommandType, Position
from caiman_sim.robot import Robot
from caiman_sim.simulation import Simulation


def test_retransmission_after_timeout():
    config = SimulationConfig(
        robot_count=3,
        seed=11,
        communication_profile=CommunicationProfile.IDEAL_MESH,
        communication_range=10,
        packet_loss=0,
        ack_timeout=2,
        max_retries=3,
        telemetry_interval=10_000,
    )
    sim = Simulation(config)
    sim.deploy()
    sim.pause()
    sim.robots["R3"].position = Position(500, 500, 0)
    command = sim.send_command("R3", CommandType.HOLD_POSITION)
    assert command.attempts == 1
    sim.step(force=True)
    sim.step(force=True)
    assert command.attempts == 2
    assert sim.network.metrics.retries == 1


def test_battery_falls_gradually(lossless_config):
    sim = Simulation(lossless_config)
    sim.deploy()
    initial = sim.robots["R1"].battery
    for _ in range(50):
        sim.step()
    assert 0 < sim.robots["R1"].battery < initial


def test_fleet_starts_on_vessel_and_deploys_every_robot_as_surveyor(lossless_config):
    sim = Simulation(lossless_config)
    assert sim.mission_phase == "ON_DECK"
    assert all(robot.position == sim.base.position for robot in sim.robots.values())
    assert not any(robot.deployed for robot in sim.robots.values())
    sim.deploy()
    assert sim.mission_phase == "DEPLOYING"
    assert sim.running
    assert {robot.role for robot in sim.robots.values()} == {"SURVEY"}
    assert sim.courier_id is None
    assert all(robot.deployed for robot in sim.robots.values())


def test_step_many_advances_ten_ticks_after_deploy(lossless_config):
    sim = Simulation(lossless_config)
    sim.deploy()
    sim.pause()
    sim.step_many(10)
    assert sim.time == 10 * lossless_config.tick_seconds * lossless_config.simulation_speed


def test_runtime_controls_apply_without_rebuilding_fleet():
    sim = Simulation(SimulationConfig(robot_count=5, seed=42))
    desired = SimulationConfig(
        robot_count=5, seed=42, communication_range=410, packet_loss=0.17,
        bitrate=250_000, default_ttl=5, telemetry_interval=11,
        obstacles_enabled=False, simulation_speed=2.0,
    )
    original_robots = sim.robots
    sim.apply_runtime_config(desired)
    assert sim.robots is original_robots
    assert sim.config.communication_range == 410
    assert sim.config.packet_loss == 0.17
    assert sim.config.bitrate == 250_000
    assert sim.config.default_ttl == 5
    assert all(robot.telemetry_interval == 11 for robot in sim.robots.values())
    assert sim.obstacles == []


def test_five_robot_mission_uses_every_robot_in_surface_backbone():
    sim = Simulation(SimulationConfig(robot_count=5, packet_loss=0))
    sim.deploy()
    assert len(sim.robots) == 5
    assert sum(robot.role == "SURVEY" for robot in sim.robots.values()) == 5
    assert sum(robot.role == "COURIER" for robot in sim.robots.values()) == 0
    sim.step_many(3_500)
    assert sim.mission_phase == "COMPLETE"
    assert sim.data_mule_history == []
    assert sim.fleet_backbone_history == [
        ["R1", "R2", "R3", "R4", "R5"],
        ["R1", "R2", "R3", "R4", "R5"],
    ]
    assert sim.bathymetry.base_coverage == 1.0
    assert sim.cleanup_passes == 1
    assert sim.time < 2_200
    assert sim.summary()["productive_utilization"] > 0.99
    for robot_id in sim.robots:
        received = sim.base.telemetry_history_by_robot[robot_id]
        fixes = [Position(row["x"], row["y"], row["depth"]) for row in received if {"x", "y", "depth"} <= row.keys()]
        assert max(left.distance_to(right) for left, right in zip(fixes, fixes[1:])) <= 20.1
    assert all(robot.position.distance_to(sim.base.position) < 3.0 for robot in sim.robots.values())


def test_dead_reckoning_remains_continuous_across_rendezvous_replans():
    sim = Simulation(SimulationConfig(robot_count=5, packet_loss=0))
    sim.deploy()
    previous = {robot_id: sim.estimated_position(robot_id)[0] for robot_id in sim.robots}
    largest_jump = 0.0
    for _ in range(900):
        sim.step()
        for robot_id in sim.robots:
            current = sim.estimated_position(robot_id)[0]
            largest_jump = max(largest_jump, previous[robot_id].distance_to(current))
            previous[robot_id] = current
    # Live RF fixes may correct accumulated dead reckoning by a few metres, but
    # a route revision must never create the old hundreds-of-metres teleport.
    assert largest_jump <= 8.1


def test_first_rendezvous_has_no_exclusive_data_mule_detour():
    sim = Simulation(SimulationConfig(robot_count=5, packet_loss=0))
    sim.deploy()
    while not (sim.data_sync_count == 1 and sim.mission_phase == "SURVEYING"):
        sim.step()
    assert sim.courier_id is None
    assert sim.fleet_backbone_history[0] == ["R1", "R2", "R3", "R4", "R5"]
    assert any(route["path"][-1] == "BASE" and len(route["path"]) >= 3 for route in sim.network.recent_routes)
    assert all(robot.speed == 2.0 for robot in sim.robots.values())
    assert all(len(robot.assigned_waypoints) == 3 for robot in sim.robots.values())
    assert all(robot.state.value == "EXPLORING" for robot in sim.robots.values())


def test_bathymetry_is_bounded_and_coverage_grows(lossless_config):
    sim = Simulation(lossless_config)
    assert 10.0 <= sim.bathymetry.true_deepest.depth <= 20.0
    sim.deploy()
    initial = sim.bathymetry.coverage
    sim.step_many(100)
    assert sim.bathymetry.coverage > initial
    assert all(robot.position.depth <= 20.0 for robot in sim.robots.values())


def test_bathymetry_seed_changes_terrain_and_deepest_location():
    maps = [BathymetryMap(1100.0, 700.0, seed) for seed in (1, 2, 3, 42)]
    deepest_locations = {(round(item.true_deepest.x), round(item.true_deepest.y)) for item in maps}
    assert len(deepest_locations) == len(maps)
    assert all(13.0 < item.true_deepest.depth < 20.0 for item in maps)
    assert all(not np.allclose(maps[0].depth_grid, item.depth_grid) for item in maps[1:])


def test_export_contains_mapped_bathymetry(lossless_config, tmp_path):
    sim = Simulation(lossless_config)
    sim.deploy()
    sim.step_many(100)
    paths = sim.export(str(tmp_path))
    assert paths["bathymetry"].exists()
    assert paths["mission"].exists()


def test_surface_rf_disconnects_submerged_robots_and_eventually_syncs():
    config = SimulationConfig(
        robot_count=6,
        seed=42,
        communication_profile=CommunicationProfile.NRF24_SURFACE,
        communication_range=260,
        packet_loss=0,
        telemetry_interval=10_000,
    )
    sim = Simulation(config)
    sim.deploy()
    sim.step_many(300)
    assert sim.network.connected_to_base() == {"BASE"}
    r2_report = next(row for row in sim.robot_rows() if row["robot_id"] == "R2")
    assert r2_report["position_status"] == "LAST KNOWN"
    assert abs(r2_report["x"] - sim.robots["R2"].position.x) > 50
    actual = sim.robots["R2"].position
    last_error = Position(r2_report["x"], r2_report["y"], r2_report["depth"]).distance_to(actual)
    estimate_error = Position(
        r2_report["estimated_x"], r2_report["estimated_y"], r2_report["estimated_depth"]
    ).distance_to(actual)
    assert estimate_error < last_error
    assert r2_report["estimate_uncertainty_m"] > 2.0
    assert sim.pc_topology_links() == []
    assert sim.bathymetry.coverage > 0
    assert sim.bathymetry.base_coverage == 0
    sim.step_many(3_000)
    assert sim.data_sync_count >= 1
    assert sim.bathymetry.base_coverage > 0
    assert sim.mission_phase == "COMPLETE"
    assert all(robot.position.distance_to(sim.base.position) < 3.0 for robot in sim.robots.values())


def test_pressure_increases_with_depth_and_gnss_is_submerged(lossless_config):
    sim = Simulation(lossless_config)
    robot = sim.robots["R1"]
    robot.position.depth = 20
    deep = robot.telemetry(0, sim.rng, 0, 0)
    robot.position.depth = 0
    surface = robot.telemetry(1, sim.rng, 0, 0)
    assert deep.external_pressure > surface.external_pressure
    assert deep.gnss_available is False
    assert surface.gnss_available is True


def test_same_seed_reproduces_motion_and_network(lossless_config):
    first = Simulation(lossless_config)
    second = Simulation(SimulationConfig(**lossless_config.to_dict()))
    first.deploy()
    second.deploy()
    for _ in range(20):
        first.step()
        second.step()
    positions_a = [(r.position.x, r.position.y, r.position.depth, r.battery) for r in first.robots.values()]
    positions_b = [(r.position.x, r.position.y, r.position.depth, r.battery) for r in second.robots.values()]
    assert positions_a == positions_b
    assert first.network.packet_log == second.network.packet_log


def test_key_rotation_updates_key_id_and_acknowledgements(chain_sim):
    old_id = chain_sim.base.keys.current_key_id
    new_id = chain_sim.rotate_key()
    assert new_id == old_id + 1
    assert all(robot.keys.current_key_id == new_id for robot in chain_sim.robots.values())
    assert all(chain_sim.base.key_rotation_status.values())


def test_key_rotation_is_deferred_while_nrf_robots_are_submerged():
    sim = Simulation(SimulationConfig(robot_count=3, communication_profile=CommunicationProfile.NRF24_SURFACE, packet_loss=0))
    sim.deploy()
    sim.step_many(20)
    current = sim.base.keys.current_key_id
    assert sim.rotate_key() == current
    assert sim.base.keys.current_key_id == current
    assert sim.events.records[-1]["event"] == "Key rotation deferred"


def test_physical_capture_recalls_survivors_only_after_surface_contact_and_rekeys():
    sim = Simulation(SimulationConfig(robot_count=5, packet_loss=0))
    sim.deploy()
    sim.step_many(100)
    assert all(robot.position.depth > 0.5 for robot in sim.robots.values())
    old_key_id = sim.base.keys.current_key_id

    sim.capture_robot("R1")

    assert sim.mission_phase == "SECURITY_RECALL"
    assert sim.compromised_key_id == old_key_id
    assert sim.robots["R1"].captured
    assert not sim.robots["R1"].online
    assert sim.security_recall_received == set()  # no fictional underwater RF
    captured_fix = sim.estimated_position("R1")[0]
    sim.step_many(2_000)

    assert sim.mission_phase == "ABORTED_CAPTURE"
    assert not sim.running
    assert sim.security_recall_received == {"R2", "R3", "R4", "R5"}
    assert sim.security_recovered == {"R2", "R3", "R4", "R5"}
    assert sim.revoked_robot_ids == {"R1"}
    assert sim.security_rekey_complete
    assert sim.base.keys.current_key_id == old_key_id + 1
    assert set(sim.base.keys.keys) == {old_key_id + 1}
    for robot_id in ("R2", "R3", "R4", "R5"):
        robot = sim.robots[robot_id]
        assert robot.position.distance_to(sim.base.position) < 3.0
        assert set(robot.keys.keys) == {old_key_id + 1}
    assert sim.robots["R1"].keys.current_key_id == old_key_id
    assert old_key_id + 1 not in sim.robots["R1"].keys.keys
    # The PC freezes the captured node at its last fix instead of leaking the
    # simulator's hidden physical position or inventing continued tracking.
    assert sim.estimated_position("R1")[0] == captured_fix


def test_tamper_and_route_mac_attacks_are_rejected(chain_sim):
    assert not chain_sim.inject_tampered_ciphertext("R1")
    assert chain_sim.robots["R1"].security.authentication_failures == 1
    assert not chain_sim.inject_tampered_tag("R1")
    assert chain_sim.robots["R1"].security.authentication_failures == 2
    assert not chain_sim.inject_invalid_route_mac("R1")
    assert chain_sim.robots["R1"].security.invalid_route_mac == 1
