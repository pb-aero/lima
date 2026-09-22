# Two ADAU1860s for stereo — channel allocation, and why the split goes by EAR not by function

**Date:** 2026-09-14 · **Agent:** LIMA · **Status:** analysis + recommendation. `[gap]` not ruled.

Peter, 2026-09-14: *"We will need 2 adau1860 evb for stereo. My thinking is we use one for dvnc using
the analog accelerometer ADXL354 and analog mic IM73A135 and the other for the feedback feedforward
mics IM73A135 as well as the electret boom mic."*

Provenance: `[fetched]` = read from the vendor PDF this session, spec quoted · `[derived]` =
arithmetic shown · `[repo]` = in this repository · `[gap]` = not established.

---

> ## ⚠ SCOPE CORRECTION — 2026-09-14, same session
>
> Peter: *"This is not for the final implementation design this is to prove the technologies for
> 1 December using evaluation boards."*
>
> **I wrote §1–§2 below against the product architecture. For a technology proof they are the wrong
> objection.** For a demonstrator, separating DVNC and ANC onto two chips is *good* engineering —
> independent bring-up, independent A/B, and one technology failing does not block the other.
> **Peter's split is right for December.** §6 is the demonstrator plan and supersedes §1–§2's
> recommendation for that purpose.
>
> §1–§2 are kept, not deleted: the product still has to be built, and the per-cup allocation is still
> where it lands. **§3–§4 (the parts and the EVB) apply unchanged and are the part of this document
> that matters most for December.**

---

**Two ADAU1860s is right, and it is the first thing that makes per-ear ANC possible at all** —
`[repo]` §22 of `docs/h1-headset-mute-relay.md` recorded that the single-DAC part could never do it.
The part count is correct. **The proposed split of work across the two parts is not**, and §1 is why.

---

## 1. The split by function does not produce stereo

Each ADAU1860 has `[fetched]` **three ADCs and one DAC**. Under the proposed allocation:

| | EVB 1 (DVNC) | EVB 2 (ANC + voice) |
|---|---|---|
| ADCs | ADXL354 + one IM73A135 | FF mic + FB mic + boom electret — **full** |
| DAC | DVNC anti-tone, **mono** | ANC anti-noise, **mono** |

Four problems, in order of how hard they are to fix:

1. **There is still only one FF/FB pair, so only one earcup is being cancelled.** A feedback mic
   senses the residual *at one ear*. Copying that cup's anti-noise into the other cup applies a
   correction derived from the wrong acoustic path — at the frequencies where ANC earns its keep the
   two cups are acoustically independent, so the second ear gets **added noise, not cancellation**.
   Two chips split this way still buy mono ANC.
2. **Two DACs, two functions, one pair of ears — so they must be summed in analog anyway.** The
   summing amplifier from `docs/anc-dvnc-summing-amp.md` would now carry **three** inputs per ear
   (comm, ANC, DVNC) instead of two, and its headroom budget (§5 there) gets a third coherent term.
3. **The feedback loop crosses a chip boundary.** FB mic on EVB 2, DVNC on EVB 1, both landing in the
   same earcup: the DVNC output is now an uncontrolled disturbance inside the ANC loop's error path,
   arriving with an inter-chip transport delay. `[repo]` §19 puts the whole feedforward budget at
   **FastDSP, 768 kHz** precisely because ~1 ms at 48 kHz is already too slow. An inter-chip hop
   inside that loop is not affordable.
4. **It contradicts the bit map that already exists.** See §2.

---

## 2. John's Rev G upstream map already answers this — the split is per cup

`[repo]` `docs/johns-bitmap.html`, upstream, 6 × 24-bit:

| Slot | | | Slot | | |
|---|---|---|---|---|---|
| 0 | Cup A — FF | feed-forward mic | 3 | Cup B — FF | feed-forward mic |
| 1 | Cup A — FB | feedback / error mic | 4 | Cup B — FB | feedback / error mic |
| 2 | Cup A — voice | boom mic uplink | 5 | **Cup B — spare** | **unallocated** |

