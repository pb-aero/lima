# The audio board's I/O voltage — the 1.8 V domain is free, and the ICM-45686 does not block it

**Date:** 2026-09-21 · **Agent:** LIMA · **Status:** analysis. No schematic changed.
**Trigger:** Peter asked whether the audio board needs a level shifter. The short answer is that as
currently drawn it would, but the shifter is the wrong fix — on our own board the rails are ours to
choose, and the part I expected to block that choice does not.

Provenance: `[fetched]` = read from the vendor PDF this session, table and page cited ·
`[measured]` = run on hardware · `[repo]` = in this repository · `[derived]` = arithmetic shown ·
`[gap]` = not established, do not assume.

---

## 1. The answer

**No level shifter is needed, if the CM5's GPIO bank runs at 1.8 V.** Nothing on the board forces
3.3 V, and the two parts that share that bank are both happy at 1.8 V — one because it has no choice,
the other because 1.8 V is its *nominal* operating point.

This is the rig's problem (`docs/rig-logic-levels.md`) arriving on a board where we still control the
answer. On the eval rig the 1860's IOVDD is pinned at 1.8 V by a fixed LDO and the CM5 sits on someone
else's carrier, so translators or a solder rework are the only moves. **Here the net has not been
drawn yet.** Choosing the rail now costs nothing; choosing it after layout costs a translator on every
clock and data line.

## 2. What is actually on the board today

`[repo]` `kicad/aeronode-lite-audio/after/`:

| Fact | Consequence |
|---|---|
| **No ADAU1860 symbol is placed anywhere.** Placed parts are R, C, connectors, relays, transformers, FETs, diodes | The codec's digital side is undrawn — this decision is still free |
| **No 1.8 V net exists in the project.** Rails are `3V3`, `3V3_MIC`, `3V3_CM5`, `3V3_NPU` | A 1.8 V domain has to be added deliberately; nothing gets it by default |
| `aeronode-audio-interface.kicad_sch` carries `I2S1_SDI0..3` / `I2S1_SDO0..3` | The RP1 four-lane link to the CM5 — these are the nets in question |

So the board as conceived is an ADAU1860 on a 3.3 V board talking I2S to a 3.3 V CM5. That is the
same fault as the rig, and it would need translators on eight data lines plus BCLK and FSYNC.

## 3. The 1860's 1.8 V limit is silicon, not an eval-board artifact

`[fetched]` ADAU186x HRM UG-2257 p.16: *"AVDD, HPVDD, and IOVDD are nominally 1.8 V"*; the p.337
system block diagram annotates IOVDD **1.2 V to 1.8 V**.

That follows the chip onto any board we build. The EVB's fixed `ADP1715ARMZ-1.8` is an eval-board
artifact and the CM5 carrier is someone else's choice — **the 1.8 V IOVDD ceiling is neither.** It is
the reason this is a rail decision and not a wiring decision.

**CORRECTION, 2026-09-21 (later): this is established, and I was wrong to call it a gap.** The HRM
indeed has no absolute-maximum table `[measured]` — 337 pages, zero hits for the phrase — but **the
datasheet does**, and I had that file when I wrote the line above.

`[fetched]` ADAU1860 datasheet Rev. 0, **Table 10, p.16**: Power Supply (AVDD, **IOVDD**, HPVDD,
HPVDD_L) **−0.3 V to +1.98 V**; Digital Input Voltage (Signal Pins) **−0.3 V to IOVDD + 0.3 V**.

> **At IOVDD = 1.8 V the limit on any digital pin is 2.1 V. 3.3 V is 1.2 V beyond it, and the
> datasheet says stresses *at or above* the ratings may cause permanent damage. It destroys the part.**

See `docs/audio-board-level-shifter.md` §2.1.

## 4. The ICM-45686 — the part I expected to block the bank move, and it does not

This was the open question. **It is closed, and the answer is better than "tolerable."**

`[fetched]` ICM-45686 datasheet, document number **DS-000489 Rev. 1.1**, §3.3.1 Table 3, D.C.
Electrical Characteristics, **p.20** — quoted verbatim:

| PARAMETER | MIN | TYP | MAX | UNITS |
|---|---|---|---|---|
| VDD | 1.71 | 1.8 | 3.6 | V |
| VDDIO | 1.08\* | **1.8** | 3.6 | V |

\* *"Important Note: When using I3C<sup>SM</sup> interface the minimum VDDIO value is 1.1V."* Both rows
are marked note 1, *"Guaranteed by design."*

**1.8 V is the datasheet's own typical, and the whole table is characterised at it** — every
electrical spec in §3.3 is headed *"VDD = 1.8 V, VDDIO = 1.8V, TA=25°C, unless otherwise noted."*
Running this part at 1.8 V is the condition its numbers were written for.

Two details that make 1.8 V the *better* choice, not merely an acceptable one:

- `[fetched]` §3.5 SPI Timing, p.32: the table splits at **VDDIO < 1.71 V** versus **VDDIO ≥ 1.71 V**.
  At 1.8 V we are in the fast column — `fSPC` SCLK max **24 MHz**, against 20 MHz below 1.71 V.
  **1.8 V costs no SPI bandwidth.** 1.2 V would.
