# Operations, Experiments, and Troubleshooting

This manual covers the complete Raspberry Pi + ESP32 workflow, explains the
network arrangement, provides reproducible experiment recipes, and maps common
symptoms to likely causes.

## 1. Bench architecture

The recommended physical arrangement is:

```text
Internet / eduroam
        |
        v
Windows PC Wi-Fi
        |
        | Windows Internet Connection Sharing (ICS)
        v
PC Ethernet  =========================  Raspberry Pi eth0
                                              |
                                              | wlan0, SSID CAIMAN-HIL
                                              v
                                         ESP32 SoftAP
                                         192.168.4.1
```

This gives the Raspberry Pi two independent paths:

- `eth0` supplies Internet access through the Windows PC.
- `wlan0` is dedicated to the ESP32 HIL network.

The ESP32 does not need Internet access. It only needs power and Wi-Fi range to
the Raspberry Pi. It can therefore be placed elsewhere and powered from a USB
charger or power bank while the terminals remain on the Pi.

Keeping the HIL link and Internet on different physical interfaces avoids
trying to associate one Wi-Fi radio with two access points on different
channels. Linux virtual Wi-Fi interfaces do not create a second physical radio.

## 2. Software prerequisites

Raspberry/native tools:

- CMake;
- a C11 compiler;
- Mbed TLS with PSA Crypto development libraries;
- NetworkManager and `nmcli`;
- `tmux` for the two-pane demonstration.

ESP32 tools:

- ESP-IDF 6.0.2, currently installed at
  `/home/rasp/esp-idf-v6.0.2`;
- USB permission for the connected serial device, normally `/dev/ttyUSB0`.

Check the most important commands:

```bash
cmake --version
cc --version
nmcli --version
tmux -V
ls -l /dev/ttyUSB0
```

## 3. Build and test the shared C code

From `/home/rasp/Caiman`:

```bash
cmake -S protocol_hil -B protocol_hil/build
cmake --build protocol_hil/build
ctest --test-dir protocol_hil/build --output-on-failure
```

Expected result: both protocol and radio-simulator tests pass.

These tests cover:

- a known derived key;
- exact telemetry packing bytes;
- an exact encrypted-frame vector;
- authentication failure after tampering;
- replay duplicate and old-window rejection;
- FIFO depth and full-queue rejection;
- radio status flags and duplicate suppression;
- relative airtime at all three rates;
- logical out-of-range failure;
- UDP-envelope encoding/decoding.

They do not exercise the real ESP32 Wi-Fi stack, Linux routing, physical
nRF24 hardware, actual sensors, or RF propagation.

To discard old build products safely, it is normally enough to use a separate
build directory rather than modifying source files:

```bash
cmake -S protocol_hil -B protocol_hil/build-fresh
cmake --build protocol_hil/build-fresh
ctest --test-dir protocol_hil/build-fresh --output-on-failure
```

## 4. Configure, build, and flash the ESP32

Activate ESP-IDF in each new shell:

```bash
source /home/rasp/esp-idf-v6.0.2/export.sh
```

Then:

```bash
cd /home/rasp/Caiman/protocol_hil/esp32
idf.py set-target esp32
idf.py menuconfig
idf.py build
idf.py -p /dev/ttyUSB0 flash
```

`idf.py set-target esp32` is normally necessary only when creating or
reconfiguring the build directory. `menuconfig` is optional if defaults are
correct.

The important menu is `Caiman protocol HIL`. Default communication values are:

| Item | Default |
|---|---|
| SoftAP | `CAIMAN-HIL` |
| Password | `caiman-test` |
| Protocol port | `4210` |
| Diagnostic port | `4211` |
| Telemetry period | `1000 ms` |
| LED | GPIO 2 |
| Rate | 250 kbps |
| Auto-ACK | enabled |
| Retries | 3 |
| Retry delay | 500 us |

Monitor the ESP32 locally:

```bash
idf.py -p /dev/ttyUSB0 monitor
```

Exit with `Ctrl+]`. A serial monitor cannot be opened by two processes at once.

## 5. Connect the HIL network

Power the ESP32 and confirm that `CAIMAN-HIL` appears:

```bash
nmcli device wifi list ifname wlan0
```

Bring up the saved profile:

