# nRF24L01+ Emulation Guide

This document explains which nRF24L01+ behaviors are reproduced by the HIL
software, how they are carried over Wi-Fi/UDP, and where the model necessarily
differs from a real radio.

## 1. Why emulate the radio?

The final system is expected to use an STM32 connected to an nRF24L01+ over
SPI. The current bench has a Raspberry Pi and one ESP32 but no pair of nRF24
modules. Sending Caiman frames directly over UDP would test encryption and
parsing, but it would ignore important radio constraints.

The emulator inserts a link model between Caiman and UDP:

```text
Caiman 32-byte frame
        |
        v
software nRF24
  FIFO, state, packet ID, Auto-ACK, retries, timing, IRQ flags, impairments
        |
        v
12-byte simulation envelope + Caiman frame
        |
        v
UDP over the ESP32 SoftAP
```

The software envelope is test infrastructure. It is never part of a production
Caiman frame and will disappear when a real nRF24 driver replaces the UDP
adapter.

## 2. What the model reproduces

### Three-packet FIFOs

The nRF24 has shallow queues. The simulator implements:

- a transmit FIFO with three entries;
- a receive FIFO with three entries;
- rejection when a full FIFO is asked to accept another payload;
- data payloads from 1 through 32 bytes (the modeled link ACK has no payload).

This exposes an important embedded-systems problem: a producer can generate
data faster than the radio or consumer can drain it. Larger host queues would
hide that problem.

### Radio states and half duplex

Each logical radio transitions among:

```text
STANDBY <----> TX
    |
    `--------> RX
```

It cannot transmit and receive user data simultaneously. During Auto-ACK, the
sender must turn from TX to RX and the receiver from RX to TX. This is
**half-duplex** behavior.

### Data rates

The model supports the nRF24L01+ rates:

- 250 kbps;
- 1 Mbps;
- 2 Mbps.

The rate changes calculated airtime. Both endpoints must use the same value. A
mismatch makes the packet invisible to the receiver, so the sender eventually
reports `MAX_RT` when Auto-ACK is enabled.

### Auto-ACK and retransmission

With Auto-ACK enabled:

1. The sender transmits a data payload.
2. The receiver accepts it if the link configuration and impairment model
   permit reception and its FIFO has space.
3. The receiver returns a short simulated link ACK.
4. The sender reports success if that ACK arrives.
5. Otherwise it waits the configured retry delay and tries again.

`retry_count`, equivalent to the nRF24 ARC setting, counts retries after the
first attempt. The default value of 3 therefore permits up to 4 transmissions:

```text
initial attempt + 3 retries = 4 total attempts
```

The retry delay models ARD and defaults to 500 microseconds. The allowed HIL
configuration range is 250 through 4000 microseconds.

Wi-Fi, FreeRTOS, and Linux cannot reliably exchange an ACK within real nRF24
microsecond timing. The UDP adapter therefore uses a practical 20 ms host ACK
timeout while still accounting for configured radio timing. This makes the
state/result logic useful but means measured wall-clock retry latency is not a
hardware timing measurement.

### Duplicate suppression

Sometimes the receiver gets the data, but the return ACK is lost. The sender
then retransmits the same packet. A correct link must acknowledge it again
without giving the payload to the application twice.

The simulator identifies a retry using:

- a two-bit packet identifier (PID), cycling through 0, 1, 2, and 3;
- a 32-bit token derived from the payload with FNV-1a.

A matching PID and token is treated as a link duplicate. This is separate from
Caiman replay protection:

| Duplicate system | Scope | Purpose |
|---|---|---|
| nRF PID + token | Link attempt | Hide retry copies from the receiving application. |
| Caiman sequence + fragment | Secure protocol | Reject repeated or stale authenticated messages. |

Both are valuable. The first handles ordinary radio retry mechanics; the
second remains necessary against replays outside one radio exchange.

### IRQ/status events

The modeled status flags match common nRF24 meanings:

| Flag | Hex bit | Meaning |
|---|---:|---|
| `RX_DR` | `0x40` | Receive data ready. |
| `TX_DS` | `0x20` | Transmit completed successfully. |
| `MAX_RT` | `0x10` | Maximum retry count reached without success. |

These flags contribute to a modeled IRQ condition. In the HIL build they are
software state and log events; there is no physical active-low IRQ pin.

The ESP32 blue LED on GPIO 2 pulses for 100 ms after telemetry reaches `TX_DS`
or after a new inbound application payload is delivered. It remains off while
idle and does not pulse for suppressed retry duplicates.

## 3. Default profile

| Setting | Default |
|---|---:|
| Data rate | 250 kbps |
| Auto-ACK | enabled |
| Retry count | 3 |
| Retry delay | 500 us |
| SPI clock | 8 MHz |
| CE startup/settle | 130 us |
| RX/TX turnaround | 130 us |
| Address width for airtime | 5 bytes |
| CRC width for airtime | 2 bytes |
| Random loss | 0% |
| Interference | 0% |
| Logical distance | 1 m |
| Logical range | 100 m |
| PRNG seed | `0xc41a4e24` |

The SPI, CE, address, CRC, and turnaround defaults are internal simulator
configuration. The commonly varied settings are exposed through ESP-IDF
Kconfig and Raspberry environment variables.

## 4. Timing model

The model accounts for three main transmission costs.

### SPI loading time

The MCU must copy a command byte and the payload into the radio:

```text
SPI time = ceil((payload bytes + 1) * 8 * 1,000,000 / SPI frequency)
```

At 8 MHz, loading a full 32-byte payload has a calculated transfer cost of 33
microseconds.

### On-air time

The packet includes more than the application payload:

```text
air bits = (preamble + address + payload + CRC) * 8
           + 9 packet-control bits

