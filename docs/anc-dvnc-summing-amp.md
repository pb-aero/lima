# The summing amplifier for aircraft audio + DVNC/ANC

**Date:** 2026-09-14 · **Agent:** LIMA · **Status:** topology proposal, `[gap]` not ruled, not drawn.

Peter, 2026-09-14: *"what does the summing amp look like for the aircraft audio with dvnc/anc"*

Provenance: `[fetched]` = read from the vendor PDF this session, spec quoted · `[derived]` = arithmetic
shown · `[repo]` = in this repository · `[gap]` = not established, do not assume.

---

## 1. Which node this is, because there are two

| | Node | Where it lives |
|---|---|---|
| **A** | **AeroNode-lite ↔ aircraft panel.** The intercom's `HS_L`/`HS_R` earphone lines, shared with AeroNode's ADAU1860 DAC. | `[repo]` `kicad/aeronode-lite-audio/after/audio-mute.kicad_sch`, ruled across §16–§26 of `docs/h1-headset-mute-relay.md` |
| **B** | **Inside an H1 cup.** Program L/R arrives over A2B as PCM; DVNC™ parameter frames ride slot 2 at ~10% occupancy with a PCM twin on slot 3. | `[repo]` `docs/johns-bitmap.html` — John's Rev G bit map |

**The summing amplifier is electrically the same circuit in both places.** The difference is what it is
summing *against*: in A the comm audio arrives as an analog line already driven by somebody else's
amplifier; in B it arrives as PCM and could equally be summed in the DSP. This document draws A,
because that is the node that exists in our schematic and is currently unsolved. §7 says what changes
for B.

**DVNC does not change the analog circuit.** `[repo]` It is per-harmonic *parameter* frames —
synthesised tonal cancellation at engine/prop harmonics — which means it reaches the analog world
through the same one DAC as broadband ANC. It changes the *headroom and bandwidth budget* (§5), not
the topology.

---

## 2. What is built today, and its three measured limits

`[repo]` §21/§23: AeroNode's mono DAC drives `T1` and `T2` primaries in parallel; each secondary
feeds one channel through a 0 Ω `R1`/`R2` onto `HS_L`/`HS_R`, which the panel is **also** driving.
That is a **passive parallel sum onto a node another amplifier owns**, and it has three limits that
no resistor value can fix:

1. **Authority is set by the panel's output impedance, not by us.** `[derived]` §21: intercom live,
   AeroNode lands at **−33 dB** into a stiff panel. §25 puts the anti-noise at the ear at
   **40.5 mV** worst case.
2. **No gain is available.** A 1:1 transformer cannot amplify. §18's *"level still needs ears"* gap
   has been open since 2026-09-09 and no passive change closes it.
3. **`HS_L` can exceed the codec's pin rating on its own.** `[derived]` §26: a 1.5 V rms panel puts
   **2.12 V** peak on the node against the ADAU1860's `[fetched]` **2.1 V** signal-pin limit. Something
   must stand between the codec and that node in all cases.

§25 proposed an op-amp (Option C) and §26 **retracted** it, correctly, because it was drawn as an
op-amp **sharing** the node — which forces the output stage to swing the panel's full range on a rail
AeroNode does not have, clipping the pilot's radio audio.

---

## 3. The thing §25/§26 both missed: a summing amp is a SERIES insertion

A real summing amplifier does not join the node. **It breaks it.** The panel becomes an *input* to the
amplifier through a resistor, the anti-noise becomes a second input, and the amplifier's output is the
only thing the earphone sees.

That single change retires every one of §2's limits at once:

- The panel now drives a **10 kΩ input**, not a 160 Ω earphone, so **its output impedance stops
  mattering** — ANC authority no longer depends on the unmeasured number in open item 20.
- The summing node is a **virtual ground**, so the codec's `HPOUT` never sees the panel's swing —
  §26's constraint is satisfied **without a transformer**.
- Gain is a resistor ratio, so §18's level gap closes by arithmetic.
- `HS_L` and `HS_R` never meet, so the L–R bridge question (§22) cannot come back.

