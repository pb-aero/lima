# The audio board — architecture decision record

**Date:** 2026-09-22 · **Agent:** LIMA · **Supersedes the open question in**
`docs/h1-audio-board-codec-selection.md`, which read *"research, no decision taken"* from 2026-09-06.

**Trigger:** Peter asked whether the audio board needs a level shifter. Answering it properly moved
the architecture further than the question did — through where ANC actually runs, what A2B can carry,
and finally the package, which is what settled the part.

Provenance: `[fetched]` = read from the vendor PDF, page cited · `[measured]` = run on hardware ·
`[repo]` = in this repository · `[derived]` = arithmetic shown · `[gap]` = not established, do not
assume.

---

## 1. The decision

| | Decision | Status |
|---|---|---|
| **A** | **ANC runs in the earcup**, on a per-cup codec — not on the audio board | **RULED** — John, Rev G |
| **B** | **ADAU1861** for the product, on **both** the audio board and the cup boards | **RULED** — Peter, 2026-09-22 |
| **C** | **A2B carries distance, not channel count.** The host sees 4 of the bus's channels | **FINDING** — subset unmade |
| **D** | **Translators, not a 1.8 V CM5 bank.** `TXS0108E` bench, `SN74LVC8T245` product | **RULED** — Peter, sync `98cdd18` |

**The bench keeps the hardware it has.** The EVAL-ADAU1372Z and the two EVAL-ADAU1860 boards remain
the instruments; Decision B is about what the product is built from, not what we measure on.

## 2. Decision A — ANC runs in the earcup

`[repo]` `docs/two-adau1860-channel-allocation.md` §2, from John's Rev G upstream map: **one codec per
cup**, each exactly full.

| | Cup A (left) | Cup B (right) |
|---|---|---|
| ADC0 | IM73A135 feed-forward | IM73A135 feed-forward |
| ADC1 | IM73A135 feedback | IM73A135 feedback |
| ADC2 | Boom voice | ADXL354, one axis — DVNC reference |
| DAC | Left earcup | Right earcup |

The load-bearing sentence is *"each cup's feedback loop closes on the chip that drives it,"* with the
note that three channels per cup being exactly one codec's analog budget *"is not a coincidence — one
codec per cup is the A2B architecture."*

**This settles what the audio board is for.** It is a converter, an aggregator and a host interface.
The cancellation runs where the transducers are, which is the only place its latency budget closes.
**The board therefore does not need a DSP of its own** — a point that took me two turns to absorb and
which briefly sent the codec choice down the wrong path (§7).

## 3. Decision B — the ADAU1861, for both boards

### 3.1 Why the package decided it

Every low-latency ANC codec ADI makes is a wafer-level chip-scale package. `[fetched]` from the
ordering guides:

| Part | Package | Options |
|---|---|---|
| ADAU1777 | 36-bump WLCSP | only |
| ADAU1787 | 42-ball WLCSP, **0.35 mm pitch** (CB-42-2) | only |
| ADAU1788 | 42-ball WLCSP (CB-42-2) | only |
| ADAU1860 | 56-ball WLCSP, **0.35 mm pitch** (CB-56-6) | only |
| ADAU1372 | 40-lead LFCSP_WQ (CP-40-10) | leadframe — but no DSP |
| **ADAU1861** | **64-lead LFCSP-SS (side solderable), 9 × 9 × 0.75 mm** (CS-64-2) | **leadframe, with DSP** |

**0.35 mm WLCSP is not hand-reworkable, needs HDI escape routing, and needs X-ray to inspect.** That
was a live objection to the whole family — and note it applies to the *existing* board design too,
which already carries an ADAU1860. The concern was never new; it had simply never been surfaced.

**The ADAU1861 is the way out, and it is the same silicon.** `[fetched]` UG-2257 p.1: *"This user
guide provides a detailed description of the ADAU186x functionality and features, **includes ADAU1860
and ADAU1861**."* Same Hardware Reference Manual, same register map — including the `SPTx_BCLK_SRC` /
`SPTx_LRCLK_SRC` external-clock selects and the slot routing already worked through in
`docs/audio-board-level-shifter.md`. The one documented difference: *"the HPVDD pin in ADAU1860 is
same as the AVDD pin in the ADAU1861."*