**Three channels per cup. That is exactly one ADAU1860's analog budget per cup, and it is not a
coincidence** — one codec per cup is the A2B architecture. Two EVBs on the bench is the correct
prototype of two cup codecs, provided they are clocked together (§5).

**And Cup B's slot 5 is spare because the pilot has one mouth.** That is where the DVNC reference
belongs. The allocation writes itself:

| | **Chip A — Cup A (left)** | **Chip B — Cup B (right)** |
|---|---|---|
| ADC0 | IM73A135 feed-forward, **differential** | IM73A135 feed-forward, **differential** |
| ADC1 | IM73A135 feedback, **differential** | IM73A135 feedback, **differential** |
| ADC2 | **Boom voice** (see §4) | **ADXL354, one axis, single-ended — DVNC reference** |
| DAC | Left earcup | Right earcup |

Both chips exactly full, nothing spare, and each cup's feedback loop closes on the chip that drives
it. DVNC parameters computed on Chip B reach Chip A the way Rev G already specifies — `[repo]`
byte-packed parameter frames on **downstream slot 2 at ~10% occupancy** — or over the second serial
port chip-to-chip. `[gap]` which, not decided.

**The accelerometer costs nothing that was being used.** That is the whole point of putting it there.

---

## 3. The parts, checked

### ADXL354 — good choice, and for a better reason than bandwidth

`[fetched]` ADXL354/ADXL355 Rev. A: three **single-ended** outputs `XOUT`/`YOUT`/`ZOUT` referred to
`V1P8ANA/2`; **400 mV/g** typ at ±2 g (200 at ±4 g, 100 at ±8 g); **20 µg/√Hz**; internal low-pass
**fixed at 1500 Hz, 50% response**; supply **2.25–3.6 V**, **150 µA**.

- **One axis, not three.** Three outputs would consume all three ADCs and a harmonic *reference*
  needs frequency and phase, not a vector. `[gap]` Which axis is a bench question — pick the one
  with the best harmonic SNR at blade-pass in the real airframe.
- `[derived]` **Headroom: 0.693 V pk** (the ADAU1860's `[fetched]` 0.49 V rms single-ended full
  scale) ÷ 400 mV/g = **1.73 g peak at 0 dB PGA**. Using the PGA's 24 dB drops that to **0.11 g**.
  `[gap]` airframe vibration at the headset mount is unmeasured, so the range strap and the PGA
  setting are both undecided.
- `[derived]` Noise: 20 µg/√Hz × 400 mV/g = **8 nV/√Hz** referred to the codec input. That is far
  below anything the ADAU1860 will contribute, so **the accelerometer will not be the noise floor —
  the codec will.** `[gap]` ADAU1860 input-referred noise is not in the abridged datasheet (the same
  no-register-map gap `linux/adau1860-pi5/` has carried since 2026-09-02).
- **AC-couple it.** `[repo]` `docs/h1-audio-board-codec-selection.md` §3: every one of these inputs
  is AC-coupled, and the ADXL354 sits at 0.9 V DC. Set the corner with the cap and pick the
  ADAU1860's 8 Hz digital HPF — the DVNC band starts around 50 Hz, so unlike the vibration work in
  `dsp/vibration-reference/` (dominant content at **8.30 Hz**, `[measured]`) the HPF is helpful here
  rather than destructive. **Same part, opposite filter decision, because the job is different.**

**The real argument for the analog ADXL354 over the digital ADXL355 is clock-domain coherence, not
bandwidth.** A tonal canceller lives or dies on the phase relationship between its reference and its
anti-tone. Into the codec's own ADC, reference and output share one sample clock and that
relationship is fixed by construction. Read over SPI by the CM5, it is not — you would be re-locking
phase in software across two asynchronous domains, forever. `[derived]`

### IM73A135 — right part, and one number that must not be ignored

