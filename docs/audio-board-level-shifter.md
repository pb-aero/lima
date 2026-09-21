# Level shifting the ADAU1860 on the audio board — what crosses, which parts, and what it costs

**Date:** 2026-09-21 · **Agent:** LIMA · **Status:** design note. No schematic changed.
**Trigger:** Peter ruled for a level shifter on the audio board rather than moving the CM5 GPIO bank
to 1.8 V (`docs/audio-board-io-voltage.md` §5). This is that design.

Provenance: `[fetched]` = read from the vendor PDF this session, table and page cited ·
`[measured]` = run on hardware · `[repo]` = in this repository · `[derived]` = arithmetic shown ·
`[gap]` = not established, do not assume.

---

## 1. What the ruling buys

Keeping the board at 3.3 V and translating at the codec closes the two gaps that blocked the other
route: our CM5 carrier's bank-voltage mechanism no longer has to be read, and the rest of the 40-pin
bank no longer has to be audited. `[repo]` The ICM-45686 stays at 3V3 as ruled on `kicad/imu-board/`,
which Table 3 says is in spec. **Nothing else on the board is disturbed by this decision.**

The cost is two small parts, one new rail, and the signals below.

## 2. The 1.8 V rail is needed either way — this is not avoided by shifting

**The ADAU1860 is a 1.8 V part throughout, not just on its I/O.** `[fetched]` HRM UG-2257 p.16:
*"AVDD, HPVDD, and IOVDD are nominally 1.8 V"*; p.337 annotates IOVDD **1.2 V to 1.8 V**.

So the board needs a 1.8 V LDO for the codec regardless of which topology is chosen. The level
shifter does not remove that rail — it confines the 1.8 V domain **to the codec and the translators'
A-side**, instead of spreading it across the CM5 bank and everything else on the header. That is the
real content of the ruling, and it is a sound reason to take it.

`[repo]` `3V3_MIC` stays 3.3 V and stays its own quiet rail. The mic modules and the 1.8 V codec rail
are separate supplies with separate jobs; do not fold them together to save an LDO — mic supply noise
sets ANC noise performance.

`[gap]` **The 1860's IOVDD absolute maximum is still not established.** No abs-max table in the HRM.
Design so that no 3.3 V net can ever reach an 1860 pin, including during power sequencing.

## 3. What actually crosses the boundary

`[fetched]` UG-2017 Table 8, p.12 — the ADAU1860's serial audio pins, two ports:

| Function | EVB pin | Function | EVB pin |
|---|---|---|---|
| I2S0 Data Out | P2.2 | I2S1 Data Out | P3.2 |
| I2S0 Data In | P2.4 | I2S1 Data In | P3.4 |
| I2S0 Frame Clock | P2.6 | I2S1 Frame Clock | P3.6 |
| I2S0 Bit Clock | P2.8 | I2S1 Bit Clock | P3.8 |
| MP0 | P2.10 | External MCLK Input | P3.10 |

`[repo]` The audio board carries **one** ADAU1860 with **three ADCs and one DAC** — three mics on
ADC0/1/2 (`analog-mics.kicad_sch`) and one mono DAC to `HPOUTP`/`HPOUTN` (`audio-mute.kicad_sch`).

`[measured]` RP1's I2S lanes are stereo pairs, one channel pair per wire
(`linux/adau1860-pi5/duplex/MULTILANE.md`). So three capture channels need **two** data wires, and one
playback channel needs **one**:

| Signal | Direction | Side |
|---|---|---|
| Bit clock | 1860 → host | **up** 1.8 → 3.3 |
| Frame clock | 1860 → host | **up** |
| I2S0 Data Out | 1860 → host | **up** |
| I2S1 Data Out | 1860 → host | **up** |
| I2S0 Data In | host → 1860 | **down** 3.3 → 1.8 |
| External MCLK | host → 1860 | **down**, *only if the host supplies MCLK* |

**Five lines, six if MCLK is host-supplied.** Directions assume the **1860 is clock master**, which is
what John ruled for the rig. `[gap]` **That has not been ruled for this board.** If the host is master
instead, the two clock rows flip direction — the part below handles either, but the direction straps
have to be set to match, so the ruling must land before layout.

`[gap]` Whether both serial ports' bit and frame clocks can be tied together on the 1.8 V side is not
established. If they can, the table above is complete; if each port needs its own pair, add two more
lines. **Check the register map before committing the pin count.**

**Plus the control port, which is easy to forget.** The 1860's I2C is IOVDD-referenced, so `SCL` and
`SDA` cross too. `[fetched]` UG-2017 Table 9: P5 is `SCL_SCLK`, P6 is `SDA_MISO`, P4 is `ADDR0_SS`.
On the EVB these are translated by a **PCA9517DP** — that board does not expose 1.8 V I2C to the
outside world, and neither should ours.

