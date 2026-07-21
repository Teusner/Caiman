"""Streamlit entry point for the Caiman swarm mission simulator."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from caiman_sim.config import CommunicationProfile, SimulationConfig
from caiman_sim.compact_protocol import decode_frame_header, frame_layout
from caiman_sim.models import CommandType
from caiman_sim.simulation import Simulation
from caiman_sim.ui_components import mission_map, telemetry_history_figure, topology_figure


AUTOMATIC_STEP_BATCH = 10
FAST_STEP_BATCH = 50


st.set_page_config(page_title="Caiman Mission Control", page_icon="🌊", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """<style>
    .stApp {background: radial-gradient(circle at 70% 10%, #0c3047 0, #061522 42%, #04101a 100%);}
    [data-testid="stMetric"] {background:rgba(8,39,57,.78); border:1px solid rgba(48,213,242,.20); border-radius:12px; padding:12px;}
    .caiman-sub {color:#75cfe2; letter-spacing:.08em; text-transform:uppercase; font-size:.8rem;}
    </style>""",
    unsafe_allow_html=True,
)


def make_config() -> SimulationConfig:
    return SimulationConfig(
        robot_count=st.session_state.get("cfg_robots", 5),
        seed=st.session_state.get("cfg_seed", 42),
        simulation_speed=st.session_state.get("cfg_speed", 1.0),
        communication_profile=CommunicationProfile(st.session_state.get("cfg_profile", CommunicationProfile.NRF24_SURFACE.value)),
        communication_range=st.session_state.get("cfg_range", 250.0),
        packet_loss=st.session_state.get("cfg_loss", 0.03),
        bitrate=st.session_state.get("cfg_bitrate", 1_000_000.0),
        default_ttl=st.session_state.get("cfg_ttl", 8),
        telemetry_interval=st.session_state.get("cfg_telemetry", 5.0),
        movement_mode=st.session_state.get("cfg_mode", "lawnmower"),
        obstacles_enabled=st.session_state.get("cfg_obstacles", True),
        temporary_offline_probability=st.session_state.get("cfg_offline", 0.0),
    )


def reset_simulation() -> None:
    st.session_state.simulation = Simulation(make_config())


manual_step_applied = False

with st.sidebar:
    st.markdown("## Mission setup")
    st.number_input("Fleet total", 3, 15, 5, key="cfg_robots", help="All vehicles survey and all carry data into the fleet-wide surface backbone.")
    st.caption(f"Current selection: {st.session_state.cfg_robots} survey AUVs; every vehicle is a redundant data carrier.")
    st.number_input("Seed", 0, 1_000_000, 42, key="cfg_seed", help="Changing fleet size or seed rebuilds the mission after confirmation.")
    st.slider("Simulation speed", 0.25, 8.0, 1.0, 0.25, key="cfg_speed")
    st.selectbox("Communication profile", [profile.value for profile in CommunicationProfile], index=0, key="cfg_profile")
    st.caption("NRF24_SURFACE: RF links exist only when both nodes are at ≤ 0.5 m depth.")
    st.slider("Range (m)", 50.0, 600.0, 250.0, 10.0, key="cfg_range")
    st.slider("Packet loss", 0.0, 0.8, 0.03, 0.01, key="cfg_loss")
    st.number_input("Bitrate (bps)", 50.0, 2_000_000.0, 1_000_000.0, 50_000.0, key="cfg_bitrate")
    st.slider("Default TTL", 1, 16, 8, key="cfg_ttl")
    st.slider("Telemetry interval (s)", 1.0, 30.0, 5.0, 1.0, key="cfg_telemetry")
    st.selectbox("Mission plan", ["coordinated_bathymetric_survey"], key="cfg_mode", disabled=True)
    st.toggle("Obstacles", True, key="cfg_obstacles")
    st.slider("Temporary outage probability / s", 0.0, 0.10, 0.0, 0.005, key="cfg_offline")
    st.divider()
    show_trajectories = st.toggle("Show trajectories", True)
    show_links = st.toggle("Show links", True)
    show_ids = st.toggle("Show IDs", True)
    if "simulation" not in st.session_state:
        reset_simulation()
    sim: Simulation = st.session_state.simulation
    # Streamlit preserves session objects across source hot-reloads. Rebuild an
    # older in-memory Simulation instance when its class gained new behavior.
    if (
        not hasattr(sim, "apply_runtime_config")
        or not hasattr(sim, "estimated_position")
        or not hasattr(sim, "_assign_known_route")
        or not hasattr(sim, "estimator_anchors")
        or not hasattr(sim, "data_mule_history")
        or not hasattr(sim, "fleet_backbone_history")
        or not hasattr(sim, "vessel_target")
        or not hasattr(sim, "rendezvous_positions")
        or not hasattr(sim, "pending_telemetry_sync")
        or not hasattr(sim, "cleanup_passes")
        or not hasattr(sim, "capture_robot")
        or not hasattr(sim, "captured_robot_ids")
        or not hasattr(sim.base, "telemetry_history_by_robot")
        or any(
            not hasattr(robot, "route_revision") or not hasattr(robot, "operational_idle_seconds") or not hasattr(robot, "captured")
            for robot in sim.robots.values()
        )
    ):
        reset_simulation()
        sim = st.session_state.simulation
    desired_config = make_config()
    restart_required = (
        desired_config.robot_count != len(sim.robots)
        or desired_config.seed != sim.config.seed
    )
    if restart_required and not sim.deployed:
        st.session_state.simulation = Simulation(desired_config)
        sim = st.session_state.simulation
        restart_required = False
    sim.apply_runtime_config(desired_config)
    st.success("Runtime sliders are applied live.")
    if restart_required:
        st.warning(
            f"Fleet/seed pending: running mission has {len(sim.robots)} AUVs; selected fleet has "
            f"{desired_config.robot_count}. Apply below to rebuild the mission."
        )
    if st.button(
        "Apply fleet/seed and restart" if restart_required else "Restart mission with these parameters",
        type="primary" if restart_required else "secondary",
        use_container_width=True,
    ):
        reset_simulation()
        st.rerun()
    controls = st.columns(2)
    if not sim.deployed and st.button("Deploy fleet", type="primary", use_container_width=True):
        sim.deploy()
        st.rerun()
    terminal = sim.mission_phase in sim.TERMINAL_PHASES
    if controls[0].button("Start / Resume", use_container_width=True, disabled=not sim.deployed or terminal):
        sim.start()
    if controls[1].button("Pause", use_container_width=True, disabled=not sim.deployed or terminal):
        sim.pause()
    if controls[0].button("Step ×1", use_container_width=True, disabled=not sim.deployed or terminal):
        sim.step(force=True)
        manual_step_applied = True
    if controls[1].button(f"Step ×{FAST_STEP_BATCH}", use_container_width=True, disabled=not sim.deployed or terminal):
        sim.step_many(FAST_STEP_BATCH)
        manual_step_applied = True
    st.caption(f"Automatic mode advances {AUTOMATIC_STEP_BATCH} simulation ticks per dashboard refresh.")
    if st.button("Export logs", use_container_width=True):
        paths = sim.export(str(Path(__file__).parent / "exports"))
        st.success(f"Exported {len(paths)} files")

sim = st.session_state.simulation
if sim.running and not manual_step_applied:
    sim.step_many(AUTOMATIC_STEP_BATCH, force=False)
if sim.running:
    st_autorefresh(interval=max(250, int(1000 / sim.config.simulation_speed)), key="mission_refresh")

st.markdown('<div class="caiman-sub">Encrypted underwater swarm operations</div>', unsafe_allow_html=True)
st.title("Caiman Mission Control")
summary = sim.summary()
pc_rows = sim.robot_rows()
reported_batteries = [row["battery"] for row in pc_rows if row["battery"] is not None]
reported_battery = sum(reported_batteries) / len(reported_batteries) if reported_batteries else None
all_positions_live = all(row["position_status"] in {"LIVE RF", "ON DECK"} for row in pc_rows)
known_buffers = [row["buffered_samples"] for row in pc_rows if row["buffered_samples"] is not None]
pc_buffered = sum(known_buffers) if all_positions_live and len(known_buffers) == len(pc_rows) else None
metric_defs = [
    ("Phase", summary["mission_phase"]), ("Mission time", f"{summary['mission_time']:.0f}s"), ("PC map", f"{summary['survey_coverage']:.1%}"),
    ("Deepest synced", f"{summary['deepest_observed']:.2f} m" if summary["deepest_observed"] is not None else "—"), ("RF online", f"{summary['connected_robots']}/{len(sim.robots)}"), ("Operating depth", f"{summary['depth_minimum']:.0f}–{summary['depth_limit']:.0f} m"),
    ("Delivery", f"{summary['delivery_rate']:.1%}"), ("Avg hops", f"{summary['average_hops']:.2f}"),
    ("Avg latency", f"{summary['average_latency']:.3f}s"), ("Surface syncs", summary["data_syncs"]),
    ("Known buffered", pc_buffered if pc_buffered is not None else "—"), ("Last reported battery", f"{reported_battery:.1f}%" if reported_battery is not None else "—"),
]
for row in (metric_defs[:6], metric_defs[6:]):
    columns = st.columns(6)
    for column, (label, value) in zip(columns, row):
        column.metric(label, value)

active_tab = st.radio(
    "Dashboard view",
    ["Mission", "Robots", "Network", "Commands", "Security", "Packet Log", "Events"],
    index=0,
    horizontal=True,
    key="dashboard_view",
    label_visibility="collapsed",
)

if active_tab == "Mission":
    if not sim.deployed:
        st.info("All AUVs are secured on the survey vessel. Deploy the fleet to begin the coordinated bathymetric search.")
    elif summary["connected_robots"] < len(sim.robots) and sim.mission_phase in {"DEPLOYING", "SURVEYING"}:
        st.info("Submerged robots are radio-silent. Open markers with '?' are last-known RF fixes; gold diamonds (~R) are plan/dead-reckoning predictions with growing uncertainty circles. Neither is hidden ground truth. New fixes arrive at a surface rendezvous.")
    if sim.mission_phase == "SECURITY_RECALL":
        st.error(
            f"PHYSICAL CAPTURE: {', '.join(summary['captured_robot_ids'])}. Key {summary['compromised_key_id']} is assumed compromised. "
            f"Recall received by {len(summary['security_recall_received'])}/{len(sim.robots) - summary['captured_robots']} survivors; "
            f"{len(summary['security_recovered'])} are back at the vessel. Submerged AUVs cannot receive the recall until surfacing."
        )
    elif sim.mission_phase == "ABORTED_CAPTURE":
        st.error(
            f"Mission aborted after capture. Survivors recovered: {len(summary['security_recovered'])}; "
            f"revoked: {', '.join(summary['revoked_robot_ids'])}; survivor key {summary['key_id']} active."
        )
    objective = st.columns(6)
    objective[0].metric("Survey region", "~0.34 km²")
    objective[1].metric("Fleet total", len(sim.robots))
    objective[2].metric("Working survey AUVs", sum(robot.role == "SURVEY" and not robot.captured for robot in sim.robots.values()))
    objective[3].metric("Backbone carriers", len(sim.robots) if sim.mission_phase == "SYNCING_WITH_VESSEL" else "all at RV")
    objective[4].metric("PC mapped", f"{summary['survey_coverage']:.1%}", help="Only bathymetry already delivered to the vessel computer.")
    objective[5].metric("Productive utilization", f"{summary['productive_utilization']:.1%}", help=f"Fleet work time excluding recovery. Only {summary['operational_idle_seconds']:.0f} AUV·s of discrete holding; early arrivals receive active sonar patrols.")
    st.caption("Echosounder: single-beam 25° · ~1.3 m physical footprint at 3 m altitude. PC mapped = reconnaissance grid supported by a measured track within 26 m, not direct insonification of every square metre. Final cooperative cleanup closes all unsupported grid cells.")
    st.plotly_chart(mission_map(sim, show_trajectories, show_links, show_ids), use_container_width=True, config={"displayModeBar": False})
    left, right = st.columns([2, 1])
    left.dataframe(pd.DataFrame(pc_rows), use_container_width=True, hide_index=True)
    right.markdown("#### Recent mission events")
    right.dataframe(pd.DataFrame(sim.events.records[-10:][::-1]), use_container_width=True, hide_index=True)

if active_tab == "Robots":
    st.caption("This tab contains only telemetry received by the vessel PC. It does not expose onboard/ground-truth positions while RF is unavailable.")
    st.dataframe(pd.DataFrame(pc_rows), use_container_width=True, hide_index=True)
    selected_robot = st.selectbox("Inspect robot", list(sim.robots), key="inspect_robot")
    selected_row = next(row for row in pc_rows if row["robot_id"] == selected_robot)
    received_history = sim.base.telemetry_history_by_robot.get(selected_robot, [])
    a, b, c, d = st.columns(4)
    a.metric("Fix status", selected_row["position_status"])
    b.metric("Last battery", f"{selected_row['battery']:.2f}%" if selected_row["battery"] is not None else "—")
    c.metric("Last depth", f"{selected_row['depth']:.1f} m" if selected_row["depth"] is not None else "—")
    d.metric("Fix age", f"{selected_row['position_age_s']:.0f} s" if selected_row["position_age_s"] is not None else "—")
    if selected_row["position_status"] == "LAST KNOWN":
        st.caption(
            f"Predicted position: E {selected_row['estimated_x']:.1f} m, N {selected_row['estimated_y']:.1f} m, "
            f"depth {selected_row['estimated_depth']:.1f} m · illustrative uncertainty ±{selected_row['estimate_uncertainty_m']:.0f} m."
        )
    st.plotly_chart(telemetry_history_figure(received_history), use_container_width=True, config={"displayModeBar": False})
    if received_history:
        st.json(received_history[-1], expanded=False)

if active_tab == "Network":
    if sim.config.communication_profile == CommunicationProfile.NRF24_SURFACE:
        st.caption("Physical RF constraint active: nodes deeper than 0.5 m have no link. The topology therefore appears only during surface contacts.")
    st.plotly_chart(topology_figure(sim), use_container_width=True, config={"displayModeBar": False})
    links = pd.DataFrame(sim.pc_topology_links())
    routes = pd.DataFrame(sim.network.recent_routes[::-1])
    left, right = st.columns(2)
    left.markdown("#### Active links")
    left.dataframe(links, use_container_width=True, hide_index=True)
    right.markdown("#### Recent routes")
    right.dataframe(routes, use_container_width=True, hide_index=True)
    st.markdown("#### nRF24 physical packet — exactly 32 bytes")
    st.dataframe(pd.DataFrame(frame_layout()), use_container_width=True, hide_index=True)
    st.caption("Each immutable frame carries 8 encrypted payload bytes and the full 128-bit Poly1305 tag. Relays retransmit the identical authenticated frame and suppress loops with the (source, sequence) seen-cache; hop/TTL stay in local mesh policy.")
    if sim.sent_frames and sim.sent_frames[-1].wire_frames:
        recent = sim.sent_frames[-1]
        physical = recent.wire_frames[0]
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Compact plaintext", f"{recent.wire_payload_bytes} B")
        p2.metric("AEAD ciphertext", f"{recent.wire_ciphertext_bytes} B")
        p3.metric("Physical frames", recent.fragment_count)
        p4.metric("On-air payload", f"{recent.wire_size_bytes} B")
        st.code(physical.hex(" "), language=None)
        st.json(decode_frame_header(physical), expanded=False)
    st.warning("Firmware status: the current nRF24/STM32 driver accepts fixed 32-byte payloads, but its fragment/reassembly, compact codec, nonce persistence, ChaCha20-Poly1305 and HMAC layers still need implementation before this format is hardware-compatible end to end.")

if active_tab == "Commands":
    left, right = st.columns(2)
    target = left.selectbox("Target robot", list(sim.robots), key="command_target")
    command_type = right.selectbox("Command", [item.value for item in CommandType if item != CommandType.ROTATE_KEY], key="command_type")
    parameters_text = st.text_input("Parameters (JSON)", "{}", help='SET_WAYPOINT example: {"x": 500, "y": 200, "depth": 15}')
    if st.button("Send encrypted command"):
        try:
            parameters = json.loads(parameters_text)
            sim.send_command(target, command_type, parameters)
            st.success("Command queued; ACK status is shown below.")
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            st.error(str(exc))
    command_rows = [command.to_dict() for command in sim.base.commands.values()]
    st.dataframe(pd.DataFrame(command_rows), use_container_width=True, hide_index=True)

if active_tab == "Security":
    a, b, c, d = st.columns(4)
    a.metric("Mission ID", sim.mission_id)
    b.metric("Key ID", summary["key_id"])
    c.metric("Fingerprint", summary["fingerprint"])
    d.metric("Provisioned", f"{sum(r.keys.current_key_id == summary['key_id'] for r in sim.robots.values())}/{len(sim.robots)}")
    if summary["captured_robots"]:
        capture_status = st.columns(5)
        capture_status[0].metric("Captured", ", ".join(summary["captured_robot_ids"]))
        capture_status[1].metric("Compromised key", summary["compromised_key_id"])
        capture_status[2].metric("Recall received", len(summary["security_recall_received"]))
        capture_status[3].metric("Recovered", len(summary["security_recovered"]))
        capture_status[4].metric("Rekey / revoke", "DONE" if summary["security_rekey_complete"] else "WAITING")
        st.caption("The captured node is never shown as live. Its red X is only the vessel PC's last received RF fix.")
    security_rows = {
        "Nonces generated": summary["nonces_generated"], "Decrypt success": summary["decrypt_success"],
        "Authentication failures": summary["authentication_failures"], "Invalid route MAC": summary["invalid_route_mac"],
        "Replay drops": summary["replay_drops"], "Duplicate drops": summary["duplicate_drops"],
    }
    st.dataframe(pd.DataFrame([security_rows]), use_container_width=True, hide_index=True)
    cols = st.columns(5)
    if cols[0].button("Rotate mission key", use_container_width=True):
        previous_key_id = sim.base.keys.current_key_id
        new_key_id = sim.rotate_key()
        if new_key_id == previous_key_id:
            st.warning("Rotation deferred: every robot must be surfaced in the vessel RF mesh.")
        else:
            st.success("Rotation messages sent under the previous key.")
    if cols[1].button("Tamper ciphertext", use_container_width=True):
        sim.inject_tampered_ciphertext()
    if cols[2].button("Tamper AEAD tag", use_container_width=True):
        sim.inject_tampered_tag()
    if cols[3].button("Corrupt route MAC", use_container_width=True):
        sim.inject_invalid_route_mac()
    if cols[4].button("Replay packet", use_container_width=True):
        sim.replay_last_packet()
    st.markdown("#### Key rotation acknowledgements")
    st.json(sim.base.key_rotation_status)
    st.markdown("#### Fault injection")
    fault_robot = st.selectbox("Robot", list(sim.robots), key="fault_robot")
    selected_fault_robot = sim.robots[fault_robot]
    capture_disabled = not sim.deployed or bool(sim.captured_robot_ids) or sim.mission_phase in sim.TERMINAL_PHASES
    if st.button(
        "SIMULATE PHYSICAL CAPTURE — abort and recall fleet",
        type="primary",
        use_container_width=True,
        disabled=capture_disabled,
        help="Marks the current group key compromised. Submerged AUVs receive RETURN_HOME only at their next real surface RF contact.",
    ):
        sim.capture_robot(fault_robot)
        st.rerun()
    f1, f2, f3, f4 = st.columns(4)
    if f1.button("Offline", use_container_width=True): sim.set_robot_offline(fault_robot, True)
    if f2.button("Restore", use_container_width=True, disabled=selected_fault_robot.captured): sim.set_robot_offline(fault_robot, False)
    if f3.button("Critical battery", use_container_width=True): sim.force_critical_battery(fault_robot)
    if f4.button("Toggle leak", use_container_width=True): sim.set_leak(fault_robot, not sim.robots[fault_robot].leak)
    iso1, iso2 = st.columns(2)
    if iso1.button("Isolate robot from mesh", use_container_width=True): sim.isolate_robot(fault_robot)
    if iso2.button("Restore all links", use_container_width=True): sim.restore_all_links()
    link_options = [f"{link['source']}|{link['target']}" for link in sim.pc_topology_links()]
    if link_options:
        selected_link = st.selectbox("Active link", link_options)
        if st.button("Interrupt selected link"):
            sim.interrupt_link(*selected_link.split("|"))

if active_tab == "Packet Log":
    packet_frame = pd.DataFrame(sim.network.packet_log)
    if not packet_frame.empty:
        f1, f2, f3 = st.columns(3)
        robot_filter = f1.multiselect("Node", sorted(set(packet_frame["src"]) | set(packet_frame["dst"])))
        type_filter = f2.multiselect("Type", sorted(packet_frame["type"].unique()))
        status_filter = f3.multiselect("Status", sorted(packet_frame["status"].unique()))
        if robot_filter: packet_frame = packet_frame[packet_frame["src"].isin(robot_filter) | packet_frame["dst"].isin(robot_filter)]
        if type_filter: packet_frame = packet_frame[packet_frame["type"].isin(type_filter)]
        if status_filter: packet_frame = packet_frame[packet_frame["status"].isin(status_filter)]
    st.dataframe(packet_frame.iloc[::-1] if not packet_frame.empty else packet_frame, use_container_width=True, hide_index=True, height=560)

if active_tab == "Events":
    event_frame = pd.DataFrame(sim.events.records)
    st.dataframe(event_frame.iloc[::-1] if not event_frame.empty else event_frame, use_container_width=True, hide_index=True, height=620)