```bash
sudo nmcli connection up caiman-hil ifname wlan0
```

Or create it:

```bash
sudo nmcli device wifi connect "CAIMAN-HIL" \
  password "caiman-test" ifname wlan0
```

Inspect active connections and addresses:

```bash
nmcli connection show --active
ip -brief address show wlan0
ip route get 192.168.4.1
```

The last command should select `wlan0`. Test basic IP reachability:

```bash
ping -c 3 192.168.4.1
```

A successful ping only proves IP reachability. It does not prove that Caiman
authentication, telemetry decoding, or the simulated nRF state machine works.

## 6. Windows Internet Connection Sharing

On the Windows PC, open the properties of the Internet-connected Wi-Fi adapter:

1. Open **Control Panel > Network and Internet > Network Connections**.
2. Right-click the Wi-Fi adapter that has Internet access.
3. Choose **Properties > Sharing**.
4. Enable **Allow other network users to connect through this computer's
   Internet connection**.
5. Select the Ethernet adapter connected to the Raspberry Pi if Windows shows
   a home-network connection selector.

The **Settings/Services** list is for inbound service forwarding and is not
needed merely to give the Pi outbound Internet access. The second checkbox that
allows other users to control the shared connection is also not required for
basic sharing.

On the Raspberry Pi, confirm the Internet route uses Ethernet:

```bash
ip route show default
ip route get 1.1.1.1
```

Confirm the two destinations take different paths:

```bash
ip route get 192.168.4.1
ip route get 1.1.1.1
```

The first should use `wlan0`; the second should use `eth0`. Windows ICS often
assigns a private Ethernet subnet automatically. Avoid hard-coding it unless
diagnosis shows DHCP is unavailable.

## 7. Run the demonstration

```bash
cd /home/rasp/Caiman/protocol_hil
./demo.sh
```

The script connects the HIL Wi-Fi profile and starts two `tmux` panes:

```text
+--------------------------------+--------------------------------+
| ESP32 diagnostic channel      | Raspberry BASE                 |
| UDP 4211                      | UDP 4210                       |
| seq / attempt / TX_DS / error | authenticate / replay / decode |
+--------------------------------+--------------------------------+
```

Useful `tmux` controls:

| Action | Keys |
|---|---|
| Move to another pane | `Ctrl+B`, then an arrow key |
| Detach, leaving programs running | `Ctrl+B`, then `D` |
| Stop the program in the selected pane | `Ctrl+C` |
| List sessions | `tmux ls` |
| Reattach | `tmux attach` |

The diagnostic pane is out-of-band observability, not part of the Caiman
protocol. The BASE pane is the authoritative view of successfully validated
application samples.

### Run components separately

BASE receiver, continuously:

```bash
cd /home/rasp/Caiman/protocol_hil
./build/caiman_pi 192.168.4.1 4210
```

BASE receiver, stop after five accepted samples:

```bash
./build/caiman_pi 192.168.4.1 4210 --count 5
```

ESP32 diagnostic listener:

```bash
./build/caiman_esp_log 4211
```

The BASE command syntax is:

```text
caiman_pi [ESP_IP] [PORT] [--count N]
```

Defaults are `192.168.4.1`, port `4210`, and no count limit.

## 8. Expected healthy behavior

With zero injected loss:

1. The ESP32 reports that its SoftAP started.
2. It learns the Raspberry Pi address when the Pi joins.
3. It generates an eight-byte telemetry payload once per second.
4. It builds and encrypts a 32-byte Caiman frame.
5. The simulated link sends it and receives an Auto-ACK.
6. ESP32 reports `TX_DS` and flashes the blue LED for 100 ms.
7. BASE reports `RX_DR`, authenticates and decrypts the frame, checks replay,
   then prints telemetry.
8. Sequence values increase. No accepted sample repeats a sequence/fragment.

The link-quality field in a sample describes the previous send:

- first-attempt success approaches 100%;
- additional retry attempts reduce it;
- `MAX_RT` makes the next generated value 0%.

This one-sample delay prevents the current frame from claiming a result that is
not known until after it has been transmitted.

## 9. Reproducible experiments

Always record both endpoint settings. Unless noted, leave the ESP32 at its
default profile and set impairments only on Raspberry.

### Baseline