`[fetched]` Infineon IM73A135V01, Rev. 1.00: **differential output**; sensitivity **−38 dBV**
(1 kHz, 94 dB SPL) = **12.6 mV/Pa**; **SNR 73 dB(A)**; **AOP 135 dB SPL** (THD 10%); noise floor
**−111 dBV(A)**; **low-frequency cutoff 20 Hz** (−3 dB re 1 kHz); **170 µA at 2.75 V**;
4 × 3 × 1.2 mm.

- **Differential output into differential inputs** — this is the part of the plan that is simply
  correct. It buys the ADAU1860's **0.98 V rms** differential full scale instead of 0.49 single-ended,
  and rejects cable-borne noise. `[repo]` §19's pseudo-differential capacitor front end was a
  workaround for single-ended modules; with the IM73A135 it becomes a real differential connection.
- `[derived]` **The codec clips 3 dB before the microphone does.** 0.98 V rms ÷ 12.6 mV/Pa = 77.8 Pa
  = **131.8 dB SPL** at 0 dB PGA, against the mic's 135 dB SPL AOP. **So the FF channel's PGA stays
  at 0 dB.** At a 100 dB SPL cockpit the mic delivers 25.2 mV rms = **−31.8 dBFS** — ample.
- **20 Hz cutoff is flat through the whole DVNC band.** No repeat of the §19 transformer scare.
- **`[fetched]` Phase response: +12° at 75 Hz** (2° at 1 kHz, −2° at 3 kHz). Group delay 52 µs at
  250 Hz, 2 µs at 1 kHz. `[derived]` **An uncorrected 12° phase error caps cancellation at
  2·sin(6°) = 0.209, i.e. −13.6 dB**, and it lands exactly on prop blade-pass. It is specified,
  repeatable and the sensitivity tolerance is ±1 dB, so it is **calibratable in the DSP — but it must
  be calibrated, not assumed away.** This is the single most important number on the microphone
  datasheet for this application and it is not the one on the front page.

### The electret boom mic — right for a reason that is acoustic, not electrical

`[repo]` §19 ruled against bare electret capsules on this part: the ADAU1860 has **no MICBIAS pin**
and only **0–24 dB** of PGA. That ruling stands electrically — an electret here needs an external
quiet rail, a bias resistor and a coupling cap that you design yourself.

**But the reason to want one anyway is directivity.** The IM73A135 is **omnidirectional**
`[fetched]`. An omni boom mic in a 100 dB SPL cockpit picks up the cockpit, not the pilot; aviation
boom mics are noise-cancelling pressure-gradient capsules for exactly this reason. So the instinct is
right and the ruling in §19 does not contradict it — §19 was about level, this is about pattern.

**There is a third option that costs no analog channel at all.** `[fetched]` UG-2017: the EVB
exposes **eight digital microphone (DMIC) channels** alongside the three analog ADCs. Voice uplink
has no latency constraint — unlike the FF/FB loop it is not inside a control loop — so it can be
**two PDM MEMS mics beamformed in the DSP**, which buys directivity in software and hands ADC2 back
to the analog budget on Chip A. `[gap]` **Confirm the 8 DMIC channels and 3 ADCs can be routed
simultaneously** — the abridged ADAU1860 datasheet still carries no register map, which is a
long-standing gap in this repo, not a new one.

> **GAP CLOSED 2026-09-22. They can, and the mechanism is a per-channel routing field rather than a
> mode.** Peter's read — *"the ADAU1860 looks like it will work with the PDM mic and the analog
> accelerometer"* — is correct.
>
> `[fetched]` UG-2257 Rev. 0 pp.145–146, Tables 206 ff: there are **eight Fast-to-Slow Decimator
> channels, each with its own input routing register** (`FDEC_ROUTE0`…`FDEC_ROUTE7`, `0x4000C084`
> upward). Each carries a **6-bit source field** selecting from one flat list:
>
> | Code | Source |
> |---|---|
> | **36, 37, 38** | **ADC Channel 0, 1, 2** — the three analog inputs |
> | **39–42** | **DMIC Channel 0–3** |
> | **47–50** | **DMIC Channel 4–7** |
> | 0–3, 34–35, 43 | FastDSP, input ASRC, EQ0 |
>
> **Every decimator channel picks any one source independently.** There is **no pairing constraint
> and no analog/digital mode** — which is worth stating explicitly because **the ADAU1372 does have
> one**: on that part `[repo]` the digital mic inputs share filters with the ADCs and switch in pairs
> (4 analog, 4 digital, or 2 + 2). **The 1860 does not work that way.** I had been carrying the 1372's
> limitation as an unexamined worry about the 1860.
>
> Cross-check that raises confidence: the same numbering (ADC 36–38, DMIC 39–42 and 55–58) was already
> recorded in this lane for `SPT0_ROUTEn` from the vendor SDK's bitfield header. It is a **shared
> source enumeration** reused by `SPT0_ROUTEn`, `DAC_ROUTEn` and `FDEC_ROUTEn` alike, which is why two
> independently-derived reads agree.

