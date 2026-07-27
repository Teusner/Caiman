# Caiman Protocol HIL

This project tests the Caiman communication protocol between a Raspberry Pi
and an ESP32 without requiring two nRF24L01+ modules. The ESP32 Wi-Fi radio and
UDP carry the test traffic, while a software model reproduces the nRF24L01+
constraints that matter to the protocol.

The goal is not to claim that Wi-Fi behaves physically like an nRF24 radio. The
goal is to run the real C protocol implementation, real 32-byte Caiman frames,
authenticated encryption, replay protection, retransmission logic, and
radio-like state transitions on two separate devices before the final STM32 +
nRF24 hardware is available.

**HIL** means **Hardware-in-the-Loop**: real hardware participates in the test
while one unavailable part of the final system is simulated. Here, the
Raspberry Pi and ESP32 are real and execute the actual C code; the missing pair
of nRF24L01+ radios is the simulated part.

> **Important:** this is a development test bench. Its keys, mission identifier,
> Wi-Fi password, and generated sensor values are public fixtures. They are not
> suitable for a real vehicle or mission.

## Start here

If communication protocols are new to you, picture the system as four layers:

```text
Telemetry values
  x, y, depth, battery, leak, ...
             |
             v
Caiman protocol
  pack -> identify -> encrypt -> authenticate -> prevent replay
             |
             v
nRF24 software model
  3-packet FIFO -> airtime -> Auto-ACK -> retry -> IRQ result
             |
             v
Wi-Fi / UDP test transport
  moves the simulated radio packet between the ESP32 and Raspberry Pi
```

Only the bottom layer changes when real radio hardware is introduced. The
Caiman frame and its security rules are already written as portable C code.

The current demonstration sends one realistic telemetry sample every second:

```text
ESP32 (vehicle R1)  ------ protected TELEMETRY ------>  Raspberry Pi (BASE)
       GPIO 2 LED                                         terminal output
       flashes on TX_DS                                   decrypts and displays
```

There is no application-level PING/PONG loop in this demo. The link layer may
still return a simulated nRF24 Auto-ACK; those are different concepts.

## What is validated

- The immutable 32-byte Caiman radio frame.
- An exact 8-byte header and 8-byte bit-packed telemetry payload.
- HKDF-SHA-256 mission-key derivation.
- ChaCha20-Poly1305 encryption and a full 16-byte authentication tag.
- A unique 12-byte nonce made from mission, source, sequence, and fragment.
- Persistent ESP32 sequence allocation and receiver-side replay detection.
- Periodic authenticated telemetry from R1/ESP32 to BASE/Raspberry Pi.
- Three-entry transmit and receive FIFOs.
- 250 kbps, 1 Mbps, and 2 Mbps packet airtime calculations.
- Enhanced ShockBurst-style Auto-ACK, retry delay/count, and duplicates.
- `RX_DR`, `TX_DS`, `MAX_RT`, and IRQ behavior.
- SPI transfer, CE startup, and RX/TX turnaround time.
- Deterministic loss, interference, and logical range impairment.
- Half-duplex state transitions: a radio cannot transmit and receive at once.

## What still needs real nRF24 hardware

- Electrical SPI behavior and register access.
- Actual CE and IRQ pin timing/voltage behavior.
- Real nRF24 CRC generation and reception.
- Antenna performance, channel noise, interference, and physical range.
- Propagation at the air/water boundary.
- Real multi-node contention and relay placement effects.

The simulator enforces radio timing as a minimum. Linux, FreeRTOS, Wi-Fi, and
UDP scheduling can add extra delay, so wall-clock latency is not a prediction
of the final nRF24 system.

## Repository layout

```text
protocol_hil/
|-- shared/       portable Caiman protocol and nRF24 simulator
|-- raspberry/    POSIX/UDP BASE application
|-- esp32/        ESP-IDF R1 firmware and SoftAP
|-- tests/        native golden-vector, security, replay, and radio tests
|-- docs/         detailed guides and reference material
|-- demo.sh       two-pane live demonstration
`-- CMakeLists.txt
```

## Quick start

### 1. Build and run the native tests

From the repository root:

```bash
cmake -S protocol_hil -B protocol_hil/build
cmake --build protocol_hil/build
ctest --test-dir protocol_hil/build --output-on-failure
```

The native build requires CMake, a C11 compiler, and Mbed TLS with PSA Crypto.

### 2. Build and flash the ESP32

The Raspberry Pi currently has ESP-IDF 6.0.2 in
`/home/rasp/esp-idf-v6.0.2`:

```bash
source /home/rasp/esp-idf-v6.0.2/export.sh
cd /home/rasp/Caiman/protocol_hil/esp32
idf.py set-target esp32        # required only for a new build directory
idf.py menuconfig              # optional: change HIL radio settings
idf.py build
idf.py -p /dev/ttyUSB0 flash
```

To inspect the serial log directly:

```bash
idf.py -p /dev/ttyUSB0 monitor
```

Exit the monitor with `Ctrl+]`.

### 3. Connect the Raspberry Pi to the ESP32

The ESP32 creates this test network by default:

| Setting | Value |
|---|---|
| SSID | `CAIMAN-HIL` |
| Password | `caiman-test` |
| ESP32 address | `192.168.4.1` |
| Protocol UDP port | `4210` |
| Diagnostic UDP port | `4211` |

Use the saved NetworkManager profile:

```bash
sudo nmcli connection up caiman-hil ifname wlan0
```

If the profile does not exist yet:

```bash
sudo nmcli device wifi connect "CAIMAN-HIL" \
  password "caiman-test" ifname wlan0