- `[fetched]` §3.7 Table 9, p.26, latch-up: *"JEDEC Class II (2) for VDDIO ≤ 1.98V, JEDEC Class I (1)
  for VDDIO > 1.98V, ±100 mA."* **At 1.8 V the part sits in the higher latch-up class.** At 3.3 V it
  does not.

`[fetched]` §3.7 Table 9, p.26 — absolute maximums, both supplies: **−0.5 V to +4 V**.

> **So the existing ruling is not wrong, and nothing has to be unwound.** `[repo]` Peter ruled 3V3 for
> both VDD and VDDIO on `kicad/imu-board/` (2026-08-21). 3.3 V is inside the operating range and well
> inside the absolute maximum. **Both rails are legal.** 1.8 V is simply the better one here, and it is
> the one that deletes the level shifter.

`[fetched]` TDK's own eval board agrees on the shape: AN-000484 Rev. 1.1 p.3 — VDDIO selectable
**1.2 / 1.8 / 3.0 V**, VDD **1.8 / 3.0 V**. *There is no 3.3 V option on it at all.* That is a jumper
list rather than a limit — Table 3 is the limit — but it says plainly which rail TDK expects.

## 5. What this means for the board

**Put the CM5 GPIO bank, the 1860's IOVDD and the ICM-45686's VDDIO in one 1.8 V domain.** Then:

- No translators on `I2S1_SDI0..3` / `I2S1_SDO0..3`, BCLK or FSYNC — ten lines saved.
- No translator propagation skew in the bit-clock path, which is the failure mode that worried me most
  in topology B on the rig.
- The ICM-45686 keeps 24 MHz SPI and gains a latch-up class.
- `[repo]` The **analog** side is untouched. `3V3_MIC` stays 3.3 V and stays its own quiet rail — the
  1860's AVDD/HPVDD and the mic modules are a separate question from IOVDD, and the mic rail's noise
  performance is what sets ANC performance. Do not fold them together to save an LDO.

`[gap]` **Everything else on that bank has to be audited before this is ruled.** I have checked the two
parts I know sit on it. A 1.8 V bank is a board-wide decision and anything else strapped to those pins
inherits it.

`[gap]` **How the CM5's bank voltage is set on our carrier is not established.** On the official CM5 IO
board it is a Vref resistor (R5→R4) `[repo]`, which is where JULIETT's `2026-09-21-004` lands for the
*rig*. Our carrier is `kicad/aerosense-cm5/` and I have not read how it does it. **Read that before
promising the bank can move.**

## 6. The honest part — what I got wrong and what I could not get

- **I expected the ICM-45686 to be the blocker** and it is the opposite: the part is happier at 1.8 V
  than at 3.3 V. The search result that first suggested "VDDIO 1.2/1.8/3.0 V" came from the *eval
  board* guide, and reading it as a device limit would have produced a wrong and confident answer about
  3.0 V being a ceiling. Table 3 says 3.6 V. **Eval-board jumper options are not device limits** — the
  same mistake, in the other direction, as reading the 1860's fixed LDO as a silicon property.
- **TDK's own PDF could not be fetched.** `invensense.tdk.com` and the Mouser mirror both return HTML
  to curl and to WebFetch — a bot wall of the same class as the 2026-09-06 analog.com block. The
  document came from an LCSC CDN path. **The checksum is what makes a mirror safe**, and it is pinned
  in `scripts/fetch-datasheets.sh`, verified this session with a present-and-matching control and a
  corrupted-file control that re-fetched.
- **The document number does not match what TDK advertises.** Every index calls this datasheet
  **DS-000577**; the PDF's own page footers read **DS-000489 Rev. 1.1** throughout. I have cited what
  the document says about itself. `[gap]` Whether DS-000577 is a newer revision with different numbers
  is unresolved — if this decision gets expensive, get the PDF from TDK directly and re-check Table 3.
- **Nothing here is measured.** No 1.8 V bank has been run on this hardware; `docs/rig-logic-levels.md`
  records the same gap for the rig. Every proven capture we have had the host at 3.3 V.

## Sources

- **ICM-45686 datasheet, DS-000489 Rev. 1.1**, 199 pp — §3.3.1 Table 3 (p.20), §3.5 SPI timing (p.32),
  §3.7 Table 9 (p.26). Restore with `scripts/fetch-datasheets.sh`; PDFs are gitignored per CLAUDE.md §5.
- **EV_ICM-45686 Evaluation Board guide AN-000484 Rev. 1.1** — p.3 (VDD/VDDIO jumper options).
- **ADAU186x Hardware Reference Manual UG-2257 Rev. 0** — pp. 16, 337.
- `[repo]` `kicad/aeronode-lite-audio/after/*.kicad_sch`, `kicad/imu-board/`, `kicad/aerosense-cm5/`,
  `docs/rig-logic-levels.md`, `docs/h1-audio-board-codec-selection.md`.