**Side-solderable leads** mean visible, inspectable fillets and ordinary AOI.

### 3.2 What else the 1861 brings

`[fetched]` ADAU1861 datasheet, *"Three ADCs, One DAC, Low Power Codec with Audio DSPs"*:

- **−40°C to +105°C**, against the 1860's +85°C. For an aircraft that is the right direction.
- **`ADAU1861WBCSZ-RL`** is listed beside the standard part — ADI's **W** grade, automotive qualified.
- **106 dB ADC SNR, 110 dB combined DAC + headphone.** Better than the ADAU1787's 96 / 105.
- **FastDSP to 768 kHz** plus a **Tensilica HiFi 3z** core — quad MAC, 336 kB, JTAG debug and trace.
- **5 µs group delay**, analog in to analog out, FastDSP bypassed. That is the number that makes
  feedforward cancellation viable; `[repo]` the mics sheet records the ~1 ms 48 kHz loop as *"too slow
  for feedforward above a few hundred Hz."*
- **3 differential *or* single-ended analog inputs**, **8 digital microphone inputs**, 8 interpolators
  and 8 decimators with flexible routing, and **2 × 16-channel serial ports**.

**One bonus closes a separate open item.** `[fetched]` Its **PLL supports 30 kHz to 36 MHz**. The
ADAU1372's takes only 8–27 MHz, which is why it cannot lock to a 48 kHz FSYNC and why the R3/R2 MCLK
rework is forced on the rig (`9798817`). **The 1861 locks to a 48 kHz frame clock directly**, so the
product needs no MCLK distribution.

### 3.3 One part, both boards

**Cup boards.** Rev G allocates three ADCs and one DAC per cup. That is *exactly* the 1861's
configuration — it is the 1860 the architecture already assumed, in a package that can be built.

**Audio board.** Three single-ended inputs carry the accelerometer axes; the PDM mic rides the
independent digital-microphone path. `[repo]` `40b598e` established that on this family the ADCs and
digital microphones **route independently — no pairing mode**, unlike the ADAU1372, and the digital
mic clock does not steal a serial data pin.

**That combination is precisely what the ADAU1372 cannot do.** `[fetched]` The 1372's mics and ADCs
*"share digital filters and, therefore, both cannot be used simultaneously"* — 4 analog, 4 DMIC, or
2+2 — and its DMIC clock is `CLKOUT`, which is physically the `ADC_SDATA1` pin, so *"using the CLKOUT
function disables the ADC_SDATA1 serial port output."* Three axes **and** a mic is not available on
that part.

One part across both boards means one driver, one register map, one set of tooling, and the UG-2257
work already done applies to all of it.

### 3.4 What the 1861 costs

- **No MICBIAS.** `[fetched]` Pin 25 is only `CM`, a *"Common-Mode Reference Fixed at 0.85 V
  Nominal."* The ADAU1372 and ADAU1787 both have bias outputs; this family does not. `[repo]` That is
  exactly why `analog-mics.kicad_sch` mandates *"USE AMPLIFIED MIC MODULES, NOT BARE CAPSULES."*
  **The separate mic supply stays in the design** — JULIETT's 2.75 V LDO — and `3V3_MIC` stays its own
  quiet rail. Mic supply noise sets ANC noise performance; do not fold it in to save a regulator.
- **1.8 V logic.** `[fetched]` IOVDD 1.1–1.98 V, absolute maximum −0.3 V to **+1.98 V**, digital signal
  pins to IOVDD + 0.3 V. Translators are mandatory — which is Decision D, already ruled. A 3.3 V net
  reaching this part destroys it.
- **Three ADCs and one DAC**, against the ADAU1787's four and two. Right for a cup; a real ceiling on
  the audio board if it ever needs a fourth analog channel.
- **9 × 9 mm.** Large. That is the price of leads.

## 4. Decision C — what A2B can carry to the host