airtime = ceil(air bits * 1,000,000 / data rate)
```

The model uses a two-byte preamble at 250 kbps and a one-byte preamble at 1 or
2 Mbps. With the default five-byte address and two-byte CRC, a 32-byte payload
has approximately:

| Rate | Calculated data-packet airtime |
|---|---:|
| 250 kbps | 1,348 us |
| 1 Mbps | 329 us |
| 2 Mbps | 165 us |

These are model calculations, not oscilloscope measurements.

### State changes and ACK

The transmit path also includes CE startup. With Auto-ACK, it includes RX/TX
turnaround and the airtime of the short ACK packet. Retries add the configured
ARD delay and repeat transmission work.

The calculated values enforce relative cost and minimum ordering. Host
scheduling, UDP, and Wi-Fi typically dominate the wall-clock observation.

## 5. The impairment model

The model can deliberately discard a data packet or ACK. It combines three
ideas:

1. Configured random loss percentage.
2. Configured interference percentage.
3. Additional loss close to, or beyond, the configured range.

Conceptually:

```text
chance = configured loss + configured interference

if distance >= range:
    chance = 100%
else if distance is above 70% of range:
    chance += 2 * (distance percentage - 70)

chance is capped at 100%
```

Examples with no base loss or interference:

| Distance / range | Added range loss |
|---:|---:|
| 50% | 0% |
| 70% | 0% |
| 80% | 20% |
| 90% | 40% |
| 99% | 58% |
| 100% or more | 100% |

The model uses a deterministic xorshift32 pseudo-random generator. A fixed
seed makes a failure sequence repeatable, which is helpful for debugging and
automated tests.

The percentage is a model parameter, not a calibrated prediction of real
packet error rate at that distance. A real result depends on antennas, supply
quality, orientation, obstacles, RF channel, hardware variation, and many
other factors.

The Raspberry adapter can impair both inbound data and the outgoing simulated
ACK. Therefore a setting such as 20% is not necessarily the same as exactly
20% missing application samples: retransmissions may recover loss, while ACK
loss may create extra attempts and duplicates.

## 6. Raspberry runtime configuration

Set variables immediately before `./demo.sh` or `caiman_pi`:

| Variable | Allowed/meaning | Default |
|---|---|---:|
| `CAIMAN_NRF_RATE` | `250k`, `1m`/`1Mbps`, or `2m`/`2Mbps` | `250k` |
| `CAIMAN_NRF_AUTO_ACK` | `0` disables; nonzero enables | `1` |
| `CAIMAN_NRF_RETRIES` | 0–15 | `3` |
| `CAIMAN_NRF_RETRY_DELAY_US` | 250–4000 | `500` |
| `CAIMAN_NRF_LOSS` | 0–100 percent | `0` |
| `CAIMAN_NRF_INTERFERENCE` | 0–100 percent | `0` |
| `CAIMAN_NRF_DISTANCE_M` | non-negative logical metres | `1` |
| `CAIMAN_NRF_RANGE_M` | positive logical metres | `100` |
| `CAIMAN_NRF_SEED` | unsigned deterministic seed | built-in seed |

The receiver validates the final loaded configuration and exits when it detects
an invalid profile. Use only the documented numeric ranges: environment values
are parsed as unsigned integers and then stored in the simulator field width,
so extremely large shell values are not a meaningful test input. The current
parser treats an unrecognized rate string as the 250 kbps default; use the
documented spelling and confirm the printed `NRF profile` line before
collecting results.

For example:

```bash
CAIMAN_NRF_LOSS=35 \
CAIMAN_NRF_RETRIES=5 \
CAIMAN_NRF_SEED=7 \
./demo.sh
```

Environment values affect only the Raspberry side. ESP32 defaults are under
`Caiman protocol HIL` in `idf.py menuconfig`; changing them requires rebuilding
and flashing the firmware. Data rates must match. Auto-ACK expectations should
also be configured consistently on both endpoints.

## 7. ESP32 build-time configuration

Run:

```bash
source /home/rasp/esp-idf-v6.0.2/export.sh
cd /home/rasp/Caiman/protocol_hil/esp32
idf.py menuconfig
```

Under `Caiman protocol HIL`, the firmware exposes:

- SoftAP SSID and password;
- protocol and diagnostic UDP ports;
- activity LED GPIO;
- telemetry period from 100 to 60,000 ms;
- data rate;
- Auto-ACK;
- retry count and delay;
- loss and interference percentages;
- logical distance and range.

After changing a value:

```bash
idf.py build
idf.py -p /dev/ttyUSB0 flash
```

## 8. UDP simulation envelope

UDP must carry information that real nRF hardware would maintain internally,
such as packet ID and ACK identity. Each HIL datagram therefore begins with a
12-byte envelope:

| Offset | Size | Meaning |
|---:|---:|---|
| 0 | 4 | Magic bytes `NRF+` |
| 4 | 1 | Envelope version (`1`) |
| 5 | 1 | Packet kind plus data-rate code |
| 6 | 1 | Two-bit PID value |
| 7 | 1 | Simulated payload length |
| 8 | 4 | Payload token |
| 12 | variable | Simulated radio payload |

A normal Caiman data datagram is therefore:

```text
12-byte HIL envelope + 32-byte Caiman frame = 44-byte UDP payload
```

A simulated ACK has no application payload and uses only the 12-byte envelope.

The envelope is not encrypted because it represents radio metadata, not the
Caiman application frame. The inner frame retains its 8-byte authenticated
header, 8-byte ciphertext, and 16-byte tag.

## 9. Wi-Fi and endpoint discovery

The ESP32 is a SoftAP at `192.168.4.1`. When the Raspberry Pi joins, the ESP32
learns the client's assigned address from the DHCP-client event and uses it as
the BASE destination on UDP port 4210.

The Raspberry receiver binds that local port and accepts packets only from the
configured ESP32 IP and port. The separate diagnostic listener uses port 4211.

The diagnostic channel reports safe HIL events such as sequence, payload
length, `TX_DS`, retry, or `MAX_RT`. It does not carry keys or plaintext
telemetry and is not a production protocol channel.

UDP is intentionally a simple carrier. It has no built-in delivery guarantee,
ordering guarantee, or application acknowledgement. Delivery behavior in the
test comes from the software radio model and Caiman receiver checks.

## 10. What the model cannot prove

Passing every emulator test does not prove that the hardware link will work.
The following need two real modules and target boards:

- SPI mode, maximum clock, command ordering, and register values;
- CE pulse and setup timing at pins;
- active-low IRQ integration and interrupt races;
- power-supply noise and the nRF's transient current requirements;
- module/antenna quality and orientation;
- address, channel, CRC, and Enhanced ShockBurst interoperability;
- genuine RF packet loss and retransmission timing;
- operation near water, inside the enclosure, and at intended range;
- behavior with every relay/device active on the same channel.

Wi-Fi also has its own retries beneath UDP. Those invisible retries can make
the transport appear more reliable or slower than an nRF24 channel. Injected
loss is applied by the HIL software so protocol failure paths are still
observable.

## 11. Recommended experiment sequence

Run tests in increasing complexity:

1. **Native unit tests:** verify exact bytes and deterministic state logic.
2. **Clean HIL link:** zero impairment, five accepted telemetry frames.
3. **Random loss:** fixed seed and moderate loss; observe retry and duplicate
   suppression.
4. **Total loss:** force `MAX_RT` and confirm the application does not invent a
   successful sample.
5. **Range boundary:** compare 70%, 80%, 90%, and 100% logical distance.
6. **Rate mismatch:** intentionally make endpoints disagree; confirm failure.
7. **Recovery:** restore matching settings without changing protocol state.
8. **Long run:** look for sequence persistence, memory leaks, FIFO stalls, and
   unexpected resets.
9. **Hardware-in-the-loop:** repeat the cases with actual STM32/nRF24 boards.

Record firmware version, both endpoint configurations, PRNG seed, duration,
sent frames, accepted frames, retries, duplicate count, `MAX_RT`, and observed
latency for a reproducible test report.

## 12. Source-code map

| File | Responsibility |
|---|---|
| `shared/include/nrf24_sim.h` | Radio model API, constants, state, and flags. |
| `shared/src/nrf24_sim.c` | FIFO, timing, packet IDs, envelope, loss, and transitions. |
| `tests/test_nrf24_sim.c` | FIFO depth, flags, duplicates, rates, range, and wire codec. |
| `raspberry/main.c` | POSIX UDP link adapter and runtime settings. |
| `esp32/main/main.c` | FreeRTOS/UDP link adapter, telemetry sender, and LED. |
| `esp32/main/Kconfig.projbuild` | ESP32 menu configuration. |

The model is deliberately kept in `shared/` so its deterministic behavior can
be compiled and tested natively, independently from networking and FreeRTOS.