What it *buys* in exchange is a headroom problem and a fail-passive obligation. Both are real. §5 and §6.

---

## 4. The circuit

Three op-amps out of one quad. `U1A` converts the differential DAC output to single-ended once
(the job `T1`/`T2` do today); `U1B` and `U1C` are the two summing amplifiers, one per ear.

```
                                     +---------------------------- +VA (+5 V)
                                     |                   |
   ADAU1860                          |               [LM27762]  <- 5V_NODE
   HPOUTP o---[ R10 10k ]---+--------|---.               |   PGOOD ---> relay coil enable (§6)
                            |        |   |               |
                        [R12 10k]    |  |\               +---------- -VA (-5 V)
                            |        +--|+\  U1A
                           GND          |  >------+----o  ANTI  (single-ended anti-noise,
   HPOUTN o---[ R11 10k ]---+-----------|-/       |        DVNC + ANC, referenced to AGND)
                            |        +--|/        |
                            +---[R13 10k]---------+
                                     (diff receiver, G = 1)


   PANEL_L o--||---[ R20 10k ]---+                          K1a (G6K-2F-Y, Form C)
             C20                 |                        NC o------------------o
             2.2u                |     [ R22 10k ]           |                  |
                                 +-----/\/\/\----+           |                  |
    ANTI o------[ R21 10k ]------+               |     +-----o COM              +--o J11.1
                                 |    |\         |     |     |                     (HS_L,
                                 +----|-\  U1B   |     |  NO o---+                  headset
                                      |  >-------+-----|---------+                  left)
                                 GND--|+/              |
                                      |/          PANEL_L (direct, fail-passive bypass)

   PANEL_R o--||---[ R30 10k ]---+   ... U1C identical ...  K1b ... ---o J11.2 (HS_R)
             C30                 |
             2.2u          ANTI --+---[ R31 10k ]

   U1D: spare. Tie +in to AGND, short out to -in, or DNP.
```

**Transfer function**, `[derived]`, with every resistor at 10 kΩ:

```
ANTI     = HPOUTP - HPOUTN                          (unity, differential -> single-ended)
HS_L_out = -( PANEL_L  +  ANTI )                     comm at unity, anti-noise at unity
```

- **Comm at unity is deliberate.** The pilot's volume knob keeps meaning what it meant. Any gain here
  is a change the pilot did not ask for on a safety-critical path.
- **ANC gain is `R22/R21`** and is the only knob worth turning. `R21` = 5 kΩ gives ×2.
- **The inversion is harmless.** Both ears invert equally, so comm imaging is unchanged, and ANC
  polarity is a DSP sign — it must be calibrated on the bench regardless of what the analog does.

### Why 10 kΩ and not 2.2 kΩ

`[derived]` The panel's own output impedance adds to `R20`. At `R20` = 10 kΩ an unmeasured panel
anywhere in the 10–600 Ω range costs at most **6% of comm level (0.5 dB)**. At 2.2 kΩ the same
unknown costs **27% (2.4 dB)** — an audible, uncontrolled error on the radio path. The noise penalty
for choosing 10 kΩ is nothing that matters: `[derived]` noise gain 3, output noise density
`√(3.3n·3)² + 3·(12.8n)²` ≈ **24 nV/√Hz** → **3.4 µV rms** over 20 kHz at the ear. Inaudible.

**The resistor value is set by an impedance you have not measured, not by noise.** That is the right
way round for this circuit.

### What it deletes

`T1`, `T2` (`SM-LP-5001` ×2 — ~$4, two 12.8 × 9 mm footprints, 7.5 mm of height, and §11.4's
`[gap]` that they are **not flight parts**: −20 °C to +85 °C, `UL60950`), plus `R1`/`R2`. The
differential→single-ended job they do moves into `U1A`, which also gives gain, which they cannot.

---

## 5. Headroom is the whole design, and DVNC is why