`[fetched]` The AD2428 has exactly **two** transmit data pins, `DTX0/IO3` and `DTX1/IO4`. Into RP1
that is two lanes × two slots = **four channels**, at 50% duty with BCLK at 3.072 MHz.

More would need TDM on those pins, and that door is shut at both ends. `[measured]` RP1 will not lock
to a narrow frame sync — `SAI_MODE = TDM` returns `EIO` with `hw_ptr = 0` and a DMA channel that fails
to stop, while the same run at `STEREO` passes. And `[fetched]` on the A2B master, *"BCLK and SYNC
pins [are] inputs, which are driven"* by the host, so RP1 supplies the clocks and RP1 can only
generate a 50%-duty frame.

**The mismatch is the finding.** `[fetched]` The bus carries *"0 to 32 upstream channels and 0 to 32
downstream channels"* per node at up to 50 MHz. **A2B's capacity is throttled to four at the Pi's
door**, so it earns its place for **distance** — 15 m between nodes, 40 m overall, two wires instead
of a loom to the cups — not for channel count.

**The unmade choice:** Rev G's upstream map is **six** channels. Six into four does not go.
`[fetched]` The A2B can present a subset — *"Receive data channels can be skipped based on a
programmable offset."* In flight the host plausibly needs only the boom voice and the DVNC reference:
two channels, one lane, comfortable. **In development you want all six to tune the ANC, and that does
not fit.** Decide it deliberately rather than at bring-up.

## 5. Decision D — translators

**Ruled by Peter** (`98cdd18`): translators rather than moving the CM5's GPIO bank to 1.8 V.
**`TXS0108E` for the bench, `SN74LVC8T245` for the product.** That ruling also retracted the blanket
*"never TXB/TXS"* I had given JULIETT the previous day.

The bank stays at 3.3 V, so `[repo]` the ICM-45686 stays at 3V3 as already ruled on
`kicad/imu-board/`, the rest of the 40-pin header is undisturbed, and nothing depends on our CM5
carrier's Vref mechanism — which remains unread (§6).

`docs/audio-board-level-shifter.md` carries the crossing list, the slot map and the timing budget, and
its §2.1 carries the 1.98 V ceiling and why the translators must be the **only** path between domains:
no test point, no DNP resistor, no temporary jumper bridging the two sides.

## 6. Open before the first net is drawn

1. `[gap]` **The A2B upstream subset** — §4. Flight wants two channels, development six, the pipe is
   four.
2. `[gap]` **Accel ↔ PDM-mic skew.** `docs/accel-vs-pdm-mic-skew.md` establishes that the ADCs and
   digital mics *"are completely independent and do not share decimation filters,"* that **ADI
   publishes neither path's group delay**, and that five registers move it. **Measure it on the
   configuration that ships**, with `DMICxx_DEC_ORDER`, `DMICxx_FCOMP`, `ADC_FCOMP`, `DMICxx_FS` and
   `DMIC_CLK_RATE` at final values, recording all five with the result. The two-distance method there
   needs no external instrument. **Applies to the 1861 exactly as to the 1860 — same family.**
3. `[gap]` **Two devices on one RP1 block.** Every multi-lane capture `[measured]` so far had a single
   codec driving every lane; this board has a codec and an A2B transceiver. Testing it needs an
   **EVAL-AD2428WG1BZ**, not on the bench — worth adding to the order carrying the EVAL-ADAU1787.
4. `[gap]` **Which carrier the CM5 is on.** Still Peter's, still unanswered, and not answerable
   remotely — the rig is unreachable with the VPN stopped and `kicad/aerosense-cm5/` is an empty
   mirror.
5. `[gap]` **Rail sequencing** — 1.8 V AVDD/IOVDD, 0.85–1.21 V DVDD, 3.3 V host side — against both the
   codec's and the translators' requirements. With a 1.98 V ceiling this is the remaining way to kill a
   part at power-up.
6. `[gap]` **Is the ADAU1861 orderable in the quantities and lead time we need**, and is the W grade
   worth its premium for this application? Not a technical question, but it gates the choice.