### What the closed gap actually buys — and the one thing it breaks

**Three analog ADCs is exactly an accelerometer's X, Y and Z, with the microphones moved to PDM.** One
ADAU1860 can therefore carry a complete sensor payload — 3 analog axes plus a digital reference mic —
**which is the whole job the ADAU1372 was brought in to do.** That removes, in one stroke, the
1.8 V/3.3 V inter-codec threshold failure, the `R2`/`R3` MCLK rework, the `S1` board-voltage switch,
the 1372's output ASRC sitting in the accelerometer path, and a second codec to clock.

> ⚠ **But it moves the P11 defect onto the critical path, and that is a promotion, not a footnote.**
> `[repo]` ADC2 is the channel behind `P11`, which reads **~64 dB quieter than ADC0 with both jacks
> empty** and is still unexplained. Three axes need ADC0, ADC1 **and ADC2**. So the shortfall stops
> costing us *a third microphone* and starts **blocking the Z axis.** Until it is explained, one 1860
> carries **two** usable analog channels, and a three-axis accelerometer does not fit.
>
> **HYPOTHESIS, 2026-09-22 — it is probably an open jumper, not a defective ADC.** `[repo]`
> `linux/adau1860-pi5/MIC_INPUT_P11.md` traces the path from the schematic:
>
> ```
> P11 tip   ── TP7 ─ P13 ─ R34 (0R) ─ C26 (22uF) ─ P15 ──► AINP2
> P11 ring  ── TP6 ──────  R33 (0R) ─ C25 (22uF) ───────► AINN2
> ```
>
> **`P13` and `P15` sit in series with the tip path, and `[repo]` they are ADC2's single-ended /
> differential selection jumper pair** (ADC0 is `P104`/`P105`, ADC1 is `P12`/`P14`). The ring path
> passes through neither — an asymmetry that only makes sense if those two are the configuration
> point. With them open, `AINP2` is simply **not connected to the jack.**
>
> **The measurement fits that better than it fits a dead converter.** `[measured]` Unplugged, P11 read
> **−89.1 dBFS against empty P9 at −25.0 and P10 at −28.7** — it is *quieter*, not louder or stuck. An
> open input has no antenna and picks up no ambient hum, which is exactly a 60-odd dB drop in floor. A
> failed ADC would be expected to read zero, full scale, or noise — not a clean, quiet, plausible
> floor.
>
> **If this holds, the Z axis is not blocked and `ADC2` is fine.** `[gap]` It is a hypothesis from the
> schematic, not a measurement, and the same ninety-second test settles it either way.
>
> **This is now the highest-value ninety seconds on the bench:** a known level into P9 and then the
> same level into P11, back to back, with John's RME. It was an if-time item in
> `inbox/peter/2026-09-18-003`; on this architecture it gates an axis.

`[gap]` **Lane budget is exact, with nothing spare.** `[repo]` One 1860 reaches the host as two stereo
lanes (`SDATAO_0`, `SDATAO_1`) = **4 channels**. Three axes plus one reference mic is **exactly 4**.
Any fifth signal needs a second serial port pair or a different part.

---

## 4. Running two EVBs together — what UG-2017 actually says

`[fetched]` EVAL-ADAU1860 user guide UG-2017 Rev. 0, read this session:

