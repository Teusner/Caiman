# Caiman Underwater Swarm Simulator

Caiman Mission Control is a self-contained visual simulator for a coordinated coastal bathymetric mission. All five AUVs survey a delimited seabed in a 10–20 m operating envelope, all five act as redundant store-carry-forward nodes at surface contacts, and every vehicle returns to the vessel for recovery. The default transport matches the current Caiman nRF24 constraint: submerged robots are radio-silent and store encrypted data until a surface contact.

## Install and run

Python 3.11 or newer is required. From the repository root:

```bash
cd simulator
python -m pip install -r requirements.txt
streamlit run app.py
```

The dashboard opens at `http://localhost:8501`. If the browser is not opened automatically, use that address. The default mission contains five robots in a 1000 x 700 metre area and uses `NRF24_SURFACE`.

## Dashboard controls

The sidebar configures fleet count, deterministic seed, clock speed, channel profile, range, packet loss, bitrate, TTL, telemetry period and temporary outages. Runtime channel controls apply immediately. Fleet count and seed rebuild the mission through the explicit **Apply fleet/seed and restart** button; before deployment they apply automatically. All robots initially share the vessel position and do not move until **Deploy fleet** is pressed.

At deploy time, all five robots receive adjacent boustrophedon transects. Each batch ends at a moving rendezvous placed near that sweep's endpoints to avoid backtracking. Early arrivals map small surface-sonar patrols instead of holding. While the AUVs map, the survey vessel continuously pre-positions near the next contact. At rendezvous all five surfaced AUVs form a redundant nRF mesh and deliver their own encrypted mission shards; edge members can reach the PC through neighboring AUV hops. No exclusive data mule leaves its transect. After fleet sync, all five immediately start the next preloaded block. Final recovery performs a complete dockside data offload.

Before final delivery, the fleet computes unsupported reconnaissance cells from its merged onboard map and distributes a nearest-cluster gap-closing pass. Mission completion requires 100% of the inside grid to lie within 26 m of a measured track. This is explicitly reconnaissance support for the IDW contour map, not 100% direct insonification: the physical Ping footprint remains about 1.3 m wide at 3 m bottom altitude.

The physical power model uses the supplied 56 Ah, 12 V battery and 15 A mean motor current. The ideal motor-only quotient is 3.73 hours; it is not a real endurance promise because electronics, conversion loss, maneuvering peaks, environmental load and safety reserve are not yet characterized.

The tabs provide:

- **Mission**: textured sea map, synced depth contours, delimited region, vessel-known robot fixes, received trajectories, surface RF links and the latest packet route. Open markers with `?` are stale last-known positions. Gold `~R` diamonds propagate the last fix along the commanded route and include a growing illustrative uncertainty envelope; neither exposes hidden simulator truth. At rendezvous the delayed onboard telemetry log is merged by timestamp, reconstructing the travelled path instead of drawing a fake instantaneous jump.
- **Robots**: only telemetry that reached the vessel, including fix age and `LIVE RF` versus `LAST KNOWN` status.
- **Network**: surface topology, link quality, routes, the byte-by-byte 32-byte packet layout, a live hexadecimal frame and compact/plaintext/ciphertext/wire sizes.
- **Commands**: command composer with JSON parameters and the ACK/retry ledger.
- **Security**: safe key identity, provisioning, counters, key rotation, attack and fault injection.
- **Packet Log**: filterable routing and delivery audit.
- **Events**: mission, network, command, security and fault events.

For a waypoint command, select `SET_WAYPOINT` and enter, for example:

```json
{"x": 650, "y": 240, "depth": 15}
```

## Communication profiles

`NRF24_SURFACE` is the hardware-oriented default. A link exists only when both endpoints are at 0.5 m depth or shallower and inside RF range. It uses a 1 Mbps nominal rate, distance-weighted loss and actual fixed 32-byte application frames with a residual-loss estimate after hardware Auto-ACK/retry. `IDEAL_MESH` remains available for debugging. `ACOUSTIC_OOK` and `ACOUSTIC_BFSK` remain optional future-modem studies.

