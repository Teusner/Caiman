# Caiman Protocol Guide

This document explains the Caiman communication protocol from first
principles. It is intended to be readable even if terms such as *frame*,
*nonce*, *authentication tag*, or *replay window* are new to you.

## 1. What a communication protocol does

Two computers cannot exchange meaningful values merely by sending arbitrary
bytes. They must agree on rules such as:

- which device sent the message and which device should receive it;
- what kind of message it is;
- where one value ends and the next begins;
- whether the message was changed or forged;
- whether it is new or a copy of an old message;
- what to do when a transmission is lost.

That agreement is a **protocol**. Caiman defines the format and security rules
for messages exchanged by mission devices. The radio is only one way to move
those messages.

This test bench currently uses these logical identities:

| Role | Device in the HIL test | Caiman address |
|---|---|---:|
| BASE | Raspberry Pi | `0` |
| R1 vehicle | ESP32 | `1` |

The current application sends `TELEMETRY` from R1 to BASE once per second.

## 2. From sensor readings to one radio frame

The transmit path is:

```text
sensor/test values
      |
      | quantize and bit-pack
      v
8-byte telemetry payload
      |
      | add type, addresses, sequence, and fragment information
      v
8-byte header + 8-byte payload
      |
      | ChaCha20-Poly1305
      v
8-byte visible authenticated header
+ 8-byte encrypted payload
+ 16-byte authentication tag
      |
      v
exactly 32 bytes
```

The receive path performs the reverse operations, but only after verifying
authenticity and freshness:

```text
32-byte frame
  -> parse header
  -> verify destination and structural rules
  -> reconstruct nonce
  -> verify authentication tag and decrypt
  -> reject duplicate/old sequence and fragment
  -> unpack telemetry fields
  -> deliver values to the application
```

The order matters. Untrusted data must not become an accepted telemetry sample
until the security and replay checks succeed.

## 3. The fixed 32-byte frame

An nRF24L01+ payload can contain at most 32 bytes. Caiman deliberately fills
that entire budget:

| Offset | Size | Content | Visible on the link? |
|---:|---:|---|---|
| 0 | 8 bytes | Header | Yes, but authenticated |
| 8 | 8 bytes | Encrypted payload | No plaintext |
| 16 | 16 bytes | Poly1305 authentication tag | Yes |
| **Total** | **32 bytes** | | |

“Visible but authenticated” means an observer can read header fields such as
the source and sequence number, but cannot modify them without invalidating the
tag. Caiman does not attempt to hide traffic metadata.

The eight payload bytes are always encrypted. If a logical message fragment
uses fewer than eight bytes, the unused bytes are padded before encryption and
the valid-length field tells the receiver how many plaintext bytes matter.

## 4. Header byte by byte

### Byte 0: control information

```text
bit:    7 6 | 5 4 3 2 | 1 | 0
        ver |   type    | A | E
```

| Field | Width | Purpose |
|---|---:|---|
| Version | 2 bits | Selects the Caiman wire-format version. Current value: `1`. |
| Message type | 4 bits | Describes the payload's meaning. |
| A | 1 bit | Application-level ACK association flag. |
| E | 1 bit | States that the payload is encrypted. |

The ACK bit is not the nRF24 Auto-ACK. It belongs to the Caiman application
header. The current periodic telemetry sets no application ACK association.

### Bytes 1 and 2: addresses

- Byte 1: source device.
- Byte 2: destination device.

In the current flow they are `1` (R1) and `0` (BASE). These fields are part of
the authentication input, so changing R1 into a fake source or redirecting a
message causes tag verification to fail.

### Bytes 3 to 5: sequence number

The sequence is an unsigned 24-bit integer. It increases for each logical
message sent by a source. It serves two security purposes:

1. It contributes to a unique encryption nonce.
2. It lets the receiver recognize old or repeated traffic.

Three bytes allow values from `0` through `16,777,215`. A production system
must define what happens before this space is exhausted; silently wrapping to
zero under the same mission key/prefix would be unsafe.

### Byte 6: fragment information

```text
bit:    7 6 5 4 | 3 2 1 0
        index   | count - 1
```