The op-amp must now **produce** the panel's full level instead of merely surviving it. That obligation
does not go away with series insertion — it moves.

`[derived]` Worst case is the **coherent** sum, and DVNC is exactly the case where it is not
conservative to assume otherwise: a sustained per-harmonic cancellation tone has no crest factor to
hide behind, unlike speech.

| Panel level | + anti-noise | Required peak |
|---|---|---|
| 1.0 V rms | 1.0 V rms | 2.83 V |
| 1.5 V rms | 1.0 V rms | 3.54 V |
| **2.0 V rms** | 1.0 V rms | **4.24 V** |

`[fetched]` OPA1664 output swing is specified as `(V−) + 0.6` to `(V+) − 0.6` **at RL = 2 kΩ**.
`[gap]` **It is not specified at 320 Ω and will be worse** — the swing-vs-load curve must be read off
the typical characteristics before this is committed.

| Rail | Usable peak (at the 2 kΩ spec) | Covers a 2 V rms panel? |
|---|---|---|
| ±4.5 V | 3.9 V | **No** |
| ±5.0 V | 4.4 V | 0.3 dB of margin — **not margin at 320 Ω** |
| +12 V single-ended | ~5.4 V about a 6 V mid-rail | Yes, comfortably |

**So the rail is decided by a number nobody has measured.** This is the same measurement §26 closed on
and it is now load-bearing for a second reason:

> `[gap]` **Measure the panel's open-circuit output voltage and its output impedance.**
> Open-circuit, not loaded — the amplifier presents 10 kΩ where the earphones presented 160 Ω, so the
> panel will read **higher** into us than it does into a headset.

### If the panel turns out to be ≤1.5 V rms: ±5 V split rails

`[fetched]` **LM27762** (TI, `SNVSAF7`): inverting charge pump + LDO on the negative side, LDO on the
positive, **±1.5 V to ±5 V adjustable, ±250 mA**, `V_IN` **2.7–5.5 V**, 2 MHz, **22 µV rms output
noise (10 Hz–100 kHz, IL = 80 mA)**, 390 µA quiescent, WSON-12 **3 × 2 mm**.

- **Feed it from `5V_NODE`, not `VBAT`.** `[repo]` `VBAT` is 5.0–7.3 V and varies; the LM27762's input
  ceiling is **5.5 V**. Getting this wrong destroys the part.
- `[derived]` Load is trivial: 4.24 V pk into 320 Ω = **13.3 mA peak per channel**, 26.6 mA both,
  against ±250 mA available and the OPA1664's `[fetched]` ±30 mA drive / ±40 mA short-circuit at 5 V.
- 22 µV rms of rail noise against the OPA1664's supply rejection is nothing at the ear.

**Split rails are worth more here than the headroom alone**, for two reasons that matter specifically
to DVNC:

1. **DC-coupled output.** No output capacitor means flat response to DC, and DVNC's cancellation tones
   live at **50–300 Hz** where a coupling cap into 320 Ω starts to cost phase — and ANC is a
   *phase* problem, not a level problem. A 47 µF cap corners at 10.6 Hz but is still −0.4° at 50 Hz
   through a part with a tolerance; the transformer it replaces was worse.
2. **No transfer thump.** A single-rail design charges its output cap to mid-rail through the
   earphone. Every bypass↔amp transfer (§6) then pops in the pilot's ear. Split rails sit at 0 V and
   have nothing to discharge.

### If it turns out to be 2.0 V rms

±5 V does not have honest margin and the answer is a **+12 V boost with a buffered mid-rail and
47 µF output coupling**, accepting the pop and the LF phase, **or** limiting the anti-noise to
~0.5 V rms in the DSP and keeping ±5 V. `[gap]` That trade needs the measurement before it is worth
arguing.

---

## 6. Fail-passive, and the part of this that is a safety argument

Series insertion puts AeroNode **inside the radio path**. That is the price, and it must be paid in
hardware, not software.

`[repo]` `K1` is already an **Omron G6K-2F-Y**, DPDT 2 Form C, gold-alloy bifurcated crossbar —
exactly the right contact class for this, and it has exactly the two changeovers needed:

- **De-energised → bypass.** `PANEL_L`→`HS_L`, `PANEL_R`→`HS_R`, direct copper. AeroNode dead, AeroNode
  removed, AeroNode on fire: the pilot has their radio.
- **Energised → through the amplifier.**

**Gate the coil on `PGOOD`.** `[fetched]` The LM27762 carries a Power-Good output. Wiring it in series
with the GPIO in the coil drive means **a rail collapse drops the headset back to direct copper in
hardware, with no software in the loop.** That is the cheapest safety feature in this whole block and
it exists because the rail IC already has the pin.

Two consequences that need Peter, not me:

1. **`K1` stops being an operating control and becomes a guard.** `[repo]` §16 ruled `K1` is a
   *changeover* — AeroNode's voice replaces the radio. With a summer, AeroNode's voice **mixes** with
   the radio, and `K1` only ever moves on a fault. That is a behaviour change and it needs a ruling.
   It is also better on its own terms: the contacts stop cycling in normal use, which retires §5's
   dry-circuit contact-oxide worry almost entirely.
2. **Transfer must be muted.** DSP mute → relay transfer → unmute after the operate time.
   `[gap]` `G6K-2F-Y` operate/release time not read this session.

### Fault case: what the codec sees if the amplifier dies

`[derived]` With `U1` unpowered the summing node floats, so the panel reaches `HPOUT` through the
`R20`/`R21` divider: `2.83 V pk × 10k/(10k+10k)` = **1.41 V pk**, inside the ADAU1860's `[fetched]`
2.1 V limit — and in practice lower still, because the op-amp's input clamp diodes hold the node near
its dead rails. With `R21` at 5 kΩ (ANC gain ×2) it falls to **0.94 V pk**.

**The summing resistors are themselves the protection the transformer was being kept for** (§26). That
is `[derived]`, not measured, and it is exactly the class of claim this repo has been bitten by before
— **it needs a bench check with the rail pulled, not a calculation.**

---

## 7. What changes inside an H1 cup (node B)

`[repo]` In the cup, comm audio arrives as **PCM on A2B slots 0/1** and DVNC arrives as **parameter
frames on slot 2 with a PCM twin on slot 3**. Both are already digital and already on the same chip.