```bash
./build/caiman_pi 192.168.4.1 4210 --count 10
```

Expected: ten accepted frames, increasing sequences, approximately 100% link
quality, and no retries or `MAX_RT`.

### Moderate deterministic loss

```bash
CAIMAN_NRF_LOSS=35 \
CAIMAN_NRF_SEED=7 \
./build/caiman_pi 192.168.4.1 4210 --count 10
```

Expected: retries, possibly duplicate link packets after ACK loss, sequence
gaps if some messages reach `MAX_RT`, and reduced subsequent link-quality
values. The exact sequence is repeatable for the same software/configuration.

### Complete failure

```bash
CAIMAN_NRF_LOSS=100 ./demo.sh
```

Expected: the ESP32 exhausts attempts and reports `MAX_RT`; the LED does not
flash for those failed outbound messages; BASE accepts no new telemetry.

### Range curve

Run separate trials at 70, 80, 90, and 100 metres with a 100-metre logical
range:

```bash
CAIMAN_NRF_DISTANCE_M=80 \
CAIMAN_NRF_RANGE_M=100 \
CAIMAN_NRF_SEED=42 \
./demo.sh
```

Expected: no range-added loss through 70%, then progressively greater
probability; 100% loss at or beyond the range limit. This is a synthetic curve,
not a prediction of real metres.

### Interference plus loss

```bash
CAIMAN_NRF_LOSS=10 \
CAIMAN_NRF_INTERFERENCE=20 \
CAIMAN_NRF_SEED=42 \
./demo.sh
```

Expected: a combined base chance of 30%, before any range penalty.

### Retry policy comparison

```bash
CAIMAN_NRF_LOSS=40 \
CAIMAN_NRF_RETRIES=0 \
CAIMAN_NRF_SEED=9 \
./demo.sh
```

Repeat with retries 3 and 10. More retries can improve delivery probability but
consume time and energy and delay reporting a final failure.

### Data-rate mismatch

If ESP32 remains at 250 kbps:

```bash
CAIMAN_NRF_RATE=1m ./demo.sh
```

Expected: the BASE treats frames as invisible and the sender reaches `MAX_RT`.
Restore `250k` afterward. To test a working 1 Mbps link, select 1 Mbps in ESP32
`menuconfig`, rebuild/flash it, and use `CAIMAN_NRF_RATE=1m` on Raspberry.

### Auto-ACK disabled

Auto-ACK policy should match on both sides. Configure the ESP32 with Auto-ACK
disabled, rebuild and flash, then use:

```bash
CAIMAN_NRF_AUTO_ACK=0 ./demo.sh
```

Without Auto-ACK, successful transmission means the sender completed its send;
it does not mean the receiver confirmed reception. Application security checks
remain unchanged.

### Long-duration soak test

```bash
CAIMAN_NRF_LOSS=10 \
CAIMAN_NRF_SEED=1234 \
./build/caiman_pi 192.168.4.1 4210
```

Observe sequence continuity across ESP32 resets, memory use, unexpected
watchdogs, FIFO stalls, recovery after disconnect/reconnect, and stable routing.

## 10. Troubleshooting by symptom

### `CAIMAN-HIL` does not appear

Likely causes:

- ESP32 is unpowered or repeatedly resetting.
- Firmware was not flashed successfully.
- The SoftAP SSID was changed in `menuconfig`.
- The Raspberry Wi-Fi interface is disabled or blocked.

Checks:

```bash
ls -l /dev/ttyUSB0
nmcli radio wifi
rfkill list
nmcli device wifi rescan ifname wlan0
nmcli device wifi list ifname wlan0
```

Open `idf.py monitor` and look for boot/reset errors and the SoftAP startup log.

### Wi-Fi connects, but BASE says it is waiting

Likely causes:

- ESP32 has not learned the Pi DHCP address yet.
- Wrong ESP IP or UDP port.
- ESP and Pi are using different simulated data rates.
- ESP32 sender task failed or firmware is resetting.
- Another process owns the UDP port.
- Route to `192.168.4.1` uses the wrong interface.

Checks:

```bash
ip route get 192.168.4.1
ping -c 3 192.168.4.1
ss -lunp | grep -E ':(4210|4211)\b'
nmcli connection show --active
```

Run the serial monitor and both applications separately to isolate which stage
is silent.