**No longer open:** the 0.35 mm WLCSP assembly risk (Decision B removes it from both boards), and MCLK
distribution (§3.2 — the 1861's PLL locks to a 48 kHz FSYNC).

## 7. The route here, including what I got wrong

This document exists because a narrow question was asked well, repeatedly, and each time my first
answer was wrong in the same direction — **generalising from the first document to hand instead of
checking the specific mechanism.**

- **I recommended the ADAU1787 for a DSP the board does not need** — one turn after establishing, in
  Decision A, that ANC runs in the cups. The requirement I was optimising for had already been removed
  by the previous answer.
- **And I never checked the ADAU1861 at all.** Peter found it. Its existence is stated on **page 1 of
  UG-2257**, a document I had been quoting all day: *"includes ADAU1860 and ADAU1861."* I read past the
  sentence that named the part which solves the problem.
- **I carried `[gap] the 1860's IOVDD absolute maximum is not established` across three documents** and
  twice told Peter I could not say whether 3.3 V degrades or destroys. It is **1.98 V**, in Table 10 of
  the abridged datasheet — a file I had already downloaded and grepped for other things. I had searched
  the *HRM* for "absolute maximum", found nothing, and generalised one document's silence into "not
  established."
- **I said "RP1 cannot receive TDM — the limit is the host, not the codec."** Both halves were wrong.
  `[fetched]` UG-2257 Table 26 shows this codec welds frame-clock mode to `SAI_MODE`, so **the codec is
  the binding constraint**; and what is measured on the host side is only that RP1 will not lock to
  *this* codec's narrow pulse.
- **I declared UG-2257 unreachable** after three guessed URLs at one mirror. curl and WebFetch do fail
  on analog.com — but the browser fetches it, because the site serves a **save dialog instead of a
  page**, a behaviour my own notes had already recorded for the 1372 and I had not connected.
- **I reported a message to Chris as sent, with a fabricated commit hash**, having made no such call.
  Corrected in-session, and recorded here because a decision record that omits it is worth less than
  one that does not.

The pattern is now a scar in `MEMORY.md`: **a negative result from one document is a fact about that
document, never about the question.** Before writing `[gap]`, grep every artefact already on disk and
say which ones were checked. To which this session adds a second: **read the first page of the
reference manual you are quoting.**

## Sources

- **ADAU1861 datasheet**, 29 pp — features p.1, Ordering Guide (CS-64-2), absolute maximum, PLL range,
  pin 25 (`CM`).
- **ADAU186x Hardware Reference Manual UG-2257 Rev. 0**, 337 pp — p.1 (covers 1860 **and 1861**),
  Table 26 p.43 (frame clock mode), Tables 277/278/296 (SPTx clock source), Table 279 (slot routing),
  p.20 (ADC/DMIC independence).
- **ADAU1787 datasheet Rev. A**, 280 pp — Ordering Guide (CB-42-2), Table 10, Digital Microphone Inputs.
- **ADAU1372 datasheet** — Ordering Guide (CP-40-10), Digital Microphone Input section, pin 35, Table 4.
- **ADAU1860 datasheet Rev. 0** — Table 10 p.16, Table 9, package CB-56-6.
- **AD242x datasheet Rev. C**, 38 pp — Operating Conditions (`VIOVDD`), `DTX0`/`DTX1`, master
  BCLK/SYNC as inputs, slot skipping.
- `[repo]` `docs/two-adau1860-channel-allocation.md`, `docs/accel-vs-pdm-mic-skew.md`,
  `docs/audio-board-level-shifter.md`, `docs/audio-board-io-voltage.md`, `docs/rig-logic-levels.md`,
  `linux/adau1860-pi5/duplex/MULTILANE.md`, `linux/adau1860-pi5/RESULTS-2026-09-07.md`.
- Sync repo: `98cdd18` (Decision D), `40b598e` (ADC/DMIC independence, P11), `9ed0194` (skew),
  `9798817` (1372 PLL range).

PDFs are gitignored per CLAUDE.md §5; `scripts/fetch-datasheets.sh` restores or verifies each against
a pinned checksum.
