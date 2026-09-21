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

### 2.1 The absolute maximum — found, and it is the hard number this whole design turns on

**I previously recorded this as an open gap across three documents. It was not a gap; I had the file
and did not read the table.** Corrected here and in `docs/audio-board-io-voltage.md`.

`[fetched]` ADAU1860 datasheet Rev. 0, **Table 10, p.16, Absolute Maximum Ratings**:

| Parameter | Rating |
|---|---|
| **Power Supply (AVDD, IOVDD, HPVDD, HPVDD_L)** | **−0.3 V to +1.98 V** |
| Digital Supply (DVDD) | −0.3 V to +1.21 V |
| **Digital Input Voltage (Signal Pins)** | **−0.3 V to IOVDD + 0.3 V** |
| Analog Input Voltage (Signal Pins) | −0.3 V to AVDD + 0.3 V |
| Input Current (except supply pins) | ±20 mA |

> **With IOVDD at 1.8 V, the absolute maximum on any digital pin is 2.1 V. A 3.3 V drive is 1.2 V
> over it.** The datasheet's wording is stricter than the usual formula — *"Stresses **at or above**
> those listed under Absolute Maximum Ratings may cause permanent damage"* — so 3.3 V on an 1860
> digital pin **destroys the part**. It does not degrade it, and it does not merely fail to clock.

This turns the level shifter from a signal-integrity choice into a **protection requirement**, and it
retires the hedged language in my earlier notes. Three consequences:

1. **No 3.3 V net may reach an 1860 pin under any condition**, including power sequencing and the
   window where one rail is up and the other is not. §7 keeps sequencing as an open item for exactly
   this reason.
2. **The translators must be the only path** between the 3.3 V domain and the codec. No test point, no
   DNP resistor, no "temporary" jumper that bridges the two sides.
3. `[repo]` **The 17 Sep duplex test sheet is a part-killer as written** — it sends CM5 playback
   straight into the 1860's `SDATAI`. JULIETT already flagged it (`2026-09-21-002`) and asked that
   Chris be told before he plugs anything in. **This is the number that says why: 3.3 V into a pin
   rated 2.1 V maximum.**

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

**Five lines. Peter ruled the 1860 clock master on this board (2026-09-21)**, as John ruled for the
rig, which settles the table above and two things that follow from it:

- **MCLK does not cross.** A master 1860 clocks itself from its crystal — `[fetched]` Table 13, ball
  B6 `XTALO` / B7 `XTALI/MCLKIN`. There is no second codec on this board needing a shared MCLK, so the
  external-MCLK row drops. **Five lines, not six.**
- **Every DIR strap is now fixed and can be tied to a rail.** Direction never changes at runtime, so
  no GPIO is spent on it and no boot-order question arises. Four bits strapped for A→B (up), one for
  B→A (down).

**The pin count does not depend on the two ports sharing a clock**, which is what I thought needed the
register map. It does not: `[measured]` RP1 has **one** bit clock and **one** frame clock for the whole
four-lane block (`linux/adau1860-pi5/duplex/MULTILANE.md`), so only one pair can cross whatever the
codec does internally. Wire `BCLK_0` and `FSYNC_0`; leave port 1's clock pins local.

> **But the question does not disappear — it changes into a worse one. See §3.1.**

### 3.1 Keeping `SDATAO_0` and `SDATAO_1` sample-aligned — answered

Three capture channels need two data lanes, so the mic array arrives on **two different serial ports**
of the same codec, and only port 0's clock reaches the host. If port 1 ran its own free generator, the
two halves of the array could sit at a fixed sample offset from each other.

This matters more than the pin count. `[repo]` The three mics are an ANC array: their **relative**
phase is the signal. A fixed sample offset between the mic on port 1 and the two on port 0 would not
show up as a dropout or an error bit — it would show up as an array that quietly steers wrong, and
`docs/analog-mics` already records that the IM73A135's +12° at 75 Hz alone caps cancellation at
−13.6 dB. This is the same failure class as the 2026-09-02 ASRC scar: **the data keeps flowing and
nothing reports a fault.**