- The high nibble is the zero-based fragment index.
- The low nibble stores total fragment count minus one.

This represents 1 through 16 fragments. Each fragment carries at most eight
plaintext bytes, so the format can identify a logical payload of at most 128
bytes.

The current telemetry is exactly eight bytes and therefore uses fragment 0 of
1. The wire fields and replay logic support fragment identities, but the HIL
application does not yet implement general multi-fragment reassembly.

### Byte 7: valid plaintext length

This value is from 0 through 8 and tells the receiver how many decrypted bytes
belong to the fragment. The telemetry payload uses all 8 bytes.

### Complete header table

| Byte | Field | Current telemetry example |
|---:|---|---|
| 0 | version, type, ACK flag, encrypted flag | v1, `TELEMETRY`, no app ACK, encrypted |
| 1 | source | R1 (`1`) |
| 2 | destination | BASE (`0`) |
| 3–5 | 24-bit sequence | increasing value |
| 6 | fragment index and count | 0 of 1 |
| 7 | valid payload bytes | 8 |

## 5. Message types

The current wire format reserves the following numeric types:

| Value | Name | Intended meaning | Used by current demo? |
|---:|---|---|---|
| 0 | `TELEMETRY` | Vehicle status and sensor values | Yes |
| 1 | `COMMAND` | Instruction sent to a device | No |
| 2 | `ACK` | Application confirmation | No |
| 3 | `PING` | Application liveness request | No |
| 4 | `PONG` | Application liveness response | No |
| 5 | `ALERT` | Urgent event or condition | No |
| 6 | `KEY_ROTATE` | Key-management message | No |
| 7 | `MISSION_START` | Mission-state transition | No |
| 8 | `MISSION_STOP` | Mission-state transition | No |

The presence of a type in the enumeration defines an identifier; it does not
mean its complete application behavior has already been implemented.

## 6. Telemetry in only eight bytes

Eight bytes contain 64 bits. Caiman assigns every bit to a field:

| Field | Bits | Resolution | Encodable range |
|---|---:|---:|---:|
| X position | 14 | 0.1 m | 0 to 1638.3 m |
| Y position | 14 | 0.1 m | 0 to 1638.3 m |
| Depth | 11 | 0.01 m | 0 to 20.47 m |
| Seafloor depth | 11 | 0.01 m | 0 to 20.47 m |
| Battery | 8 | 0.5 percentage point | 0 to 127.5% |
| Link quality | 4 | 1/15 | 0 to 100% in 16 levels |
| Leak | 1 | Boolean | no/yes |
| GNSS available | 1 | Boolean | no/yes |
| **Total** | **64** | | |

The packed integer is written in big-endian byte order (most-significant byte
first). Its exact bit positions are:

```text
bit 63                                                    bit 0
| X:14 | Y:14 | depth:11 | seafloor:11 | battery:8 | LQ:4 | leak:1 | GNSS:1 |
 63..50  49..36    35..25       24..14       13..6    5..2     1        0
```

Using an explicit wire order is important: copying a compiler C structure
directly would make the result depend on padding, bit-field rules, and CPU byte
order.

### Quantization

Real-world values such as `12.34 m` cannot always be represented exactly.
**Quantization** converts them to integers at a chosen resolution.

For depth, the scale is 100 units per metre:

```text
12.34 m * 100 = integer 1234
```

For X/Y, the scale is 10 units per metre:

```text
123.4 m * 10 = integer 1234
```

Values are rounded to the nearest representable integer. Negative,
non-finite, or zero values become zero; values over a field's capacity are
clamped to the largest representable value. Clamping prevents overflow but can
also hide an out-of-range sensor reading, so an application may want to report
that condition separately.

The battery field can technically encode above 100% because eight bits were
allocated at 0.5% resolution. Real telemetry should normally remain in the
physical 0–100% interval.

### Current generated values

Until sensors are connected, the ESP32 produces coherent changing values:

- X and Y move slowly.
- Depth and seafloor depth change within small ranges.
- Battery decreases gradually and cycles for a long-running demonstration.
- Leak and GNSS are false.
- Link quality describes the result of the previous simulated radio send.

