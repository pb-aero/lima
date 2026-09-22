# The DVNC rig's logic levels — where a translator is needed and where the board already has one

**Date:** 2026-09-21 · **Agent:** LIMA · **Status:** analysis, verified against both EVB user guides.
**Trigger:** Peter asked whether the ADAU1372 is needed in the rig at all, then twice corrected me on
the ADAU1860 EVB's 3.3 V capability. Both pushes changed the answer. This file is the result.

Provenance: `[fetched]` = read from the vendor PDF this session, page/figure cited · `[measured]` =
run on hardware · `[repo]` = in this repository · `[gap]` = not established, do not assume.

---

## 1. The question, and the short answer

**Do we need the ADAU1372?** Yes. `[repo]` John's option (c) ruling
(`john/outbox/2026-09-18-001`) and the build spec
(`john/agents/2026-09-10_dvnc-rig-build-spec/README.md:95-104`) allocate all three of the single
1860's ADCs — ADC0/ADC1 to two differential IM73A135s on P9/P10, and **ADC2/P11 to a third
differential mic** once its ~64 dB shortfall is fixed. There is no spare analog channel on the 1860
for even one accelerometer axis, so the ADXL354's three axes plus the IM68A130A need the 1372.

**I previously claimed ADC2 was free. That was wrong** — it was read from a status summary, not from
the spec. Corrected here.

## 2. What the build spec already specifies, and the part it does not

`[repo]` The spec settles the transport in a way that is better than I had assumed:

> "one master (the 1860) drives BCLK and FSYNC for the 1372 and the CM5. Every channel is then
> sample-synchronous."

Both codecs on one RP1 block across four lanes, one shared frame clock. That is the right shape —
`[measured]` `linux/adau1860-pi5/duplex/MULTILANE.md` streams 8 channels with exact byte counts and a
negative control showing unused lanes stay static. **What the spec does not cost is the voltage that
shared clock runs at.** §3–§5 are that gap.

## 3. The ADAU1860 EVB: control port 3.3 V, serial audio 1.8 V

This is the distinction that took three passes to get right.

### The control port genuinely is 3.3 V — the board shifts it for you

`[fetched]` UG-2017 Figure 14 (Schematics, Page 8) draws `3.3V` and `IOVDD` as two separate rails
into a full set of translators:

| Block | Part | Note |
|---|---|---|
| I2C-BUS LEVEL SHIFT | **PCA9517DP** | bidirectional I2C level-translating buffer |
| SPI LEVEL SHIFT | **U2–U5 FXLP34P5X** | sheet labels them "UNI-DIRECTIONAL TRANSLATOR" |
| UART LEVEL SHIFT | **U6, U7 FXLP34P5X** | `UART_CTRL_*` and `UART_COMM_*` |

`S1` (`MSS420004`) selects I2C vs SPI; `S14` straps ADDR0/ADDR1.

> **Consequence, and it removes work: I2C from a 3.3 V Pi/CM5 to the 1860 needs no external level
> shifting.** The EVB already does it.

### The serial audio port does not

`[fetched]` UG-2017 p.12, on headers **P2** (Serial Audio Port 0) and **P3** (Serial Audio Port 1):

> "The IOVDD logic level is 1.8 V"

There are no translators on that path. P2/P3 carry data in/out, frame clock, bit clock, and — on
P3 pin 10 — the external MCLK input.

### And IOVDD cannot be moved to 3.3 V

`[fetched]` UG-2017 Figure 12 (Power Supplies), read off the drawing:

| Ref | Part / function | Result |
|---|---|---|
| **U10** | `ADP1715ARMZ-1.8-R7` — **fixed** 1.8 V | net `IOVDD_LDO` → P48 pin 1 |
| **P48** | IOVDD selector | pin 1 = `IOVDD_LDO`, pin 2 = `IOVDD`, pin 3 = `EXT_IOVDD` |
| **P43** | `EXT_IOVDD` header | where an external IOVDD is injected |
| **JP3** | IOVDD jumper | ties IOVDD to the AVDD/HPVDD rail — sheet note: "AVDD, HPVDD AND IOVDD COMBINED TOGETHER" |
| **U9** | `ADP1713AUJZ-1.8-R7` | that AVDD/HPVDD rail, so JP3 also gives 1.8 V |
| **U19** | `ADP1715ARMZ-3.3-R7` | net `3.3V` → FT4232 (p.9) + the translators' high side. **No path to IOVDD anywhere on the sheet** |

Contrast the jumpers that *are* voltage selectors: `JP1` short/open = DVDD 0.9 / 1.1 V, `JP2`
short/open = HPVDD_L 1.3 / 1.5 V. **IOVDD has no equivalent, because U10 is a fixed-output part.**

The silicon agrees: `[fetched]` HRM UG-2257 p.16 "AVDD, HPVDD, and IOVDD are nominally 1.8 V", and
the p.337 system block diagram annotates IOVDD **1.2 V to 1.8 V**.

`[gap]` **The absolute-maximum rating for IOVDD is not established** — the HRM carries no
absolute-maximum table and the abridged datasheet gives only the operating range. Do not conclude
3.3 V into P43 merely degrades; it is out of spec and the damage threshold is unknown.

## 4. The ADAU1372 EVB: 3.3 V by default, and movable

`[fetched]` UG-807 p.13, verbatim:

| Ref | Functional name | Description |
|---|---|---|
| **J8** | IOVDD 1372_IOVDD | "supplies power to the IOVDD supply of the ADAU1372 from the power supply section" |
| **J10** | IOVDD VDD | "connects IOVDD on the ADAU1372 to **VDD (3.3 V board supply)**" |
| **J17** | VDD AVDD | "connects AVDD on the ADAU1372 to VDD (3.3 V board supply)" |

**J10 is a jumper that puts IOVDD at 3.3 V.** J8 and J10 are separate feeds, and AVDD is on its own
jumper (J17), so **IOVDD is separable from the analog supply.**

`[fetched]` ADAU1372 datasheet p.8 Table 4: AVDD and IOVDD both **1.71 V to 3.63 V** — so 1.8 V
IOVDD with 3.3 V AVDD is in spec and keeps analog headroom for the ADXL354 and the IM68A130A.

`[gap]` **What rail J8 feeds is not established.** The power-supply schematic (UG-807 Figure 38)
lists an `ADP1713AUJZ-1.5` on that board, and 1.5 V would be *below* the 1372's 1.71 V minimum.
**Read Figure 38 before moving either jumper.**

## 5. The number that decides the shared clock

`[fetched]` ADAU1372 datasheet p.8 Table 3 — input voltage high, min:

| 1372 IOVDD | **V_IH min** |
|---|---|
| 3.3 V | **2.0 V** |
| 1.8 V | 1.1 V |

The 1860's audio pins swing to IOVDD = 1.8 V, and V_OH is below that rail. **As the boards ship —
1860 master at 1.8 V into a 1372 at 3.3 V IOVDD — 1.8 V does not meet a 2.0 V threshold.** The
spec's clock plan does not work without one of the fixes below.

The reverse direction is worse: a 1372 master at 3.3 V into the 1860's 1.8 V-referenced inputs is an
**overvoltage**, the same class of error as the 2026-09-18 DMIC catch. So the spec chose the safe
failure direction — it will simply not clock rather than damage anything.

## 6. Two topologies

**A — common 1.8 V codec domain, translate at the host.** Move the 1372's IOVDD to 1.8 V (§4), share
BCLK/FSYNC directly between codecs, translate BCLK + FSYNC + 4 data lines to the CM5. Cleanest, and
it is the flight end-state. **Cost: it un-proves the one link that works** — `[measured]` the 1372 at
3.3 V driving the Pi.