**So in the cup, sum in the DSP and skip most of this document.** One DAC, one driver, no summing
node, no panel impedance, no fail-passive relay (the cup is not in the radio path — its bypass is the
headset's own passive mode). The analog part reduces to the earcup driver and its headroom budget,
and §5's coherent-sum arithmetic is the part that still applies.

**The reason node A cannot do the same** `[fetched]`: the ADAU1860 has **three ADCs**, and `[repo]`
§19 spends all three on boom voice, ANC feedforward and ANC feedback. There is **no fourth input to
digitise the panel with**, so node A's sum is forced into the analog domain. That is a consequence of
a decision already taken, and it is worth writing down, because "just sum it in the DSP" is the
obvious first suggestion anyone makes about this circuit and it is unavailable.

---

## 8. What this is worth, honestly

**Gained:**

- `[derived]` Anti-noise at the ear goes from §25's **40.5 mV** worst case to the DAC's full
  **1.0 V rms** — about **+28 dB of ANC authority**, and it no longer depends on the panel at all.
- §18's level gap closes; §22's L–R bridge cannot recur; open item 20 stops gating ANC authority.
- Two non-flight-rated transformers leave the BOM.
- AeroNode's voice mixes with the radio instead of replacing it.

**Paid:**

- AeroNode is in the radio path, mitigated by a relay that is already in the design and a `PGOOD`
  interlock that is free.
- Galvanic isolation is gone. `[repo]` §25 ruled AeroNode floats on battery in flight, so the audio
  ground is its **only** bond — one bond is not a loop — but that ruling is now load-bearing for this
  circuit too, and if AeroNode is ever charged from ship's power in flight this trade reopens.
- One quad op-amp, one rail IC, ~20 passives, and a rail whose voltage is not yet decidable.

**Not established, and blocking:**

1. `[gap]` **Panel open-circuit output voltage and output impedance.** Decides the rail, which decides
   the part count. Nothing below this is worth refining first. Ten minutes with a scope and a resistor.
2. `[gap]` OPA1664 output swing **at 320 Ω** — spec is only given at 2 kΩ.
3. `[gap]` ADAU1860 `HPOUT` common-mode voltage, against the op-amp input common-mode range, if `U1A`
   is DC-coupled. DC coupling is what preserves DVNC's LF phase, so this is worth checking rather than
   defaulting to a capacitor.
4. `[gap]` Ruling needed: does `K1` stop being a changeover (§6.1)?
5. `[gap]` §19's question is still open and still decides whether any of this is worth building —
   **does the target headset already have its own ANR?** Two cancellers in one earcup is worse than
   either alone.

## Sources

- OPA1662/OPA1664, TI `SBOS489` — `https://www.ti.com/lit/ds/symlink/opa1662.pdf` `[fetched]`
- LM27762, TI `SNVSAF7` — `https://www.ti.com/lit/ds/symlink/lm27762.pdf` `[fetched]`
- In-repo: `docs/h1-headset-mute-relay.md` §16–§26, `docs/h1-audio-board-codec-selection.md`,
  `docs/johns-bitmap.html`, `kicad/aeronode-lite-audio/after/audio-mute.kicad_sch`

---

## 9. CORRECTION 2026-09-15 — the earphone load was wrong, and it changes the op-amp

Peter asked whether the earphone is 150 Ω per speaker. **It is not — 150 Ω is the pair.** But he was
right that the number in this document is wrong, and the correction goes the way that costs us.

### What the sources actually say

`[fetched]` **David Clark H10-13.4**, verbatim: *"Earphone Impedance: 150 ohms (300 each; wired in
parallel)"*. `[fetched]` The general-aviation convention is the same everywhere: **300 Ω elements,
paralleled to 150 Ω**, and aircraft audio amplifiers are specified to drive 300 Ω or higher.

### Where my 320 Ω came from, and what I did wrong with it

`[repo]` `docs/h1-headset-mute-relay.md` §2 quotes the Bose A20 brochure: *"Monaural mode: 160 ohms
ON and OFF · Stereo mode: 320 ohms ON and OFF."* That is **the A20's input impedance in each mode**,
and it is quoted correctly. What I did wrong was **generalise one ANR headset's input impedance into
"the earphone load"** and then build every level, current and headroom number on it.

**The A20 figure is also the best case.** A passive GA set is 300 Ω per element, and in **mono wiring
— which most GA installations are — both elements sit in parallel on one channel.** So the worst case
a summer actually drives is **150 Ω**, not 320 Ω. I designed to the favourable end of the range and
then wrote it down as the value.

### What changes

| | At 320 Ω (as written) | At 150 Ω (worst case) |
|---|---|---|
| `[derived]` Peak current, 4.24 V pk | 13.3 mA | **28.3 mA** |
| vs OPA1664's `[fetched]` ±30 mA drive | 44% — comfortable | **94% — no margin** |
| `[derived]` `T1`/`T2` level, 1.0 V rms through 230 Ω DCR | 0.582 V rms | **0.395 V rms — 3.4 dB worse** |

**§4's part choice does not survive.** The OPA1664 is a general-purpose audio op-amp and 28.3 mA is
at its rating, where distortion rises. The output stage becomes a **headphone driver**:
`[fetched]` **OPA1622**, +145 / −130 mA, ±2 V to ±18 V, designed for exactly this load. `U1A`, the
differential receiver, is unaffected — it drives 10 kΩ and needs the low noise, not the current, so
an OPA1662 half does it.

**And it makes §18's open "level needs ears" gap worse**, not better, if `T1`/`T2` are kept: 3.4 dB
less at the ear than §23 claimed.

### The honest conclusion