These values are synthetic. The packing, encryption, frame, and radio model
are real code paths; the data source is the replaceable part.

## 7. Confidentiality and authenticity

Caiman uses **ChaCha20-Poly1305**, an authenticated-encryption algorithm.

- ChaCha20 encrypts the payload so someone observing the link cannot read it.
- Poly1305 produces a tag that detects accidental or malicious changes.

The algorithm receives:

```text
key                 32-byte mission encryption key
nonce               unique 12-byte value for this fragment
associated data     the visible 8-byte header
plaintext           the padded 8-byte payload
```

It returns:

```text
ciphertext           8 bytes
authentication tag  16 bytes
```

At the receiver, even a one-bit change to the header, ciphertext, or tag makes
authentication fail. Decryption must not be treated as successful in that
case.

Encryption alone would not prove that a message is genuine. Authentication
alone would not hide the telemetry. Authenticated encryption provides both.

## 8. Mission key derivation

The frame is not encrypted directly with an arbitrary password. The code uses
HKDF-SHA-256 to derive a 32-byte encryption key:

```text
input key material:  32-byte mission master key
salt:                mission identifier
context/info:        "caiman/encryption"
output:              K_enc (32 bytes)
```

HKDF is a standard key-derivation function. Its context string prevents one
derived key from being silently reused for a different purpose.

The HIL fixture deliberately uses:

```text
master key: 00 01 02 ... 1f
mission:    CAIMAN-DEMO
```

These values are public and provide reproducible tests. They offer no
production security.

## 9. The nonce and why it must never repeat

A nonce is not a password and does not need to be secret. It must be unique for
every encryption performed with the same key.

The 12-byte Caiman nonce is:

| Part | Bytes | Current encoding |
|---|---:|---|
| Mission prefix | 4 | Fixed for the mission (`a1 b2 c3 d4` in HIL) |
| Source | 2 | High byte zero, then 8-bit source address |
| Sequence | 5 | Two high zero bytes, then the 24-bit sequence |
| Fragment index | 1 | 0 through 15 |

This makes fragments of the same logical message distinct and makes messages
from different sources distinct.

Repeating a ChaCha20-Poly1305 nonce under the same key can seriously compromise
security. Therefore sequence persistence is a security feature, not just an
organizational counter.

### ESP32 crash-safe sequence reservation

The ESP32 stores sequence progress in NVS. On boot it reserves a block of 4096
sequence numbers, then transmits from that block. If power fails, unused values
in the block are intentionally skipped on the next boot. Wasting a few sequence
numbers is safe; accidentally reusing them is not.

This is an appropriate test implementation, but the final system still needs a
mission-wide policy for provisioning, exhaustion, key changes, board
replacement, corrupted storage, and multiple senders.

## 10. Replay protection

Imagine that an attacker records a valid `MISSION_STOP` message and sends the
same bytes again later. Its tag is still valid because it was once genuine.
Authentication alone cannot recognize that it is old. This is a **replay
attack**.

Caiman keeps a sliding window of 64 sequence numbers per replay context:

- A sequence newer than the current maximum advances the window.
- A sequence inside the window can be accepted if that fragment has not been
  seen.
- The same sequence and fragment a second time is rejected.
- A sequence older than the 64-entry window is rejected.
- A 16-bit fragment bitmap tracks fragment indices within each sequence.

This allows limited packet reordering while rejecting duplicates and stale
traffic.

The Raspberry HIL application creates this replay state when the receiver
process starts. Restarting the process resets its memory, so the current HIL
receiver does not preserve replay history across restarts. A production design
must decide whether receive-side persistence is required by its threat model.

## 11. Three different meanings of ACK

It is important not to mix these layers:

| Mechanism | Layer | What it proves |
|---|---|---|
| nRF24 Auto-ACK | Radio/link layer | A compatible receiver heard a radio payload and returned a short link response. |
| Caiman `ACK` type / ACK flag | Application protocol | Application-defined confirmation of a Caiman operation. Not used by current telemetry. |
| UDP behavior | Test transport | UDP itself provides no acknowledgement or delivery guarantee. |

