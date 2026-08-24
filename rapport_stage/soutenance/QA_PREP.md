# PRe defence — question prep

**24 August 2026, 10:30–11:15 · Teams · 20 min talk + 20 min questions**
Jury: Philippe Xu (chair) · Franck Ruffier (CNRS supervisor) · Quentin Brateau (invited)

General rule: do not upgrade a claim under questioning. Where a measurement was not made, say so
and state what would be measured. The presentation is built on that distinction, so it has to hold
in the discussion as well.

---

## 1. Prepared answer: DRC on the transmitted revision

> **"Was the DRC re-run on the revision actually transmitted to manufacturing?"**

Five points, in this order. About 30 seconds.

1. **What I did.** "The DRC was run and archived during routing. The last revision I document
   in the report is `b58eda6`, which comes down to a single residual clearance at 0.1291 mm —
   below my own project rule, above the 0.10 mm capability published for 1 oz copper, and
   recorded as a documented exclusion."

2. **What I did not do.** "What I did not do is re-run it on the exact state that fed the
   production export. The export came from a later state, and the project file shows the design
   rules were not touched again after that check."

3. **What I found when I audited it.** "I audited that afterwards. The transmitted revision
   carries violations the design-stage check did not cover — including geometric contact between
   `+3V3` and `GND`. They are corrected in the repository now."

4. **What I cannot certify.** "What I cannot tell you is which Gerber set was actually uploaded.
   The download is restricted on the manufacturer's account and the export workstation was not
   kept, so I will not claim a revision I cannot verify."

5. **The consequence, which is already in the report.** "So the first action on delivery is a
   continuity check on `+3V3` / `GND` before any power is applied. I will not energise a received
   board before that measurement."

Then stop. Do not volunteer violation counts unless asked. If pressed for numbers, the
audit is written up in `rapport_stage/DRC_JLC_AUDIT.md` and you can offer to send it.

This is consistent with §5.1 and §9.2 of the report, which already state that the design rule check
belongs at the exit of the production export. The answer presents the audit that produced that
conclusion rather than treating it as a defect raised by the jury.

> ⚠️ **Consistency check before the defence.** The report's §5.1 presents `b58eda6` as
> DRC-verified, while `EVIDENCE_MAP.md` records the validated run on `b900398` (09/06) and lists
> `b58eda6` among the commits that changed the PCB afterwards. The jury only has the report, so
> this will not surface on its own — but decide which line you are holding **before** you are
> asked, and do not switch mid-answer. Answer 1 above is written to survive either reading,
> because it concedes the export-state gap up front.

---

## 2. Hardware

**"What happens if L1 saturates?"**  *(the full converter table is on slide 5)*
Not demonstrated, and I will not claim it does — the 5 V rail current was never characterised
because the board was never powered. The computed peak is 2.28 A against 2.5 A rated saturation, so 8.7 % margin, against 28.2 % on L2.
L1 is the tighter rail and the one to instrument first.
Measuring rail current and the inductance-versus-bias curve at temperature is a first bring-up
step. If the margin is genuinely thin, the fix is constrained by the land pattern: another
WE-MAPI 4020 part with a higher saturation current, or a documented reduction of the 5 V budget.

**"Why not simply choose a bigger inductor?"**
The footprint is fixed by the board, and the selection was already re-done once under exactly
that constraint — the manufacturer's review had rejected the first parts for pad geometry. Any
substitute has to match the WE-MAPI 4020 land pattern.

**"You ordered 0.8 mm but the KiCad stackup says 1.6 mm."**
Correct, and it is in the report. It does not change the 1 oz copper clearances I compared
against, but it matters for board rigidity, mounting and connector retention. It has to be
reconciled before a second order.

**"Ten blocking ERC errors in the inherited design — how did that get there?"**
I can only report what the history shows. The decoupling capacitors were drawn in series on the
rails, which blocks DC and makes power-up impossible, so the design cannot ever have been built
and tested. That is consistent with the board never having been manufactured.

---

## 3. Protocol and security

**"Why ChaCha20-Poly1305 rather than AES-GCM?"**
The STM32F765 has no AES accelerator, so AES would be a software implementation with the timing
side-channel care that implies. ChaCha20-Poly1305 is fast and constant-time in software on a
32-bit MCU, and the same C implementation runs unchanged on the ESP32 and the Raspberry Pi — which
is what made the HIL bench possible.

**"25 % application efficiency is poor."**
The figure is correct. The other 75 % is addressing,
sequencing and authentication — not waste. Two honest levers exist: truncating the Poly1305 tag
trades forgery resistance for payload, and authenticating a *group* of fragments instead of each
fragment individually would amortise the tag. I chose the full 16-byte tag with per-fragment
authentication because this is a security demonstration, not a throughput-optimised link.

**"A single group key means one captured robot compromises the fleet."**
Yes, and that is stated in the report as a limitation, not a design claim. It keeps the capture
demonstration legible. A production system needs a per-vehicle root, pairwise traffic keys, and a
short-lived routing key distributed only to authorised members.