**B — keep both proven links, translate between the codecs.** 1372 stays at 3.3 V to the host.
Translate the 1860's 1.8 V BCLK/FSYNC up for the 1372 and the CM5, its two `SDATAO` lines up for the
CM5, and the playback line down to the 1860. Preserves the measured configuration; adds translator
skew into the clock path.

**Recommendation: B for December, A as the end-state.** Either way the I2C needs nothing (§3).

### RULED 2026-09-22 by Peter — `TXS0108E` in push-pull for the bench, `SN74LVC8T245` for the product

**And I am retracting the blanket ban I wrote here.** My earlier text said *"do not use an
auto-direction translator on the clocks… not TXB/TXS"* without qualification. **That was too broad and
the speed half of it was simply wrong.**

`[fetched]` TXS0108E datasheet (SCES650), title page: the part is *"8-Bit Bi-Directional,
Level-Shifting, Voltage Translator **for Open-Drain and Push-Pull Applications**"*, rated
**110 Mbps push-pull** (1.2 Mbps open-drain), with **1.4–3.6 V on A and 1.65–5.5 V on B, VCCA ≤ VCCB**.
For our 1.8 V ↔ 3.3 V case that is in range with the ordering satisfied, and **110 Mbps is 36× our
3.072 MHz bit clock.** Speed is not the objection and I should not have implied it was.

What TI actually says, `[fetched]` p.19, is a preference rather than a prohibition: the device is *"an
excellent choice… where an **open-drain** driver is connected"* and *"**appropriate** for applications
where a push-pull driver is connected… **but the TXB0104 device… might be a better option** for such
push-pull applications."* Its stated design target is MMC/SD-class interfaces that *"start out in a
low-speed open-drain mode and then switch to a higher speed push-pull mode."*

**So the bench choice is sound.** Three real cautions, all from the datasheet's own text, and all
about the bench's flying leads rather than the part:

1. **The high level is held by a resistor, not a buffer.** `[fetched]` p.18: smart pull-ups are
   **4 kΩ when driving high** (40 kΩ when driving low), giving *"a modest DC-current sourcing
   capability of hundreds of micro-amperes."* An edge is driven hard by a **~30 ns one-shot**; after
   that the line is merely held.
2. **Keep the leads SHORT — this is the one that bites on a bench.** `[fetched]` p.18: *"With very
   heavy capacitive loads, the one-shot can time-out before the signal is driven fully to the positive
   rail,"* and TI warns of *"one-shot retriggering, bus contention, output signal oscillations, or
   other adverse system-level affects."* Long unshielded jumpers between eval boards are exactly the
   capacitance this is describing.
3. `[gap]` **The datasheet's rates assume the driving device's output impedance is under 50 Ω**
   (`[fetched]` p.18). **The ADAU1860's serial-port output impedance is not established.** If it is
   high, `tPHL` and the achievable rate both degrade from the published figures.

**One structural note, not an objection:** auto-direction is solving a problem we do not have — every
signal here is fixed-direction. On the bench that is an acceptable trade for a part on hand; in the
product it is why a strapped-direction part is the better answer, which is what Peter ruled.

## 7. "Sample-synchronous" needs a shared MCLK, not just a shared frame clock

The 1372 runs its converters from its own 12.288 MHz crystal. With only BCLK/FSYNC shared, its
**output ASRC stays in the capture path** — `[measured]` 2026-09-17, the DAPM chain reads
`Decimator0 Mux → Output ASRC Supply → Output ASRC0 Mux → Serial Output 0`.

That collides with the 2026-09-02 scar: **an ASRC on accelerometer data fabricates samples and
reports no error.** `[repo]` [[rp1-i2s-clock-direction]].

Sharing MCLK is a resistor rework on the 1372: `[fetched]` UG-807 — `R2` is open from the factory and
must be fitted to bring MCLK out on J4; `R3` must be removed to drive MCLK in. The 1860 side is a
header, not a rework — `[fetched]` UG-2017 p.12, external MCLK is **P3 pin 10**, selected by P8 with
P27, and P25 disables the on-board oscillator.