A link Auto-ACK does **not** prove that the Caiman tag was valid or that the
application accepted the telemetry. Physical nRF24 hardware can acknowledge a
payload before the CPU has authenticated its contents. The simulator follows
that separation: the BASE sends the link response when the simulated radio
accepts the packet, then performs Caiman validation.

If an operation needs proof that the remote application processed it, an
application-level response must be designed and authenticated.

## 12. Error and rejection behavior

A frame should not reach the telemetry application when any of these checks
fails:

- frame length is not exactly 32 bytes;
- header version, field range, or fragment structure is invalid;
- source, destination, message type, or expected payload size is wrong;
- ChaCha20-Poly1305 authentication fails;
- sequence/fragment replay check fails;
- telemetry cannot be unpacked according to its schema.

Radio retry and cryptographic rejection solve different problems. Retry helps
with accidental loss. Authentication rejects modification or forgery. Replay
protection rejects valid but stale duplicates.

## 13. Source-code map

| File | Responsibility |
|---|---|
| `shared/include/caiman_protocol.h` | Public constants, types, and API. |
| `shared/src/caiman_protocol.c` | Packing, key derivation, nonce, AEAD, and replay logic. |
| `tests/test_protocol.c` | Golden vectors, tamper rejection, packing, and replay tests. |
| `esp32/main/main.c` | R1 sequence storage, generated telemetry, transmit loop, SoftAP. |
| `raspberry/main.c` | BASE UDP adapter, validation, replay check, and display. |

All protocol values on the wire must be changed deliberately and together.
Changing a C structure without defining an exact serialized representation is
not a protocol update.

## 14. Security properties and current gaps

The implementation tests useful security mechanisms, but the HIL setup is not
a deployed security architecture.

Already exercised:

- standard key derivation;
- authenticated payload encryption;
- authenticated visible headers;
- nonce construction;
- crash-conscious transmit sequence reservation;
- bounded replay detection;
- known-answer tests and tamper tests.

Still required for deployment:

- secret provisioning instead of compiled public fixture material;
- secure storage and lifecycle rules for device keys;
- a defined key-rotation protocol, not only a reserved message number;
- behavior for sequence exhaustion and storage failure;
- authorization rules for each source, destination, and command;
- receive-state persistence decisions;
- audit of denial-of-service and failure modes;
- independent protocol and cryptographic review.

## 15. A beginner's mental checklist

When adding a new Caiman message, answer these questions:

1. What does the application value mean, including units and valid range?
2. What exact bits/bytes represent it, independent of compiler structure
   padding and CPU endianness?
3. Does it fit one 8-byte fragment? If not, who reassembles fragments and how?
4. Which source and destination are authorized to use this message type?
5. Must the receiver send an application-level result?
6. How does the receiver handle duplicates, reordering, and timeout?
7. Does every encrypted fragment receive a unique nonce?
8. What is logged, and could logs expose secrets or sensitive plaintext?
9. Are golden test vectors updated for both ends?
10. Can malformed input fail safely without changing vehicle state?

The answers are part of the protocol specification, not merely implementation
details.

## 16. Reproducible golden example

The native test includes a fixed known-answer vector. This is useful when
porting the protocol to another CPU or language because both sides must produce
exactly the same bytes.

Input fixture:

```text
master key       = 00 01 02 ... 1f
mission ID       = CAIMAN-DEMO
mission prefix   = a1 b2 c3 d4
source           = 2
destination      = 0
sequence         = 7
type             = TELEMETRY
fragment         = 0 of 1
```

Derived `K_enc`:

```text
8b428062b151ee60cd7dcd3cfca7582c
b269296287eda02b730831471ab512ef
```

The golden telemetry values pack to:

```text
13 49 1d 7b 23 af 6b ec
```

The resulting complete 32-byte protected frame is:

```text
41 02 00 00 00 07 00 08
a7 5f 56 c1 06 ff df cf
d1 80 d6 95 07 6e 11 fe
45 67 a2 08 62 18 12 fa
```

These are public test bytes, not secret material. A port should reproduce this
vector and reject the frame after any authenticated byte is modified.