1. **I²C address is strappable on switch `S14`: `0x64` / `0x65` / `0x66` / `0x67`.** Default is
   `0x64` on both boards, so **one must be changed** before they share a bus. This is a switch
   setting, not a problem — but it is the first thing that bites.
2. **Clock them together, or they will beat.** Three MCLK sources are provided: an external MCLK into
   `MCLKIN` via **`P3`** with the on-board oscillator disabled by a jumper on **`P25`**; the on-board
   **24.576 MHz oscillator**; or the on-board 24.576 MHz crystal. **Run one board's clock into the
   other's `P3`.** Two free-running oscillators on one head means two cancellers drifting against
   each other and against the comm audio — an audible, intermittent fault that will look like a DSP
   bug for a week.

   > **Correction, 2026-09-21** `[fetched]` UG-2017 p.12/13, read from the PDF rather than a mirror
   > summary: **`P3` is Serial Audio Port 1**, and the external MCLK input is specifically **pin 10
   > of `P3`**. The source is selected by **`P8`** (`EXT_MCLK`/oscillator), which "must be used with
   > `P27`" (`XTALI/MCLKIN` option); **`P25`** disables the on-board oscillator. So "into `P3`" is
   > right only at pin 10, and it is `P8`+`P27` that do the selecting. The advice to share one clock
   > stands unchanged.
   >
   > Also established the same day, and it bears on §4.5's level-shifting note: the EVB's **control
   > port is 3.3 V** — a `PCA9517DP` I2C buffer and six `FXLP34P5X` translators sit between a `3.3V`
   > rail and `IOVDD` (Figure 14) — **but the serial audio headers `P2`/`P3` are 1.8 V with no
   > translators**, and `IOVDD` cannot be moved off 1.8 V (`U10` is a fixed `ADP1715ARMZ-1.8`).
   > **I2C needs no shifter; the audio clock does.** Full analysis: `docs/rig-logic-levels.md`.
3. **Single-ended vs differential is a per-channel jumper pair**, so mics-differential and
   accelerometer-single-ended coexist on one board with no rework: ADC0 = `P104`/`P105`,
   ADC1 = `P12`/`P14`, ADC2 = `P13`/`P15` (pins 1–2 differential, pins 2–3 single-ended).
4. **The analog output `P30` has a 32 Ω load fitted by default.** `[repo]` The aviation earphone is
   **320 Ω** and the summing amplifier presents 10 kΩ. **That load must come off** before any level
   measurement taken on the bench means anything about the aircraft.
5. Supplies: USB or a single 5 V; AVDD/HPVDD 1.8 V, IOVDD 1.8 V, DVDD 0.9 V from on-board LDOs.
   `[repo]` The 1.98 V IOVDD ceiling against a 3.3 V CM5 is the known level-shifting problem from
   `docs/h1-audio-board-codec-selection.md` §1 and it does not go away on the EVB.

---

## 5. What this changes downstream

- **The summing amplifier becomes two independent single-input summers, not a shared one.** Each cup
  has its own DAC, so `docs/anc-dvnc-summing-amp.md`'s `U1A` differential receiver is duplicated per
  chip and `ANTI` is no longer a shared node. The headroom budget (§5 there) is unchanged; the L–R
  question disappears completely.
- **`[repo]` §22's "per-ear ANC would need 2 DACs + 2 feedback mics = different codec" is now
  satisfied** — not by a different codec, but by two of this one.
- **`[repo]` §19's "channel budget is full with nothing spare" was true per chip and is still true.**
  Two chips does not create slack; it creates a second exactly-full chip. Any future analog channel
  still forces a part change.

## Open

1. `[gap]` **Ruling: split by ear, not by function?** Everything above depends on it.
2. `[gap]` Which ADXL354 axis, which range strap, and what PGA — all wait on a vibration measurement
   at the headset mount in the real airframe.
3. `[gap]` Boom voice: analog noise-cancelling electret (costs ADC2 + a bias network you design) or
   two PDM MEMS beamformed (costs nothing, needs the DMIC/ADC co-routing confirmed).