**"How much of this actually runs on the STM32?"**
The driver moves a fixed 32-byte payload. Fragmentation, the compact codec, the AEAD and safe
persistence of the nonce counter are not ported yet. The specification is ahead of the firmware
and I say so on the slide.

---

## 4. Simulator and HIL

**"Why Wi-Fi/UDP instead of real nRF24 radios on the bench?"**
The bench targets the protocol and scheduling layer — codec, AEAD, sequence monotonicity,
bidirectional ordering — on two real processors. The nRF24 chip behaviour is modelled, so SPI and
real RF propagation are explicitly not validated. Transport sits behind a single interface in the
code, so substituting a real radio adapter is a localised change rather than a redesign. That is
the next step, not a claim I am making today.

**"How do you know the simulator is deterministic?"**
Seeded pseudo-random generation with the parameters explicitly configurable. The automated suite
asserts that two runs with identical parameters produce identical terrain, mission decisions and
packet outcomes.

**"You claim a mapped percentage, but a 25° beam at 3 m only insonifies 1.33 m."**
Correct, and the report is explicit about it. The percentage is a reconnaissance grid supported by
a track measured within 26 m — it is not a claim that every square metre was directly insonified.
A continuous chart would require interpolation and track overlap.

**"Is 3.73 hours the endurance?"**
No. It is the ideal motors-only quotient from modelling assumptions handed to the project —
12 V, 56 A·h, 15 A average. Converter losses, electronics, manoeuvre peaks, currents and safety
reserve are all uncharacterised. No mission endurance is claimed.

**"caimansim.fr does not respond."**
The instance ran on an Azure subscription opened under student credits, which have lapsed. DNS
still resolves. What the report claims is the deployment chain — containerisation, reverse proxy,
health check, domain — not continuous availability. The dashboard you saw is the same image
rebuilt from the repository.

**"Why keep the STM32/IMU bench in the report with no logs?"**
Because it did real work: it prepared the sensor-integration approach on STM32 before the board
existed. It is labelled documented and qualitative, and I claim no accuracy, sample rate or drift
figure from it. Not keeping the raw logs was a mistake, and it is on my list of expected
complementary evidence.

---

## 5. Scope and framing

**"The subject promised several robots and tank trials."**
It did, and that is in the traceability table rather than glossed over. The board was ordered on
23 June and lead times made delivery before today impossible, which put manufacturing and trials
out of reach. Rather than pause, I moved validation to what could be tested without hardware.
That changes the verifiable perimeter — it does not lower the bar, and no simulation result is
presented as a hardware result.

**"What is the research contribution, as opposed to engineering work?"**
This is an engineering PRe and I would not oversell it. What I think transfers: the separation
between the simulator's internal truth and what the surface ship can actually know, which is what
makes the supervision model honest rather than a cheat; the 32-byte authenticated frame designed
to the exact nRF24 limit; and the portable protocol plus HIL bridge, which give the team a
reference the final firmware can be checked against.

**"What would you do differently?"**
Three things, all already written up. Treat DRC as an exit gate on the production export, re-run
on the exact exported state and archived with the order. Treat a BOM as a set of geometric
commitments, not a list of values. And version everything that makes an order reproducible — a
production file that exists only on one workstation is not evidence.

---

## 6. Delivery notes for a video call

The deck runs **20:15** over 18 slides by the per-slide timings in the speaker notes.

- **Have the simulator already running** before the call opens. `cd simulator && streamlit run app.py`
  at `http://localhost:8501`, advanced just past the first rendezvous. Never launch it on camera.
- **Cap the demo at 60 seconds.** Four moves, ~15 s each: Mission view and a LAST KNOWN marker;
  advance the clock so submerged robots stop updating; Network view at a rendezvous; one AEAD
  tamper in the Security view. Then stop — do not open Packet Log or Events unless asked.
- **If the demo breaks**, 15 seconds maximum, then say *"let me show you the captures instead"*
  and press next — slide 14 is the backup, immediately behind. Do not debug in front of the jury.
- **Slides 2, 5 and 10 carry the most weight** — the fleet coverage math, the architecture with
  the converter table, and the manufacturing economics. Give them their full time. Slides 4 and
  9 (routing) are the compressible ones.
- **Slide 10 states the working method.** The three slides after it follow that order.
- **After the closing sentence, stop talking.** Let the silence sit while they unmute.


---

## 5. New in this pass: manufacturing economics (slide 10)

**"Is €81.57 a real production cost?"**
No, and I say so on the slide. It is landed, assembled cost at n = 5, JLCPCB's prototype-quantity
pricing: €18.88 for five bare boards, €368.87 for five assembled boards, €20.11 DHL Express
shipping, €407.87 total. Per-unit cost falls substantially at production volume — this figure
answers "what did this batch cost," not "what would a series run cost."

**"What exactly does the €368.87 PCBA figure cover?"**
Component procurement and SMT assembly labour for five boards, billed separately from the bare
PCB fabrication (€18.88). Both line items are on the same order, W2026062315153820.

**"Why JLCPCB specifically?"**
No claim of being the only or best option — it is the fabricator used, chosen for accessible
PCB and PCBA services in one order at prototype quantity. jlcpcb.com, Shenzhen, China.