`[gap]` Whether the 1372's output ASRC can instead be muxed out of the path is not established;
it is checkable in the register map.

## 8. What Monday does not need to care about

Monday's bring-up is the **1372 alone**, as clock master at 3.3 V into the Pi — `[measured]` the
proven configuration. None of §5–§7 applies until the 1860 joins for eight channels. Fit the GPIO22
jumper and run `linux/adau1372-evb/FOUR-CHANNEL-1372.md`.

`[gap]` **Nothing has been measured with 1.8 V clocks into the Pi or CM5.** Every proven capture on
this rig had the 1372 driving the host at 3.3 V.

## Sources

- EVAL-ADAU1860 UG-2017 Rev. 0 — pp. 9, 12, 13–14; Figure 12 (Schematics p.6, Power Supplies),
  Figure 14 (Schematics p.8, Control Ports Level Shift). Restore with
  `scripts/fetch-datasheets.sh`; PDFs are gitignored per CLAUDE.md §5.
- ADAU186x Hardware Reference Manual UG-2257 Rev. 0 — pp. 16, 337.
- EVAL-ADAU1372Z UG-807 Rev. 0 — pp. 6, 8, 13.
- ADAU1372 datasheet — p. 8 Tables 3 and 4.
- `[repo]` `john/agents/2026-09-10_dvnc-rig-build-spec/README.md`,
  `john/outbox/2026-09-18-001`, `linux/adau1860-pi5/duplex/MULTILANE.md`,
  `linux/adau1372-evb/FOUR-CHANNEL-1372.md`, `docs/two-adau1860-channel-allocation.md`.


---

## 8 · Propagation delay and phase lag with the translator inserted — measured against two separate budgets

**Date added:** 2026-09-22 · Peter asked what the level shifter costs in propagation delay and phase
lag. The short answer is that it buys into **two unrelated budgets**, and it is negligible in the one
people worry about and material only in the one nobody asks about.

### 8.1 The framing that matters: the translator is not in the ANC loop

**The anti-noise control loop does not cross the level shifter.** `[repo]` (JULIETT, 2026-09-10, and
John): the cup's fast loop is **analog in → ADC → FastDSP → DAC → analog out, entirely local to the
codec**, with the 48 kHz link bridged by the part's own ASRCs. The translator sits on the **path to
the CM5**, which records and monitors. **So "phase lag" in the ANC sense does not arise from it at
all** — there is no mechanism by which it can contribute.

And treated as plain transport delay to the host, a translator moves **already-sampled data**. A
sample that arrives 7 ns late is still the same sample, captured at the codec's own ADC at the codec's
own clock. The only thing lateness can do is **miss a setup window** — which is §8.3, a timing-
integrity question, not a latency one.

### 8.2 The numbers · `[fetched]` datasheet maxima at VCCA = 1.8 V, VCCB = 3.3 V

| Part / direction | `tPHL` | `tPLH` | worst | % of a 162.8 ns half-period | % of a 20.833 µs sample |
|---|---|---|---|---|---|
| **TXS0108E push-pull** A→B | 5.7 ns | 6.5 ns | **6.5 ns** | 3.99% | 0.031% |
| **TXS0108E push-pull** B→A | 7.4 ns | 5.8 ns | **7.4 ns** | 4.55% | 0.036% |
| **SN74LVC8T245** A→B | — | — | **7.4 ns** | 4.55% | 0.036% |
| **SN74LVC8T245** B→A | — | — | **23.4 ns** | 14.38% | 0.112% |
| ⚠ **TXS0108E open-drain** A→B | 9.3 ns | **466 ns** | **466 ns** | **286%** | 2.24% |

Bit clock is **3.072 MHz** (8 channels over 4 stereo lanes, 2 × 32 bit each, 48 kHz) — a **325.5 ns**
period and a **162.8 ns** half-period.