4. `[gap]` DVNC parameter transport between chips — A2B downstream slot 2 as Rev G specifies, or a
   direct SPT1 chip-to-chip link.
5. `[gap]` **Still open from §19 and still decides whether any of this is worth building: does the
   target headset already have its own ANR?** Two cancellers in one earcup is worse than either alone.

## Sources

- ADXL354/ADXL355 Rev. A — `https://www.radiolocman.com/datasheet/pdf.html?di=130145` (mirror;
  analog.com remains unreachable from this machine, the 2026-09-06 scar) `[fetched]`
- IM73A135V01 datasheet Rev. 1.00 —
  `https://www.infineon.com/assets/row/public/documents/24/49/infineon-im73a135-datasheet-en.pdf` `[fetched]`
- EVAL-ADAU1860 UG-2017 Rev. 0 —
  `https://docs.ampnuts.ru/analog.com.datasheet/adau1860/related_data/eval-adau1860-ug-2017.pdf` `[fetched]`
- In-repo: `docs/johns-bitmap.html`, `docs/h1-headset-mute-relay.md` §19/§22,
  `docs/h1-audio-board-codec-selection.md`, `docs/anc-dvnc-summing-amp.md`

---

## 6. The 1 December demonstrator — what to build, what to cut, what will bite

**~11 weeks from 2026-09-14.** The objective is to *prove the technologies*, not to prototype the
product. That changes the answer in §2, and it changes what is on the critical path.

### 6.1 Split by function — but give each function its own EAR

Peter's split works for a demonstrator, and it works much better with one addition: **put each chip's
DAC in a different earcup.**

| | **EVB 1 — DVNC, LEFT cup** | **EVB 2 — ANC, RIGHT cup** |
|---|---|---|
| ADC0 | **ADXL354**, one axis, single-ended — harmonic reference | IM73A135 **feed-forward**, outside the cup, differential |
| ADC1 | **IM73A135** in-cup **error mic** — this is what *measures* the cancellation | IM73A135 **feedback / error**, inside the cup, differential |
| ADC2 | spare — second axis, or an external reference mic | boom electret (§3), or leave for a second FF mic |
| DAC | **left earcup** | **right earcup** |

Three things this buys:

1. **No summing amplifier is needed for December at all.** Each DAC owns its own transducer.
   `docs/anc-dvnc-summing-amp.md` comes off the critical path entirely — it is a product problem,
   and it is unblocked anyway by a measurement (the panel) that has nothing to do with this demo.
2. **You can A/B each technology live, by ear, on one head** — cover one ear, then the other. That is
   a *better* demonstration than either technology alone, and it is the one thing a room full of
   people can evaluate without instruments.
3. **The in-cup error mic on EVB 1 is not optional.** Without it you can hear DVNC but you cannot
   *measure* it, and a demo that produces a number ("−N dB at blade-pass") is worth several that
   produce an opinion. Peter's "analog mic" on the DVNC board is exactly this — the allocation above
   just names its job.

Clock drift between the two boards does not matter here (two acoustically independent cups, no shared
signal) — but **wire `P3` from one board's clock to the other anyway** (§4.2). It is one jumper and
one wire, and it removes a variable you would otherwise have to rule out at the worst moment.

### 6.2 What comes OFF the December critical path

Everything the demo does not need to prove:

- **The CM5.** `[fetched]` Lark Studio drives the EVB over USB and the board self-powers from it.
  Dropping the CM5 also drops the **1.98 V IOVDD vs 3.3 V level-shifting** problem
  (`docs/h1-audio-board-codec-selection.md` §1), the RP1 four-lane I2S work, and all CM5 integration.
- **The A2B link and the AD2428W.** Not needed to prove cancellation.
- **The summing amplifier, `T1`/`T2`, `K1`/`K2` and the whole `audio-mute` sheet.**
- **The panel measurement** (open item 21 of `status.md`). It gates the product, not the proof.

That is a large amount of risk removed, and none of it weakens the demonstration.