**CLOSED — and the fix is two traces, not a register bet.** `[fetched]` UG-2257 Rev. 0, Tables 277
and 296 (`SPT0_CTRL2` @ 0x4000C0E1, `SPT1_CTRL2` @ 0x4000C0F4) and Table 278 (`SPT0_CTRL3`
@ 0x4000C0E2):

| Field | Setting | Meaning |
|---|---|---|
| `SPTx_BCLK_SRC` [2:0] | **000** | **BCLK is from external source** |
| | 001 / 010 / 011 / 100 | generate BCLK at 3.072 / 6.144 / 12.288 / 24.576 MHz |
| `SPTx_LRCLK_SRC` [3:0] | **0000** | **LRCLK is from external** |
| | 0001 / 0010 / … | generate LRCLK at 48 / 96 / … kHz |

**Both ports carry an identical, independent pair of source selects, and both can take their clocks
externally.** So the design need not hope that two on-chip generators stay in step:

> **Set SPT0 to generate (`BCLK_SRC` = 001, `LRCLK_SRC` = 0001) and SPT1 to external
> (`BCLK_SRC` = 000, `LRCLK_SRC` = 0000), then wire `BCLK_1` ← `BCLK_0` and `FSYNC_1` ← `FSYNC_0`
> on the board.** Port 1 is then clocked by the very same edges as port 0, and alignment is by
> construction rather than by configuration.

Those two traces sit **on the 1.8 V side, before the translators** — no translator bits, no extra
part. They are the cheapest thing in this document and they delete a silent failure mode. **Draw
them.**

The cross-correlation measurement is still worth running once hardware exists — one tone into two
mics on different ports, checked for zero sample offset. The register map states design intent; only
a capture proves the silicon. But it is now a confirmation rather than a gate.

### 3.1.1 Why three mics cannot ride one lane — it is a mismatch, not a host limit

**Correction to an earlier version of this note, which said "RP1 cannot receive TDM — the limit is
the host, not the codec."** That was too coarse in both halves. Peter asked the sharper question:
could the Pi take several slots on one data line with an ordinary frame clock, without it being TDM?
In general that is a real mode and many parts do it. **Here it is closed, by the codec.**

`[fetched]` UG-2257 Table 26, p.43 — frame-clock mode is **welded to** `SPTx_SAI_MODE`:

| Format | Frame Clock Mode (`SPTx_SAI_MODE`) |
|---|---|
| I2S / Left Justified / Right Justified | **0 — 50% duty cycle** |
| TDM | **1 — single bit clock wide pulse** |

And the text on the same page is explicit about what 50%-duty buys you: *"In stereo modes, **both
edges of frame clock determine where data is placed**, and the left channel maps to the output for
Channel 0, while the right channel maps to the output for Channel 1. In TDM mode only, the rising
edge of frame clock determines where data is placed."*

> **So the ADAU1860 offers exactly two options: a 50%-duty frame clock carrying two channels, or a
> multi-slot frame (to TDM16) carrying a single-BCLK-wide pulse. There is no 50%-duty multi-slot mode
> on this part.** One serial port is two channels, full stop — which is why three mics need two ports.

The host side then fails against the only multi-channel option the codec has. `[measured]`
`RESULTS-2026-09-07`: with `SPT0_CTRL1` bit 0 `SAI_MODE` = TDM, `aplay` returns `EIO` with
`hw_ptr=0` and the DMA channel fails to stop; the same run at `SAI_MODE` = STEREO passes cleanly.
Setting `dai-tdm-slot-num` on the Linux side does not change what the DesignWare block locks to.

**Stated precisely, so the record is right:**