## 4. The parts

**Audio and clocks — `SN74AVC4T774`, two of them.** `[fetched]` TI datasheet: 4-bit dual-supply
transceiver, **individual direction control per bit** (DIR1–DIR4 separate, supplied from VCCA), VCCA
and VCCB each accept **1.1 V to 3.6 V**, and up to **500 Mbps translating 1.8 V → 3.3 V**.

Two devices give eight bits against a five- or six-line requirement — enough for the pin-count gap
above, or for both ports' clocks, without a third part. VCCA = the 1.8 V codec rail, VCCB = 3.3 V.

Per-bit direction is the reason for this part specifically: our lines are **mixed direction** — four
up, one or two down. A bank-direction part like the `SN74AVC8T245` has one `DIR` for all eight bits
and cannot express that. `[repo]` The `SN74AXC4T774` is the newer equivalent and is a fair substitute
if availability favours it.

> **Do not use TXB/TXS-class auto-direction translators.** They are for bidirectional low-drive
> signalling and misbehave on a continuously-clocked line. This applies to the bit clock above all.
> Fixed-direction parts only — the same rule as the rig (`docs/rig-logic-levels.md` §6).

**Control — a proper I2C translator, not a transceiver.** I2C is open-drain and bidirectional on one
wire, so it cannot go through the AVC4T774. Use the **PCA9517A** (the part on the EVB, so it is the
proven choice for this exact codec) or a **PCA9306** if board area matters. Either way both sides need
their own pull-ups, sized for the bus capacitance.

## 5. Timing — there is no difficulty here, with the numbers

`[derived]` At 48 kHz with a stereo lane of 2 × 32 bits, the bit clock is
48 000 × 64 = **3.072 MHz**, a period of **325.5 ns** and a half-period of **162.8 ns**.

The AVC4T774's propagation delay is single-digit nanoseconds and its rated throughput is 500 Mbps
`[fetched]`. **The translator consumes on the order of 1–2% of a half-period.** At these rates the
part is not a constraint.

Two real design rules survive that:

1. **Route bit clock, frame clock and all data through the same device type**, so their delays track.
   Mixing part families across a synchronous bus is what turns a comfortable margin into a skew bug.
2. **Playback data crosses in the opposite direction to the clock.** A→B and B→A paths do not have
   identical delays, so the setup/hold budget on the host-to-codec line is not the same as on the
   capture lines. `[derived]` With ~160 ns of half-period against single-digit-ns delays there is ample
   room — but it is the line to check first if playback ever misbehaves while capture is clean.

## 6. Bill of what this adds

| Item | Qty | Note |
|---|---|---|
| `SN74AVC4T774` (or `AXC`) | 2 | VCCA = 1.8 V, VCCB = 3.3 V; strap DIR per §3 |
| `PCA9517A` (or `PCA9306`) | 1 | I2C only; pull-ups both sides |
| 1.8 V LDO | 1 | **Needed regardless of topology** — §2 |
| Decoupling | — | Both supplies on every translator |

## 7. What is still open

- `[gap]` **Who is clock master on this board.** Sets every DIR strap. Must be ruled before layout.
- `[gap]` **Whether the two serial ports can share one bit/frame clock pair.** Sets the line count,
  and therefore whether two translators is right or generous. Checkable in the register map.
- `[gap]` **The 1860's IOVDD absolute maximum.** Still no abs-max table in the HRM.
- `[gap]` **Power sequencing between the 1.8 V and 3.3 V rails** has not been checked against the
  translator's requirements or the codec's. Read both datasheets' sequencing sections before layout.
- **Nothing here is measured.** `[measured]` Every proven capture on this project ran with the host at
  3.3 V and no translator in the path. This design has never been built.

## Sources

- **EVAL-ADAU1860 UG-2017 Rev. 0** — Table 8 (p.12, serial audio pin functions), Table 9 (p.12–14,
  connector descriptions). Restore with `scripts/fetch-datasheets.sh`; PDFs gitignored per CLAUDE.md §5.
- **ADAU186x Hardware Reference Manual UG-2257 Rev. 0** — pp. 16, 337.
- **TI SN74AVC4T774** — 4-bit dual-supply bus transceiver with configurable voltage level:
  `https://www.ti.com/lit/ds/symlink/sn74avc4t774.pdf`
- `[repo]` `kicad/aeronode-lite-audio/after/*.kicad_sch`, `linux/adau1860-pi5/duplex/MULTILANE.md`,
  `docs/audio-board-io-voltage.md`, `docs/rig-logic-levels.md`.