### 6.3 What CANNOT come off, ranked by schedule risk

1. **The FastDSP implementation. This is the whole schedule.** `[fetched]` Lark Studio has a
   drag-and-drop FastDSP schematic designer with filter coefficient generation and magnitude/phase
   visualisation, the FastDSP core has a reduced instruction set explicitly optimised for noise
   cancellation, and a Lark SDK ships with drivers in source. The tooling is real.
   `[gap]` **What is not established is whether Lark Studio ships ready-made ANC blocks — FF/FB
   filters, a filtered-x LMS — or whether they have to be written.** That single question decides
   whether 1 December is comfortable or heroic.
   **Do this in week one, before ordering anything: install Lark Studio and look.** It costs a day
   and it is the highest-information action available.
2. **Acoustics and mechanics.** Where the FF mic sits outside the cup and where the FB mic sits
   inside is most of ANC performance, and it is a mechanical problem with fabrication lead time, not
   an electrical one.
3. **A repeatable noise source.** A canceller cannot be tuned against an aeroplane you fly
   occasionally. A recorded cockpit played through a speaker on a bench, with a measurement mic in
   the cup, is a prerequisite for tuning — not a nicety.
4. **The analog front end.** Lowest risk of the four. Resistors, caps and a quiet rail.

### 6.4 Procurement — and the one find that removes a lead-time item

**Buy `KIT_IM73A135V01_FLEX`** (order code `KITIM73A135V01FLEXTOBO1`, at Mouser / Farnell / Newark).
`[fetched]` **Five IM73A135V01 microphones pre-soldered on 25 × 4.5 mm flex boards, plus one adapter
board, connected by a 6-position ZIF.**

This matters more than it looks. The bare IM73A135 is a **4 × 3 × 1.2 mm** bottom-port MEMS part —
it cannot be hand-wired, it needs a breakout PCB, and a breakout is a fab cycle you do not have spare
weeks for. **The flex kit deletes that item**, and a 25 × 4.5 mm flex strip is the right physical form
for threading a microphone into an earcup in the first place. Five mics is exactly the demo's need:
2 feed-forward, 2 feedback/error, one spare.

Also needed: **2 × EVAL-ADAU1860EBZ** (DigiKey `15848881`, Newark `18AM2474`), an **ADXL354** — which
still needs a small breakout, so **fab it in week 1–2** — a quiet rail for the accelerometer and mics
(`[repo]` §19's `3V3_MIC` argument applies to the demo too: ANC noise floor is set by the mic
supply), and the earcup itself.

`[gap]` **Which earcup?** This is §19's open item 18 in its most urgent form: **if the target headset
already has its own ANR, the December demo will be two cancellers fighting in one cup**, which
performs worse than either alone and will read as "the technology does not work." The demo needs a
**passive** headset, or a cup with its ANR defeated, and that needs deciding before anything is
ordered.

### 6.5 Phase 2, if the schedule allows — and it is the phase that matters most

The function split never tests the thing most likely to fail in the product: **DVNC and ANC sharing
one DAC and one error mic in one cup.** So once each works alone:

> **Move both onto one chip, one cup: ADC0 = FF mic, ADC1 = FB mic, ADC2 = ADXL354, DAC = that cup.**

That is exactly §2's per-cup allocation, reached as the **last** demo step instead of the first. It
costs no new hardware — it is a re-patch and a Lark Studio reload — and it converts the December
demonstration from *"both technologies work"* into *"both technologies work together on the silicon
we are going to ship."*

### 6.6 Week-one checklist

1. Install Lark Studio; answer §6.3's `[gap]` about ANC blocks. **Before ordering.**
2. Decide the earcup, and whether it already has ANR (§6.4).
3. Order 2 × EVAL-ADAU1860EBZ and `KIT_IM73A135V01_FLEX`.
4. Fab an ADXL354 breakout with the AC-coupling caps and a quiet rail (§3).
5. On arrival, **before anything else:** set `S14` on the second board to `0x65` (both ship `0x64`),
   and **remove the 32 Ω load on `P30`** (§4).