- `[measured]` RP1 will not lock to **the ADAU1860's** narrow TDM pulse.
- `[gap]` Whether RP1 could receive TDM from *some other* source with a different sync width is **not
  established** — and it does not matter here, because the 1860 cannot produce anything else.
- `[fetched]` The **codec** is the binding constraint for a 50%-duty multi-slot link, not the host.

**Worth remembering if either end changes.** A codec offering 50%-duty multi-slot would put all three
mics on one lane and halve the lines crossing the translator. This one does not.

### 3.1.2 The slot map — four slots across two lanes, 50% duty, no TDM

Peter's framing, and it is the right mental model: **slot 0 → port 0 left, slot 1 → port 0 right,
slot 2 → port 1 left, slot 3 → port 1 right.** Four independently-routable slots on two wires with an
ordinary 50%-duty frame clock. `[fetched]` The registers are named exactly this way — *Serial Port 0
Output Routing Slot 0 **(Left)***, *Slot 1 **(Right)*** — and each port carries 16 slot registers, of
which **only slots 0 and 1 are used in stereo mode**; slots 2–15 exist only in TDM.

`[fetched]` UG-2257 Table 279, `SPT0_ROUTE0` @ 0x4000C0E3. Each slot register is a 6-bit source
select, `SPTx_OUT_ROUTEy` [5:0], which can take **any** internal channel:

| Value | Source |
|---|---|
| 0–15 | FastDSP Channel 0–15 |
| 16–… | Tensilica DSP Channel 0–… |
| 32–35 | Output ASRC Channel 0–3 |
| **36 / 37 / 38** | **ADC Channel 0 / 1 / 2** |
| **63** | **No Output. Slot not used.** |

So the three mics land like this, with `SPT1` clock-slaved to `SPT0` per §3.1:

| Slot | Register | Address | Value | Carries |
|---|---|---|---|---|
| 0 | `SPT0_ROUTE0` (left) | 0x4000C0E3 | **36** | ADC0 — mic 1 |
| 1 | `SPT0_ROUTE1` (right) | 0x4000C0E4 | **37** | ADC1 — mic 2 |
| 2 | `SPT1_ROUTE0` (left) | 0x4000C0F6 | **38** | ADC2 — mic 3 |
| 3 | `SPT1_ROUTE1` (right) | — | **63** | unused, explicitly disabled |

Four slots, three used, one spare — and the spare is free capacity on a wire we are already paying to
translate. **`[gap]` Confirm `SPT1_ROUTE1`'s address against the register map before writing it**; the
0x4000C0F6 above is inferred from the `SPT1_ROUTE0` position and has not been read off the table.

> **TRAP, and it sits four values away from the ones we want.** Entries **32–35 are Output ASRC
> Channels**. `[measured]` The 2026-09-02 scar: an ASRC in an accelerometer or reference path
> **fabricates samples and reports no error**. Route the ADCs **direct** — 36/37/38 — and never
> through 32–35. A typo of four in this register is silent and it is the exact failure this project
> has already been bitten by once.

### 3.2 Every serial pin is multiplexed — the trap that already bit us once

`[fetched]` Table 13: `BCLK_0/MP3` (ball B2), `BCLK_1/MP7` (D5), `SDATAI_1/MP10` (D4) — **every serial
audio pin doubles as a multipurpose I/O.**

`[measured]` This exact family of mux cost us the Monday bring-up on the other codec: mainline's
ADAU1372 driver writes `MODE_MP6 = 0x12` (CLKOUT) at probe, which the datasheet says disables
`ADC_SDATA1` — two of four channels with no data path, found on 2026-09-18. **A pin that is strapped
correctly in the schematic can still be taken away by a driver write at probe time.** Confirm the MP
assignments in the driver, not only in the netlist.

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

`[fetched]` ADAU1860 datasheet Table 9 gives the codec's own numbers, and they are the larger term:

| Parameter | Limit | Note |
|---|---|---|
| `fBCLK` | 0.512–**24.576 MHz** | 3.072 MHz is comfortably inside |
| `tSOD` — `SDATAO_x` delay from `BCLK_x` falling | **0–16 ns** at IOVDD ≥ 1.62 V | **0–32 ns** at IOVDD 1.1 V min |
| `tSS` / `tSH` — `SDATAI_x` setup / hold to `BCLK_x` rising | 3 ns / 10 ns | the host must meet these |
| `tTS` — `BCLK_x` falling to `FSYNC_x` skew (master) | 6 ns | |

**Our 1.8 V IOVDD puts us in the 16 ns bracket, not the 32 ns one** — a further argument for 1.8 V
over the 1.1 V end of the codec's range.

`[derived]` Worst case on a capture line: `tSOD` 16 ns + translator delay of a few ns ≈ **20 ns against
a 162.8 ns half-period, about 12%.** Ample. The AVC4T774's 500 Mbps rating `[fetched]` is two orders of
magnitude beyond what this bus asks of it. **The translator is not the constraint; the codec's own
output delay is, and it is still comfortable.**

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

- ~~Who is clock master on this board.~~ **Ruled by Peter, 2026-09-21: the 1860.** DIR straps fixed,
  MCLK does not cross, five lines.
- ~~Whether `SDATAO_0` and `SDATAO_1` are sample-aligned.~~ **Closed — §3.1.** Slave SPT1's clocks to
  SPT0's externally; two traces on the 1.8 V side.
- ~~The 1860's IOVDD absolute maximum.~~ **Closed — §2.1. It is 1.98 V**, and digital pins are
  IOVDD + 0.3 V. This was never a real gap: I had the datasheet and failed to read Table 10.
- ~~UG-2257 is not reachable.~~ **Closed.** analog.com refuses curl and WebFetch but serves the file
  to a browser as a download. It is now at `linux/adau1860-pi5/ADAU186x_HRM_UG-2257.pdf`, gitignored,
  with its checksum verified by `scripts/fetch-datasheets.sh` (that entry checks a hand-placed file
  rather than fetching — the comment there carries the URL and the method).
- `[gap]` **Power sequencing between the 1.8 V and 3.3 V rails** has not been checked against the
  translator's requirements or the codec's. Read both datasheets' sequencing sections before layout.
- **Nothing here is measured.** `[measured]` Every proven capture on this project ran with the host at
  3.3 V and no translator in the path. This design has never been built.

## Sources

- **EVAL-ADAU1860 UG-2017 Rev. 0** — Table 8 (p.12, serial audio pin functions), Table 9 (p.12–14,
  connector descriptions). Restore with `scripts/fetch-datasheets.sh`; PDFs gitignored per CLAUDE.md §5.
- **ADAU1860 datasheet Rev. 0**, 30 pp — **Table 10 (p.16, Absolute Maximum Ratings)**, Table 9
  (serial port timing), Table 13 (pin functions). Pinned in `scripts/fetch-datasheets.sh`.
- **ADAU186x Hardware Reference Manual UG-2257 Rev. 0**, 337 pp — Table 276 (`SPT0_CTRL1`),
  Table 277 (`SPT0_CTRL2`), Table 278 (`SPT0_CTRL3`), Table 296 (`SPT1_CTRL2`); pp. 189, 212.
  Hand-downloaded from analog.com via a browser; checksum verified by `scripts/fetch-datasheets.sh`.
- **TI SN74AVC4T774** — 4-bit dual-supply bus transceiver with configurable voltage level:
  `https://www.ti.com/lit/ds/symlink/sn74avc4t774.pdf`
- `[repo]` `kicad/aeronode-lite-audio/after/*.kicad_sch`, `linux/adau1860-pi5/duplex/MULTILANE.md`,
  `docs/audio-board-io-voltage.md`, `docs/rig-logic-levels.md`.