### ESP32 reports `MAX_RT` continuously

Check, in order:

1. BASE receiver is running and bound to port 4210.
2. Both endpoints use the same data rate.
3. Auto-ACK expectations match.
4. Loss/interference is not 100%.
5. Distance is less than range.
6. The Raspberry firewall permits the UDP traffic.
7. The ESP32 learned the correct Raspberry address.

Print relevant shell variables:

```bash
env | grep '^CAIMAN_NRF_'
```

Unset an accidental override in that shell, for example:

```bash
unset CAIMAN_NRF_LOSS
```

### Frames arrive but authentication fails

Likely causes:

- endpoints use different key/mission fixtures;
- one endpoint was built from incompatible protocol source;
- a frame or header was corrupted intentionally or accidentally;
- nonce/header serialization changed on one side only.

Rebuild native tests first. Then rebuild and flash the ESP32 from the same
working tree used for the Raspberry binary. Do not “fix” this by skipping tag
verification.

### Frames are rejected as replayed

A repeated sequence/fragment was already accepted or is too far behind the
highest sequence. Ordinary link retransmissions should usually be suppressed
by the radio model before reaching this stage.

If a newly reflashed/erased ESP32 begins again at old sequence values while the
BASE process still holds its replay window, restart the test deliberately only
after understanding why persistent NVS state was lost. In production, clearing
replay state is a security-sensitive operation.

### Blue LED never flashes

The LED indicates successful `TX_DS`, not merely that a telemetry sample was
generated. Check for `MAX_RT`, missing BASE receiver, or total impairment.

Also check:

- the board actually connects its onboard blue LED to GPIO 2;
- LED polarity and board model;
- `Caiman protocol HIL > activity LED GPIO` was not changed;
- another board function does not own that pin.

Some ESP32 development boards have no user LED on GPIO 2. The protocol can
still work; use logs or wire an external LED with an appropriate resistor and
configure the GPIO.

### Raspberry loses Internet during the HIL test

The HIL Wi-Fi has no Internet gateway. Internet should use Ethernet/Windows
ICS. Check:

```bash
ip -brief address show eth0
ip route show default
ip route get 1.1.1.1
nmcli connection show --active
```

Confirm Windows sharing is enabled on the Internet Wi-Fi adapter toward the
correct Ethernet adapter. Do not configure the ESP32 network as the Pi's
default Internet route.

### `idf.py` is not found

Activate the environment in the same terminal:

```bash
source /home/rasp/esp-idf-v6.0.2/export.sh
```

### `/dev/ttyUSB0` is missing or busy

Check the cable, power, and detected serial devices:

```bash
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

Close any existing `idf.py monitor`, terminal emulator, or other program using
the serial port. Reconnect the board and verify the device name; it can change.

### `tmux` does not open a visible desktop terminal

`demo.sh` starts a terminal multiplexer inside the terminal where it is run. It
does not launch a new graphical terminal window. Run it interactively in the
SSH/local shell where you want to see the panes.

### Native tests pass but the HIL link fails

This usually points outside the deterministic shared libraries: routing,
ports, firmware version, ESP32 reset, endpoint configuration mismatch, or UDP
adapter behavior. Passing unit tests narrows the problem; it does not validate
the live network.

## 11. Test result template

Use a consistent record for comparisons:

```text
Test name:
Date/time:
Git commit / working-tree state:
ESP32 build configuration:
Raspberry CAIMAN_NRF_* environment:
ESP32 power source and position:
Duration:
Generated sequences:
BASE accepted frames:
Retries:
Duplicates suppressed:
MAX_RT count:
Authentication failures:
Replay rejections:
Observed latency notes:
Unexpected behavior:
```

Do not compare loss/range trials unless the software versions, endpoint
settings, seed, and observation interval are known.

## 12. Moving to STM32 + real nRF24L01+

The migration boundary is intentionally clear:

```text
Keep                              Replace
-------------------------------   ----------------------------------
caiman_protocol.c/.h              UDP socket adapter
telemetry wire schema             nRF24 software envelope
key/nonce rules                   simulated timing/loss decisions
frame authentication              ESP32 SoftAP endpoint discovery
replay rules                      ESP32-generated sensor values
32-byte frame                     software-only IRQ representation
```

A practical migration sequence:

1. Compile `shared/caiman_protocol` for the STM32 toolchain and run the same
   golden vectors on target if possible.
2. Implement an nRF24 driver for SPI commands, CE, IRQ, register setup, FIFO
   management, channel, address, data rate, CRC, Auto-ACK, ARC, and ARD.
3. Give the driver a 32-byte send/receive interface so Caiman does not depend
   on SPI details.
4. Replace generated telemetry with real, range-checked sensor inputs.
5. Implement crash-safe monotonic sequence storage suitable for the STM32's
   flash/endurance constraints.
6. Provision non-public mission keys and prefixes securely.
7. Test two real modules on the bench at short range before introducing relays
   or water-adjacent operation.
8. Compare hardware traces/events with HIL expectations: FIFO full, retry,
   duplicate, `TX_DS`, `MAX_RT`, and `RX_DR`.
9. Test power interruption, link loss, corrupted payloads, stale sequences, and
   rate/config mismatch.
10. Characterize actual range and antenna behavior in the final enclosure and
    environment.

Do not copy the HIL master key, mission prefix, Wi-Fi credentials, or synthetic
range curve into the deployed system.

## 13. Glossary

| Term | Plain-language meaning |
|---|---|
| ACK | An acknowledgement: a response saying something was received or processed. Its exact meaning depends on the layer. |
| AEAD | Encryption that also authenticates the message and selected visible metadata. |
| Airtime | Time during which a radio packet occupies the channel. |
| ARC | Automatic retransmit count: retries after the first attempt. |
| ARD | Automatic retransmit delay between attempts. |
| BASE | Base-station role, represented by the Raspberry Pi. |
| Bit packing | Placing several small integer fields into selected bits to save space. |
| Ciphertext | Encrypted bytes that are not readable without the key. |
| CRC | Error-detection code used by a radio; not a substitute for cryptographic authentication. |
| FIFO | First-in, first-out queue. The simulated nRF FIFOs contain at most three packets. |
| Fragment | One piece of a logical message that does not fit in a single payload. |
| Frame | One complete protocol unit with header, protected payload, and tag. |
| Half duplex | Communication where a radio can transmit or receive at one moment, but not both. |
| HIL | Hardware-in-the-loop: real devices run the software while part of the final hardware is simulated. |
| HKDF | A standard function that derives purpose-specific cryptographic keys. |
| IRQ | Interrupt request: a signal/event that tells the MCU the radio needs attention. |
| Kconfig | ESP-IDF's build-time configuration menu system. |
| MAX_RT | nRF status meaning all configured transmit attempts failed. |
| Nonce | A unique per-encryption value; public, but dangerous to repeat with the same key. |
| NVS | ESP32 non-volatile storage, used here to reserve sequence numbers across resets. |
| PID | Small radio packet identifier used to recognize retransmissions. |
| Plaintext | Original readable data before encryption or after verified decryption. |
| Quantization | Converting a continuous/decimal value into a limited integer representation. |
| Replay | Re-sending an old valid message as if it were new. |
| R1 | Vehicle/node role represented by the ESP32, address 1. |
| RX_DR | Receive-data-ready radio status. |
| SoftAP | A device acting as a Wi-Fi access point; here, the ESP32. |
| SPI | Short-distance synchronous bus between an MCU and peripherals such as the nRF24. |
| Tag | Cryptographic authenticator that detects modification or forgery. |
| TX_DS | Transmit-data-sent radio status. |
| UDP | Simple connectionless IP transport with no built-in delivery or ordering guarantee. |

## 14. Useful source locations

| Path | Purpose |
|---|---|
| `protocol_hil/README.md` | Project overview and quick start. |
| `protocol_hil/docs/PROTOCOL_GUIDE.md` | Caiman frame/security explanation. |
| `protocol_hil/docs/NRF24_EMULATION.md` | Radio-model definition and limits. |
| `protocol_hil/shared/` | Portable protocol and simulator source. |
| `protocol_hil/raspberry/` | BASE program and diagnostic listener. |
| `protocol_hil/esp32/` | ESP-IDF firmware. |
| `protocol_hil/tests/` | Native deterministic tests. |
| `protocol_hil/demo.sh` | Live two-pane launcher. |