`[gap]` **Which headset is still not chosen** — §19's open item 18, open since 2026-09-09, decides
this number as well as whether the ANC path is worth building at all. The right response is not to
pick 150 or 300 but to **design for 150 Ω** and then **measure the real set**: voice-coil DC
resistance runs about 80% of nominal impedance, so a meter across the plug settles in thirty seconds
what no datasheet will.

**The generalisable lesson, and it is the one this repo keeps relearning:** a number quoted correctly
from a datasheet can still be the wrong number, because **the error is in the scope of the claim, not
in the digits.** "320 Ω" was true of a Bose A20's input. It was never true of "the earphone load",
and nothing in the arithmetic downstream could have caught that.

---

## 10. 2026-09-15 — the 150 Ω is a Bose A30 in mono, and that answers a bigger question

Peter: *"I'm not sure of the headset, the impedance I have stated is based on the Bose A30 mono."*

### The number is right, and it is better than right

`[fetched]` **Bose A30: headphone input impedance 150 Ω mono, 300 Ω stereo, per RTCA DO-214A.**

So **150/300 is not one headset's figure — it is the standard.** That is why the David Clark
H10-13.4 is *"150 ohms (300 each; wired in parallel)"* and why the A20's 160/320 was the outlier.
§9's correction stands and is now on firmer ground: **design to 150 Ω, and it is a specification
rather than a guess.**

### But it half-answers §19's open item 18, and the answer splits the two technologies

An A30 has its own ANR. §19 flagged this on 2026-09-09 as the thing that decides whether the ANC path
is worth building, and it has been open since. If the target is an A30, the decisive fact is
structural: **that 150 Ω is the input impedance of Bose's electronics, not a voice coil.** The
transducer is driven by Bose's own amplifier, downstream of Bose's own ANR. Anything we send arrives
as *program audio*.

| | Broadband ANC (FF + FB) | DVNC (per-harmonic) |
|---|---|---|
| Must reach the transducer | **Yes** — the loop closes acoustically | No — injects as program audio |
| Tolerates a fixed but unknown path latency | **No.** Fatal for broadband | Yes — calibrate phase once per harmonic |
| Through an ANR headset's audio input | **Not viable** | Viable |
| Against the headset's own ANR | **Two cancellers fighting** — §19's warning | Complementary: it cancels the tonal residue broadband ANR leaves |

`[derived]` The asymmetry is latency tolerance. A feedback loop through a black box of unspecified
delay cannot be closed at all. A **sustained harmonic** only needs the path's phase *at that one
frequency*, which is fixed and measurable — so an unknown constant latency is a calibration problem
for DVNC and a fatal one for ANC.

**This is not a consolation prize.** Cancelling prop and engine orders *on top of* a good broadband
ANR is the differentiated product; adding a second broadband canceller inside a Bose earcup is the
fight §19 already named.

### What it does to the December demonstrator

- **EVB 1's allocation already is the DVNC-on-an-ANR-headset demo** — accelerometer reference, in-cup
  error mic, DAC into the cup — and it works through the A30's audio input with **no surgery**. The
  error mic's role changes from control-loop sensor to **measurement** sensor, which is what
  `docs/anc-dvnc-schematics.html` sheet 1 already calls it.
- **EVB 2's FF/FB ANC cannot be proven on an A30.** It needs a passive cup, or one with its ANR
  defeated. That is now a procurement item, not a footnote.
- `[derived]` **Mono forecloses per-ear anything through the audio input.** 150 Ω *is* both earcups in
  parallel on one channel. If the aircraft intercom is mono, the second board buys nothing on the
  audio path — only on the sensing side.

### One lead worth chasing before any bench work

`[fetched]` The A30's sensitivity is quoted as **96.5 ± 3.5 dBA SPL, measured to RTCA DO-214A**.
`[gap]` If DO-214A names the reference input level that sensitivity is referred to, **§18's "level
needs ears" gap closes analytically** — that would be the first route to the number that does not
need an aircraft, and it has been open since 2026-09-09.