```

Confirm that packets for the ESP32 use Wi-Fi:

```bash
ip route get 192.168.4.1
```

For stable experiments, use Ethernet for Raspberry Pi Internet access and keep
its Wi-Fi radio dedicated to `CAIMAN-HIL`.

### 4. Run the live demonstration

```bash
cd /home/rasp/Caiman/protocol_hil
./demo.sh
```

The script opens a `tmux` session with two panes:

- Left: safe ESP32 diagnostic events on UDP port 4211.
- Right: the BASE authenticating, decrypting, and decoding telemetry on 4210.

Detach without stopping it with `Ctrl+B`, then `D`. Stop a foreground program
with `Ctrl+C`.

You can also run only the BASE receiver:

```bash
./build/caiman_pi 192.168.4.1 4210 --count 5
```

`--count 5` exits after five accepted telemetry samples. Without it, the BASE
runs continuously.

## Reading the output

A normal sample resembles:

```text
NRF Auto-ACK pid=2 sent
NRF IRQ RX_DR pid=2 fifo=1/3
NRF IRQ RX_DR cleared fifo=0/3
TELEMETRY seq=123 R1->BASE | x=124.0m y=456.9m depth=12.20m \
bottom=18.60m battery=99.0% link=100% leak=no GNSS=no
FRAME 32B encrypted=<64 hexadecimal characters>
```

The exact formatting may vary, but the important events are:

| Event | Meaning |
|---|---|
| `RX_DR` | A new simulated radio payload reached the receive FIFO. |
| `TX_DS` | Delivery succeeded, normally after an Auto-ACK. |
| `MAX_RT` | Every configured transmission attempt failed. |
| retry | The sender did not receive an Auto-ACK and tried again. |
| duplicate | A retransmission was already delivered and is not delivered twice. |
| replay rejected | A valid-looking Caiman sequence/fragment was already accepted or is too old. |

The blue onboard LED on ESP32 GPIO 2 is normally dark. It lights for 100 ms
after outbound telemetry reaches `TX_DS`, or after an inbound Caiman payload is
delivered to the ESP32 application. A link-layer retransmission does not create
a second application event.

## Try controlled failures

Raspberry-side impairments use environment variables and do not require a
rebuild. This example injects a repeatable 35% base loss:

```bash
CAIMAN_NRF_LOSS=35 CAIMAN_NRF_SEED=7 ./demo.sh
```

Force all attempts to fail:

```bash
CAIMAN_NRF_LOSS=100 ./demo.sh
```

Model a device at the range limit:

```bash
CAIMAN_NRF_DISTANCE_M=100 \
CAIMAN_NRF_RANGE_M=100 \
./demo.sh
```

Combine impairments and retry settings:

```bash
CAIMAN_NRF_LOSS=20 \
CAIMAN_NRF_INTERFERENCE=10 \
CAIMAN_NRF_DISTANCE_M=80 \
CAIMAN_NRF_RANGE_M=100 \
CAIMAN_NRF_RETRIES=5 \
CAIMAN_NRF_RETRY_DELAY_US=750 \
CAIMAN_NRF_SEED=42 \
./demo.sh
```

Both endpoints must use the same data rate. Change the ESP32 setting with
`idf.py menuconfig`, rebuild and flash it, then run the BASE with the matching
value:

```bash
CAIMAN_NRF_RATE=1m ./demo.sh
```

Recommended Raspberry values are `250k`, `1m`, and `2m` (`1Mbps` and `2Mbps`
are also recognized aliases). A rate mismatch makes
the packet invisible, just like incompatible physical-radio configuration, and
eventually produces `MAX_RT`.

## Documentation map

- [Protocol guide](docs/PROTOCOL_GUIDE.md): frame format, telemetry packing,
  cryptography, sequences, fragmentation, and replay protection.
- [nRF24 emulation](docs/NRF24_EMULATION.md): FIFO, Auto-ACK, retries, timing,
  IRQ flags, loss/range model, UDP envelope, and limitations.
- [Operations and troubleshooting](docs/OPERATIONS_AND_TROUBLESHOOTING.md):
  complete setup, experiment recipes, network topology, common failures,
  glossary, and migration to STM32 + nRF24L01+.

## Safety and security warning

The source deliberately uses a public test master key (`00` through `1f`), the
mission identifier `CAIMAN-DEMO`, a fixed mission prefix, generated telemetry,
and a documented Wi-Fi password. Never reuse any of them in a deployed system.
Production work also needs secure key provisioning, a durable global sequence
policy, key rotation/revocation procedures, persistent receive-side replay
state where required, and a review of failure behavior.