> **The surprise, stated because it is the opposite of what one would assume:** in this configuration
> **the TXS0108E is the more symmetric part** — 6.5 / 7.4 ns against the LVC8T245's 7.4 / 23.4 ns. LVC
> drives slowly at 1.8 V, so its B→A leg is three times the TXS's. **The reason to prefer LVC in the
> product is therefore not speed** — it is that a strapped direction has no one-shot, no
> direction-sensing and no capacitance-dependent failure mode. Worth being clear about, so nobody
> defends the product choice on a performance argument that does not hold.

### 8.3 Where the nanoseconds actually go — the serial-bus timing budget

This is the budget the translator really spends, and it is about setup and hold, not phase.

- **Clocks and capture data travel the same way** (codec → CM5), so what sets setup/hold is
  **channel-to-channel skew**, bounded by `max − min` within a direction: **6.4 ns for LVC A→B, ≈4% of
  a half-period.** Ample.
- **The binding path is playback round trip** — BCLK up, the CM5 clocks data out, data comes back
  down — measured against the codec's own *local* BCLK, which was never translated:

| | round trip | % of a half-period |
|---|---|---|
| **TXS0108E** | 6.5 + 7.4 = **13.9 ns** | **8.5%** |
| **SN74LVC8T245** | 7.4 + 23.4 = **30.8 ns** | **18.9%** |

Both comfortable. **This, not the clock, is the path to watch**, and it is the number that would go
marginal if the framing ever changed (a 12.288 MHz bit clock has an 81 ns half-period, where 30.8 ns
is 38%).

### 8.4 Phase lag, if you want it in degrees anyway — `φ = 360 · f · τ`

`[derived]` from the maxima above, against the codec's own ADC-to-DAC group delay for scale
(`[fetched]` UG-2257 Table 8 gives 12.9 µs at 192 kHz; the 48 kHz figure is JULIETT's extrapolation
and is `[derived]`, not characterised by ADI):

| Contributor | 40.01 Hz | 100 Hz | 500 Hz | 1 kHz |
|---|---|---|---|---|
| TXS0108E round trip (13.9 ns) | 0.0002° | 0.0005° | 0.0025° | **0.005°** |
| LVC8T245 round trip (30.8 ns) | 0.0004° | 0.0011° | 0.0055° | **0.011°** |
| ADAU1860 group delay @192 kHz `[fetched]` | 0.19° | 0.46° | 2.32° | **4.64°** |
| ADAU1860 group delay @48 kHz `[derived]` | 0.65° | 1.62° | 8.10° | **16.2°** |

> **At 1 kHz the translator contributes five to eleven thousandths of a degree while the codec
> contributes 4.6° to 16.2°.** The codec's own converter chain is **419× to 3237×** larger. **The
> translator is not a phase-lag consideration — it is four orders of magnitude below the term that
> sets the answer.** If phase budget is tight, the lever is the codec's internal rate (192 kHz buys
> 12.9 µs against ~45 µs at 48 kHz), never the translator.

### 8.5 The one number that is not negligible, and it is a cliff rather than a slope

⚠ **`tPLH` on the TXS0108E collapses from 6.5 ns to 466 ns if it operates open-drain rather than
push-pull** — a factor of **72**, and **286% of a half-period**, so the bit clock cannot pass at all.

**This is why Peter's "push-pull configuration" qualifier is load-bearing and not a detail.** The
distinction is not a degradation; it is working versus not working. The part decides for itself which
mode it is in, based on the driving device's edge and the one-shot firing correctly — which is exactly
what §"keep the leads short" above is protecting, and `[gap]` why the ADAU1860's unestablished
serial-port output impedance (TI assumes < 50 Ω) is the open risk on the bench.

**Diagnostic, stated before the run:** if a captured clock shows edges arriving hundreds of ns late,
or the link fails outright while every register reads correct, **suspect open-drain operation and lead
capacitance first** — not the codec, and not the framing.