Each immutable physical frame contains an 8-byte header, 8 encrypted payload bytes and the full 16-byte ChaCha20-Poly1305 tag. Common telemetry is bit-packed into eight bytes and therefore occupies exactly one radio frame. Relays retransmit the same authenticated bytes and suppress loops with a `(source, sequence)` seen-cache; TTL and hop count remain local mesh policy rather than consuming or mutating radio bytes. A message is limited to 16 fragments. This is a simulator protocol specification: the repository's STM32 driver already sends fixed 32-byte nRF payloads, but firmware-side fragmentation/reassembly, compact encoding, cryptography and crash-safe nonce persistence remain to be implemented.

## Security demonstration

Each mission creates `K_mission` with `secrets.token_bytes(32)`. HKDF-SHA256 derives independent encryption, routing and fingerprint keys. ChaCha20-Poly1305 protects the inner packet, with immutable routing fields as AAD. Mutable relay fields are protected by HMAC-SHA256 and re-signed at every relay. A deterministic 4+2+6 byte nonce construction combines the mission prefix, source ID and monotonic per-source sequence.

The dashboard never shows a key. It exposes only `key_id` and a truncated keyed fingerprint. Use the Security tab to alter ciphertext, corrupt a route MAC, replay an old packet, rotate the mission key or inject robot/link failures.

## Tests

```bash
cd simulator
pytest -q
```

The suite covers AEAD validation and tampering, route authentication, nonce uniqueness, replay windows, duplicate forwarding, three-hop delivery, TTL exhaustion, relay ACKs, timeout retransmission, sensor coherence, battery behavior, deterministic runs, surface-only RF, rendezvous synchronization and group-key rotation.

## Export

The **Export logs** button writes six timestamped files to `simulator/exports/`: telemetry CSV, packet CSV, mapped bathymetry CSV, full mission JSON, configuration JSON and summary JSON. The same operation is reusable from Python:

```python
from caiman_sim.mission import export_mission

paths = export_mission(simulation, "exports")
```

## Project structure

```text
simulator/
├── app.py                     Streamlit composition and controls
├── caiman_sim/
│   ├── crypto_layer.py        HKDF keys, nonce and replay window
│   ├── packets.py             encrypted payload and relay frame
│   ├── compact_protocol.py    fixed 32-byte nRF24 wire codec
│   ├── network.py             transport interface and flooding mesh
│   ├── robot.py               movement, battery and commands
│   ├── telemetry.py           coherent virtual sensors
│   ├── bathymetry.py          coastal seabed and coordinated route planner
│   ├── base_station.py        provisioning and command state
│   ├── simulation.py          step-driven mission coordinator
│   ├── mission.py             reusable exports
│   └── ui_components.py       Plotly views
├── tests/
├── assets/ocean_texture.png   local low-contrast sea texture
├── exports/
└── ARCHITECTURE.md
```

## Current limitations

- Motion is kinematic and obstacle avoidance is deliberately simple; no hydrodynamic or collision physics engine is used.
- The terrain is a deterministic, smooth synthetic coastal region rather than imported hydrographic survey data.
- The nRF24 model treats water immersion as complete link loss; antenna transition effects at the air/water boundary are not modeled.
- While submerged, the PC cannot know a current position. The dashboard freezes the last received fix; an onboard INS/DVL/dead-reckoning estimate would remain unavailable to the vessel until a surface contact.
- Surface rendezvous scheduling is deterministic. It does not yet optimize against measured currents, waves, surfacing energy or collision-risk forecasts.
- The fixed 32-byte frames are generated by the simulator, but their STM32 fragment/reassembly and crypto implementation is not yet present in firmware.
- GNSS and Ping2 drivers in the current firmware tree are still stubs; simulated navigation and echosounder data must not be treated as hardware-in-the-loop validation.
- OOK/BFSK are timing and loss profiles, not waveform or modem DSP simulations.
- Controlled flooding is suitable for this small prototype but does not model channel contention or medium-access control.
- The prototype group key makes relaying simple, but compromise of one provisioned robot exposes the group. The transport and key-store boundaries are designed for later per-robot keys.
- Exports are local files and there is no persistent database.
