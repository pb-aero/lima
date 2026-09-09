# Headset mute relays — GPIO_RLY_SPKR / GPIO_RLY_MIC

**Date:** 2026-09-08 · **Agent:** LIMA · **Status:** design note. Nothing wired, nothing drawn.

Peter, 2026-09-08: *"I need to start looking at wiring up a relay board to mute the audio left and
right going to the headset and electret mic from the headset when i2s audio path is active."*

**Peter's rulings this session:** bench proof first; design for a GA aviation headset but prototype
on the TRRS rig that is already plugged in; **mute only**, not changeover; **CM5 GPIO asserts it**,
software-driven, no hardware activity detector.

Provenance: `[fetched]` = read from the vendor document myself · `[derived]` = arithmetic shown ·
`[measured]` = I ran it · `[assumed]` / `[gap]` = not established, do not build on it.

---

## 1. This is not a blank sheet

`[repo]` The signals already exist on John's AERONODE block diagram
(`~/aerosense/aeronode/aerosense/aeronode-lite/aeronode-audio-interface.kicad_sch`). The `AUDIO`
block takes six nets from the CM5:

```
I2S1_SDO2   I2S1_SDI2   I2S1_SDO3   I2S1_SDI3   GPIO_RLY_SPKR   GPIO_RLY_MIC
```

`docs/h1-audio-board-codec-selection.md:151` records them as **"John's fail-passive changeover
relays"**. Two GPIOs, two independent mutes — speaker and mic — which is exactly the split Peter
asked for. The audio interface sheet itself currently contains **only connectors** (J1–J4,
`Conn_01x06/08/10`); no codec and no relays are placed. So the block is agreed and the circuit is
not drawn.

**One semantic difference worth naming.** John's diagram says *changeover*; Peter has ruled *mute
only*. Section 3 shows why the difference is one link resistor per channel, so the ruling does not
have to be re-taken to keep both options open.

---

## 2. What the far side actually is, electrically

`[fetched]` Bose A20 brochure (`sarasotaavionics.com/Manuals/BOSE/A20BROCHURE.pdf`, 6 pp, pulled
and text-extracted this session — `WebFetch` gets a 403, plain `curl` with a browser UA gets 200):

| | Verbatim from the spec block |
|---|---|
| Earphone impedance | *"Monaural mode: 160 ohms ON and OFF · Stereo mode: 320 ohms ON and OFF"* |
| Electret mic bias | *"Bias required: 8 to 16 VDC through 220 to 2200 ohms"* |
| Mic sensitivity | *"Typical output is 600 mV at 114 dB SPL"* |
| Connector options | dual G/A plug, 6-pin panel, 5-pin XLR, U174 |

Three consequences fall straight out, and each one changes the circuit:

1. **320 Ω at line level is a trivial switching load.** No contact rating problem, and no arc.
2. **The mic line is not a signal line — it is a powered line.** It carries 8–16 V DC through a
   220–2200 Ω bias resistor, and the audio rides on that. Anything that opens it produces a DC
   step at the panel's mic input, and a DC step at a mic input is a **thump in every headset on the
   intercom**. This is the single hardest part of the whole job, and §4 is honest that it is not
   solved from a desk.
3. **600 mV rms is already near line level.** For reference the ADAU1860's full scale is
   **0.49 V rms single-ended** `[fetched, linux/adau1860-pi5/MIC_INPUT_P11.md]` — so an aviation
   mic at high SPL **overdrives the codec input**, the opposite of the bench problem. Attenuate,
   don't amplify. Do not carry the "buy a MAX9814" conclusion from the bench across to the aircraft.

---

## 3. Topology — one relay form, two behaviours, chosen by a link

Use a **2 Form C (DPDT) signal relay** per GPIO and wire it break-and-shunt:

```
                         ┌── NC ──────────────── intercom / source
   earphone L ── COM ────┤
                         └── NO ──[ R_MUTE ]──── GND
```

- **De-energised** (coil off, CM5 off, board unpowered): `COM–NC` closed. The pilot hears the
  radio. **This is the fail-passive state and it is a metal contact, not a logic level.**
- **Energised:** `COM–NO` closed. The earphone is tied to ground through `R_MUTE` — silent, low
  impedance, no antenna pickup — and the intercom output sees an **open**, never a short.

`R_MUTE` is the whole flexibility:

| `R_MUTE` | Behaviour | When |
|---|---|---|
| **0 Ω fitted** | Hard mute. Earphone grounded. | Peter's ruling: mute only, nothing replaces the audio. |
| **DNP (omitted)** | Series break only. Earphone left free for a codec feed summed in downstream. | If AeroNode audio is later summed into the same earphone, grounding it would short the codec too. |

**The shunt returns to AIRCRAFT ground, not AeroNode ground — see the correction in §11.3.**

**Never shunt without breaking.** A bare shunt-to-ground short-circuits the intercom's headphone
amplifier. Some GA panels have a series resistor and survive it; some do not, and which is which is
`[gap]`. The Form C break removes the question entirely.

One DPDT does both earphone channels off `GPIO_RLY_SPKR`. `GPIO_RLY_MIC` needs one pole; use the
second for a **mute-state readback** into a CM5 input, so software can prove the relay actually
moved rather than trusting that it wrote a GPIO. (§10 of `CLAUDE.md`: a control that is written,
believed and cited but not actually live is the pattern to fear. A readback contact is cheap.)

---

## 4. The mic mute is the hard one, and I cannot finish it from here

Breaking the mic line disconnects the capsule from its bias. The panel's mic input then floats up
toward the full 8–16 V through the bias resistor, and on release it steps back down. Both edges are
thumps.

The fix in principle is to make the shunt leg present a **DC load that mimics the capsule**, so the
panel's mic node barely moves across the transition — `R_MUTE` on the mic channel becomes a
calculated value rather than 0 Ω, and the shunt goes on the **panel** side, not the headset side.

**I cannot calculate it, and I am not going to pretend otherwise.** The value depends on the DC
operating point of an aviation electret capsule under its bias network, and I have no datasheet for
one — Bose publishes the bias the capsule *requires*, not the current it *draws* or the voltage it
sits at.

**Superseded in part by §10.** Peter asked 2026-09-08 whether a blocking capacitor solves this.
For the mic mute it does — and it removes the need for the measurement below entirely, because the
DC path is never broken in the first place. §10.2 has the circuit. The measurement is still worth
taking, but it is no longer blocking.

`[gap]` **Measure this before the mic mute topology is fixed:** with a real headset plugged into a
real panel, put a meter on the mic line and record (a) the DC voltage at the mic node with the
capsule connected, (b) the same with it disconnected, (c) the bias resistor value if the panel's
schematic is available. Three numbers and this section closes. Until then the mic channel gets the
same Form C footprint with `R_MUTE` as a fitted-later part.

### And the safety interlock that is not in scope yet

If the mic is muted and the pilot presses PTT, **they transmit silence and do not know it.**
Peter has ruled software-asserted GPIO with no hardware watchdog, which is the right call for a
bench proof. It is not the right call for an aircraft. Recorded here so it is a decision someone
takes rather than a gap someone inherits: before this flies, either the mute releases on PTT, or a
hardware one-shot limits how long software can hold it.

---

## 5. The part — and why a generic "relay board" is the wrong one

A typical 5 V relay module (SRD-05VDC-SL-C, 10 A, 250 VAC) has **silver-alloy contacts**. Those
need wetting current to punch through the oxide that grows on them. Headset audio and an electret
mic are dry-circuit signals — microvolts to millivolts, microamps — and silver contacts in that
service go intermittent and crackly, sometimes within weeks. This is a real failure mode, not
audiophile folklore.

The right class is a **gold-alloy bifurcated-crossbar signal relay**. Candidate, and it is already
a JLCPCB basic-catalogue part:

**Omron `G6K-2F-Y`**, DPDT 2 Form C, SMD, fully sealed. `[fetched]` from Omron's own datasheet
(`omronfs.omron.com/en_US/ecb/products/pdf/en-g6k.pdf`, pulled this session):

| Spec | Value | Why it matters here |
|---|---|---|
| Contact type | **Bifurcated crossbar** | Two contact points per pole — one dirty point does not open the circuit. |
| Contact material | **Ag (Au-Alloy contact)** | Gold alloy. This is the dry-circuit property. |
| **Minimum permissible load** | **10 µA at 10 mV DC** | The number that settles it. Our mic signal is far above this. |
| Contact resistance | 100 mΩ max | Negligible against a 320 Ω earphone. |
| Operate / release time | **3 ms max / 3 ms max** | Sets the software guard band in §7. |
| Coil, 3 VDC | 33.0 mA, 91 Ω, ~100 mW | Must-operate 80% of rated max = 2.4 V. |
| Coil, 5 VDC | **21.1 mA, 237 Ω**, ~100 mW | Preferred — less current off `5V_NODE`. |
| Mechanical life | 50,000,000 operations | Irrelevant at this duty cycle, which is the point. |
| Size | 10 × 6.5 × 5.2 mm | Two of them is a small corner of the audio sheet. |

Price `[fetched, search-result — not verified on the vendor page]`: LCSC lists `G6K-2F-Y DC3` at
**$0.81** (`C93168`), DigiKey the tape-and-reel variant at $4.76. `[gap]` Stock not checked; do
that at BOM time, not now.

Omron also make **`G6KU-2F-Y`**, a single-winding **latching** version (minimum set/reset pulse
10 ms). Latching halves the standing current but **breaks fail-passive**: a latched relay stays
muted through a power loss. **Do not use it here.** Recorded so nobody re-derives it as an
optimisation later.

### Why relays at all, when an analog switch is smaller

Because of the failure state. A TS3A-class analog switch or a PhotoMOS has an *undefined* state
when its rail collapses; a de-energised relay has a **metal contact in a known position**. For a
box that sits between a pilot and their radio, that difference is the entire safety argument.
John's choice of relays is correct — this note exists partly so it does not get "improved".

---

## 6. Drive circuit, and the one detail that decides fail-passive

```
                      5V_NODE
                         │
                     ┌───┴───┐
                     │ coil  │◄── 1N4148 flyback, cathode to 5V_NODE
                     └───┬───┘
                         │
   GPIO_RLY_SPKR ──[1k]──┤ G   2N7002 / BSS138
                         │
                   100k ═╪═ to GND (gate pulldown)
                         │
                        GND
```

- Series gate resistor 1 kΩ, flyback diode across the coil, low-side N-FET. Ordinary.
- **The 100 kΩ gate pulldown is the part that matters.** A CM5 or Pi GPIO is a *high-impedance
  input* during boot, reset and shutdown, with no guarantee about pulls. Without the pulldown, the
  relay's state through a CM5 reboot is undefined — which is to say the pilot's audio state through
  a CM5 reboot is undefined. With it, the FET is held off and the relay is guaranteed released.
  **This resistor is the fail-passive claim.** It gets a positive control in §8, not a comment.
- `[derived]` 21.1 mA through a 2N7002 (R_DS(on) ≈ 1.8 Ω at V_GS = 3.3 V) drops ~38 mV. Fine.
- Two relays energised = 42 mA off `5V_NODE`, only while AeroNode is speaking.

---

## 7. Sequencing

`[derived]` from the 3 ms max operate/release time, plus datasheet bounce of ~0.5–2.5 ms:

```
MUTE:    assert GPIO  →  wait 10 ms  →  start playback
UNMUTE:  stop playback →  wait 10 ms  →  release GPIO
```

10 ms is ~3× the datasheet maximum. Playing into a bouncing contact is what makes the buzz that
people then blame on the relay choice.

---

## 8. Bench plan — what can be proven today, and what cannot

The rig is `node@192.168.0.99` (`aeronode`, kernel `6.18.39+rpt-rpi-2712`). `[measured]` It did
**not** answer SSH while this note was written — port 22 timed out — so everything below is a plan,
not a result.

**Use the relay board Peter already has for the sequencing tests.** It will work well enough to
prove control and timing. It will *not* tell you anything trustworthy about audio quality, because
of the contact material in §5 — so if the bench shows crackle, suspect the module before the design.

### 8a. Speaker mute — provable today

The codec's analog output is proven end to end: `[measured]` 2026-09-08, Peter heard Piper TTS out
of **P30** by ear. So insert the relay in P30 → headset and both controls are available:

| Control | Action | Expected |
|---|---|---|
| **Negative** | GPIO low, play TTS | audible in both ears |
| **Positive** | GPIO high, play the same TTS | **silence in both ears** |
| **Fail-passive** | GPIO high (muted), then `sudo reboot` the Pi | audio returns during boot and **stays** returned |

The third row is the one that actually matters and the one that is easiest to skip.

### 8b. Mic mute — **cannot be proven today**

`[measured]` The bench mic path does not work yet, for two stacked reasons already recorded in
`linux/adau1860-pi5/MIC_INPUT_P11.md`: the headset is a **4-pole TRRS plug in P11's 3-pole TRS
jack**, so the mic conductor reaches no contact at all; and P11 supplies **no bias** (`R33`/`R34`
are 0 Ω, and the ADAU1860 has no `MICBIAS` pin), so a PC electret stays silent even once correctly
broken out.

**A mute on a path that is already silent is untestable** — the positive control passes for the
wrong reason, which is exactly the class of false green this project keeps getting bitten by.
So: fix the mic path first (amplified module per `MIC_INPUT_P11.md`, or the PDM route on P44/P23),
*then* test the mic mute. Do not report the mic mute as working before that.

### 8c. GPIO selection

`[assumed]` GPIO23 and GPIO24 (header pins 16 and 18) — adjacent, and with no default alt function
on a stock Pi 5. **Verify with `pinctrl get` before wiring**, and specifically keep clear of
**GPIO18–21**, which are the I2S1 four-lane bus the whole audio path depends on. The 2026-09-04
scar applies: read the mux column, not the level column.

---

## 9. What is not decided

1. ~~`[gap]` **The mic-node DC operating point** (§4).~~ **No longer blocking** — §10.2's AC-only
   shunt mute never breaks the DC path, so the operating point does not have to be known. Worth
   measuring anyway to size the shunt cap against the real source impedance.
2. `[gap]` **PTT interlock** (§4). A decision for Peter and John, not a gap to inherit.
3. `[gap]` **Where the AeroNode audio actually joins the earphone** — summed downstream of the mute,
   or nothing at all. §3's `R_MUTE` link keeps both alive at the cost of two resistors, so this does
   not block layout.
4. `[gap]` **`G6K-2F-Y` stock and current price.** Checked at BOM time.
5. **My reading of the requirement, stated so it can be corrected:** I have taken "when the I2S
   audio path is active" to mean *AeroNode is speaking and wants the pilot's attention*. There is a
   second reading this project makes plausible — `linux/adau1860-pi5/DATA_OVER_I2S.md` uses the same
   I2S link as a raw **sensor sample pipe**, and playing that to a headset would be a very loud
   noise. If *that* is the case being guarded, the mute is a hearing-protection interlock and it
   should not be software-asserted at all. **Same circuit either way** — but a different safety
   argument, and worth one sentence from Peter.

---

## 10. Blocking capacitors — answering Peter, 2026-09-08

> *"Can we use a blocking capacitor to stop the bias from affecting the analog output from the
> ADAU1860?"*

**Yes, and it is mandatory rather than optional.** But the question has two readings and they get
different circuits, so both are below. The numbers first, because they decide it.

### The two facts that settle it

`[fetched]` ADAU1860 datasheet Rev. 0, pulled and text-extracted this session
(`docs.ampnuts.ru/analog.com.datasheet/adau1860/adau1860.pdf`):

| | Verbatim |
|---|---|
| Absolute maximum, signal pins | *"Analog Input Voltage (Signal Pins) −0.3 V to AVDD + 0.3 V"* |
| Absolute maximum, pin current | *"Input Current (Except Supply Pins) ±20 mA"* |
| Absolute maximum, analog supply | *"Analog Supply (AVDD, HPVDD, and HPVDD_L) −0.3 V to +1.98 V"* |
| The output pins | F2 `HPOUTP` *"Headphone Output Noninverted"*, G1 `HPOUTN` *"Headphone Output Inverted"* |
| DAC differential output | *"Full-Scale Output Voltage 0 dBFS to DAC **1.0 V rms**"*, DC offset ±0.1 mV |
| Headphone output power | 30 mW into 32 Ω at AVDD = 1.8 V, <0.1% THD+N |

`[derived]` AVDD is 1.8 V, so a signal pin's ceiling is **2.1 V**. The aviation mic line sits at
**8–16 V**. Connect them directly and the pin is 6 to 14 volts over its absolute maximum; the fault
current through the ESD structure, worst case (16 V through a 220 Ω bias resistor), is
**(16 − 2.1)/220 ≈ 63 mA** against a ±20 mA rating. That does not degrade the part, it destroys it.
Even the gentlest case in the range — 8 V through 2200 Ω — is 2.7 mA held indefinitely on a pin
that is 6 V over its limit.

So this is not a fidelity question. **Nothing connects the ADAU1860 to an aviation mic line without
DC blocking.**

### 10.1 If the ADAU1860 is driving the biased mic line

This is the literal reading — AeroNode injecting its audio into the intercom's mic input, which is
the usual way to get audio into a GA panel without modifying it.

```
                          ┌───────────── fault path if C1 shorts, limited by R1
                          ▼
 HPOUTP ──┬──[ C1 ]──[ R1 10k ]──────────► mic line node (8-16 V, source Z ≈ R_bias)
          │           220 nF
       [ BAT54S ]     film/C0G
       clamp to       ≥50 V
       AVDD & AGND

 HPOUTN ── leave OPEN. Do NOT ground it — it is a driven output, not a reference.
```

`[derived]`, with the mic node's source impedance taken as the bias resistor, 470 Ω typical:

- **Injection level.** Single-ended off one leg gives 0.5 V rms full scale. Through R1 = 10 kΩ into
  470 Ω, the node sees `0.5 × 470/10470 =` **22 mV rms** — a sane mic level against the A20's
  600 mV at 114 dB SPL. Attenuate in the analog domain and run the DAC near full scale; the reverse
  (quiet DAC, small R1) throws away SNR.
- **Coupling corner.** `f = 1/(2π·C1·(R1 + 470))` → 220 nF gives **69 Hz**, well under the
  300 Hz–3 kHz comms band. 1 µF gives 15 Hz if you want margin.
- **R1 is the fault limiter, and that is why it sits between C1 and the line.** If C1 fails short,
  16 V through 10 kΩ is **1.6 mA** — inside the ±20 mA rating, so the on-die clamp survives it. The
  BAT54S makes that explicit rather than relying on an ESD structure for a sustained fault.

Three traps in that little circuit:

1. **Do not use X7R ceramic for C1.** Class-II ceramics lose most of their capacitance under DC
   bias — a 50 V X7R in a small case can be down 60–80% at 16 V, which walks the corner frequency
   up into the voice band. Use **film (PET/PPS) or C0G**, rated ≥50 V for a 16 V line.
2. **The output is differential and the mic line is not.** `HPOUTP`/`HPOUTN` are a driven pair.
   Taking one leg costs 6 dB, which the 26 dB attenuator makes free — but `HPOUTN` must be left
   **open**, never tied to ground. `[gap]` The abridged datasheet has no register map and no
   output-stage description, so *whether the HP amp is specified to run with one leg unloaded* is
   not established. Confirm before committing, or take it differentially into a transformer.
3. **A capacitor blocks DC. It does not break a ground loop.** Aircraft audio ground and AeroNode
   ground can sit volts apart, and tying them through an audio path is a classic avionics buzz.

### The transformer is the better answer for the aircraft — **RULED 2026-09-08, see §11**

A small 600:600 Ω audio isolation transformer does everything the capacitor does — blocks DC
absolutely, with no failure mode that passes 16 V — and also converts the differential output to
single-ended and **galvanically isolates the two grounds**. It costs more board area and some low-end
response. For a bench proof, use the capacitor. For anything that goes in an aircraft, `[assumed]`
the transformer is the right part, and I would want that argued rather than assumed.

### And an operational warning that is not electrical

Injecting into the mic line means AeroNode's voice goes wherever the pilot's voice goes. It will
trip the intercom's **VOX**, and if PTT is pressed while AeroNode is speaking, **it transmits over
the air**. If the intent is a private advisory to the pilot, the mic line is the wrong injection
point and the earphone line or a panel AUX input is the right one. Flagging, not deciding.

### 10.2 If the question was about the mic mute in §4 — the answer is better than §4

A blocking capacitor also solves the thump problem, and more cleanly than the shunt-resistor scheme
§4 left open. **Put the capacitor in the shunt leg and never break the DC path at all:**

```
 mic node ──┬───────────────────────── capsule stays connected and stays biased
            │
            └──[ C2 ]──┬──[ relay, Form A ]── GND
              100 µF   │
              NP/25 V  └──[ R2 1M ]────────── GND   (bleed)
```

- **Energised:** C2 shorts the audio to ground. The mic is muted.
- **DC is never interrupted** — the capsule keeps its bias, the panel's mic node never moves, and
  **there is no step to make a thump on either edge.**
- **R2 keeps C2's lower plate at ground** so the cap is always charged to the node voltage. Without
  it, closing the contact dumps charge and you get exactly the click you were trying to avoid.

`[derived]` Mute depth is `20·log10(Xc/(R_src + Xc))`. At 300 Hz with R_src = 470 Ω, 100 µF gives
Xc = 5.3 Ω → **−39 dB**; against the worst-case 2200 Ω bias resistor it is −52 dB. Deeper at higher
frequencies, which is the right way round for speech intelligibility.

**What this buys, and it is the real point:** §4's open item was that the shunt resistor's value
depends on the capsule's DC operating point, which I have no datasheet for. **This circuit does not
need to know it**, because it never disturbs it. `[gap]` closed by changing the circuit rather than
by measuring — which is the better kind of answer.

Two residuals, stated rather than glossed:

- `[assumed]` A capsule driving a near-short at audio frequencies is outside its normal loading.
  The DC drain current is unchanged, so I expect no harm, but it is not something I have measured
  or found stated.
- The mute is a shunt, so its depth is finite and frequency-dependent, where a contact break is
  infinite. −39 dB is not −∞. If the requirement is *provably* no audio, §3's Form C break is still
  the stronger claim — at the cost of reopening the DC step.

### 10.3 The third reading — protecting the ADAU1860's *input*

For completeness, since "output" may have been loose: if the aviation mic feeds the ADAU1860's
**ADC input**, the same 8–16 V arithmetic applies and blocking caps are equally mandatory. On the
EVB they already exist — `[fetched]` `C25`/`C26` are **22 µF** in series with `AINP2`/`AINN2`
(`MIC_INPUT_P11.md`). On a custom board, replicate them **and** add the attenuator, because §2's
600 mV at 114 dB SPL overdrives the ADAU1860's 0.49 V rms single-ended full scale.

---

## 11. RULED 2026-09-08 — transformer isolation on the aircraft side

Peter: *"use the transformer approach for the aircraft side."* §10.1's capacitor coupling is
**superseded for anything facing the aircraft**; it stays valid only as a bench expedient.

### The part

**Bourns `SM-LP-5001`**, surface-mount line-matching transformer. `[fetched]` from Bourns'
own datasheet (`bourns.com/pdfs/sm-lp-5001.pdf`, rev 05/17 — note `bourns.com/docs/...` 403s,
`bourns.com/pdfs/...` serves it):

| Spec | Value | Bearing on this design |
|---|---|---|
| Nominal impedance / ratio | **600 Ω, 1:1** | Voltage-transfer, no matching arithmetic. |
| Frequency response | **±0.25 dB, 200 Hz–4 kHz** | The aviation comms band is 300 Hz–3 kHz. It sits inside. |
| Insertion loss | 2.0 dB max at 2 kHz | 1.0 V rms in → **0.79 V rms** out. Folded into §11.2. |
| **Dielectric strength** | **2000 V rms for 1 min** | This is the isolation barrier. |
| Insulation resistance | 100 MΩ at 500 V | |
| Distortion | −76 dB at 600 Hz, −10 dBm | Far below anything speech cares about. |
| DC resistance | 115 Ω ±15% each winding | Used in the saturation and level sums below. |
| Shunt inductance | **3.8 H min** | Decides where the attenuator goes — see §11.1. |
| Power level | 10 dBm | We drive **+2.2 dBm**. `[derived]` 1.0 V rms into 600 Ω = 1.67 mW. |
| Size | 12.8 × 9.0 mm, 7.5 mm seated | Larger than the relays. Budget the area. |

`[fetched, search-result]` LCSC `C7503474`, **$1.95, 550 in stock**; Newark ~$3.56.

### 11.1 Drive the primary directly. Put the attenuator on the SECONDARY.

This is the one number that decides the layout, and getting it backwards ruins the audio:

`[derived]` The low-frequency corner is the primary's shunt inductance working against the
**source** impedance, `f = R_source / (2π·L)`.

| Attenuator position | Source impedance seen by the primary | LF corner |
|---|---|---|
| 10 kΩ on the **primary** | 10 kΩ | **419 Hz** — inside the voice band. Ruins it. |
| 10 kΩ on the **secondary** | ~116 Ω (winding DCR + HP amp) | **4.9 Hz** — irrelevant. Correct. |

So: `HPOUTP`/`HPOUTN` connect straight across the primary, and the level-setting resistor lives on
the far side.

### 11.2 The circuit, and what the transformer deletes

```
                    SM-LP-5001
                    2000 V rms
  HPOUTP ─────┐    ║        ║    ┌──[ R1 10k ]──────► aircraft mic node
              │  ) ║        ║ (  │
              │  ) ║        ║ (  │
  HPOUTN ─────┘    ║        ║    └──────────────────► aircraft MIC GROUND
                    ║        ║                          (plug sleeve — NOT AeroNode GND)
              AeroNode side │ aircraft side
                            │
                    ISOLATION BOUNDARY
```

**Three things from §10.1 disappear, and that is the argument for the ruling:**

1. **No blocking capacitor on the primary.** `[derived]` The DAC's differential DC offset is
   ±0.1 mV (datasheet), which across the 115 Ω winding is **±0.87 µA** — nothing against a 3.8 H
   core. There is no DC to block, so there is no cap, no X7R derating trap, and no capacitor whose
   failure mode passes 16 V.
2. **The differential-output problem is gone.** `HPOUTP` and `HPOUTN` both drive the winding, which
   is what a differential output wants. **This closes the §10.1 `[gap]`** about whether the HP amp
   is specified to run with one leg unloaded — the question no longer arises. It also recovers the
   6 dB that taking a single leg would have cost.
3. **The 16 V fault path is gone entirely.** A transformer has no failure mode short of insulation
   breakdown, and that is what the 2000 V rms rating covers. The BAT54S clamp becomes belt-and-braces
   rather than the thing standing between the bias and a dead codec.

`[derived]` **Level:** 1.0 V rms full scale − 2 dB insertion loss = 0.79 V rms open-circuit. Through
`R1` = 10 kΩ into a mic node of ~470 Ω (the bias resistor, mid-range):
`0.79 × 470 / (10000 + 115 + 470) =` **35 mV rms**. Sane against §2's 600 mV at 114 dB SPL, and the
DAC still runs near full scale, so the SNR is spent in the analog attenuator rather than in digital
gain.

### 11.3 CORRECTION to §3 and §10.2 — which ground the mutes shunt to

**§3 and §10.2 both say "GND". That is now wrong and it matters.** A transformer that isolates the
two grounds is worthless if a mute contact bonds them somewhere else on the board.

Every shunt on the aircraft side — §3's `R_MUTE` on the earphone lines, §10.2's mic-mute capacitor
and its 1 MΩ bleed — must return to the **headset/aircraft ground (the plug sleeve)**, never to
AeroNode `GND`. Treat them as a separate net; give it its own symbol and its own copper island, and
make the schematic show it as such. The most likely way this design fails is a well-meaning ground
symbol dropped on the wrong side of the boundary during layout.

**The good news is that the relays are already part of the barrier.** A relay's contacts are
galvanically isolated from its coil, so the coils are ours and the contacts are the aircraft's.
`[fetched]` The `G6K` is rated **1500 V AC between coil and contacts for 1 min**, insulation
resistance 1000 MΩ at 500 V DC, and the **`-Y`** suffix is specifically the wide-creepage variant —
3.2 mm coil-to-contact, 2.5 kV impulse to Telcordia. So `G6K-2F-**Y**` was the right call in §5, and
now it is the right call for a stated reason rather than by habit.

With the transformer carrying the only signal that crosses, and the relay coils the only control,
**nothing on the aircraft side is galvanically connected to AeroNode.** That is a clean boundary and
it is worth defending in review.

### 11.4 Honest limits — this part is not a flight part

Two things I am not going to let pass quietly:

1. **Operating temperature is −20 °C to +85 °C.** `[fetched]` A GA cockpit, cold-soaked or at
   altitude, goes below −20 °C. This is the specification that disqualifies it from a flight
   article, and it is easy to miss because everything else about the part fits.
2. **`UL60950` is an IT-equipment safety standard, not `DO-160`.** Bourns' own applications list is
   *"Modems (V32), Laptop Computers, Telecommunications, Instrumentation"*. This is a telecom part.

**So:** `SM-LP-5001` is the right part for the bench proof and for a proof-of-concept board, and the
topology it proves carries over unchanged. A flight article needs a transformer qualified to the
environment, and that is a sourcing exercise nobody has started. `[gap]`

3. `[gap]` **Confirm the pinout before layout.** The part has six pins (1,2,3 / 4,5,6) and the
   datasheet notes it is *"symmetrical, meaning there is no real primary nor secondary winding"* —
   which implies a centre tap per side, but the pin functions live in a schematic **graphic** that
   carries no extractable text. Render it and read it, the way the UG-2017 Figure 8 crop was read
   for `MIC_INPUT_P11.md`. Do not assume 2 and 5 are the taps.

---

## 12. DRAWN 2026-09-08 — the block is in the schematic

> **Superseded 2026-09-09 by §13.** The block was moved off the block-diagram page onto its own
> hierarchical sub-sheet, `audio-mute.kicad_sch`. The component list, values and verification
> method below all still stand; only the *location* and the layout changed.

Peter: *"draw the transformer and relay block into the audio interface schematic."* Done, in
**`~/aerosense/aeronode/aerosense/aeronode-lite/aeronode-audio-interface.kicad_sch`** — the canonical
tree, through Konnect MCP tools only. That sheet's `AUDIO` block was an empty placeholder with the
CM5-side connectors already labelled; the circuit now sits in the free page area to its right.

**That tree is not under git**, so before touching it: a timestamped `.bak-LIMA-<stamp>` was written
beside the file, and a byte copy went to `lima:kicad/aeronode-lite-audio/before/`. Rollback is one
`cp`, documented in that folder's README.

### What was drawn — 18 components

| Ref | Part | Role |
|---|---|---|
| `K1` | G6K-2F-Y | **SPKR mute.** Both poles: `COM`→`HS_L`/`HS_R`, `NC`→`AC_L`/`AC_R`, `NO`→`R1`/`R2`. |
| `K2` | G6K-2F-Y | **MIC mute.** Pole 1 is the §10.2 AC shunt; pole 2 no-connected as a spare. |
| `T1` | SM-LP-5001 | Primary across `HPOUTP`/`HPOUTN`, secondary → `R4` → `MIC_LINE`, other leg → `AC_GND`. |
| `Q1`,`Q2` | 2N7002 | Low-side coil drivers. |
| `R7`,`R8` | 100k | **Gate pulldowns — the fail-passive claim.** |
| `R5`,`R6` | 1k | Gate series. |
| `D1`,`D2` | 1N4148 | Coil flyback. |
| `R1`,`R2` | 0R | §3's `R_MUTE` links. DNP = series break instead of hard mute. |
| `C1`,`R3` | 100µF NP, 1M | §10.2 mic shunt + bleed. |
| `R4` | 10k | §11.1 secondary-side attenuator. |
| `J10`,`J11` | Conn_01x04 | Aircraft panel and headset. |

### Verified, not assumed

- **ERC: 41 errors before, 41 errors after, byte-identical list.** `[measured]` The block adds
  **zero** ERC errors and zero warnings. The 41 are pre-existing "label not connected" on the block
  diagram's own decorative labels. Running ERC on the untouched `before/` copy is the negative
  control; without it "41 errors" would have looked like my doing.
- **`validate_wire_connections`: 0 floating endpoints.** `[measured]`
- **The netlist says what the design says.** `[measured]` Exported and parsed:

```
5V_NODE       -> D1.1, D2.1, J2.8, K1.A1, K2.A1
GND           -> J1.1, J2.1, J3.1, Q1.S, Q2.S, R7.2, R8.2
GPIO_RLY_SPKR -> J4.2, R5.1          GPIO_RLY_MIC -> J4.1, R6.1
AC_L -> J10.1, K1.12                 AC_R  -> J10.2, K1.22
HS_L -> J11.1, K1.11                 HS_R  -> J11.2, K1.21
MUTE_L -> K1.14, R1.1                MUTE_R -> K1.24, R2.1
MIC_LINE  -> C1.1, J10.3, J11.3, R4.2
MIC_SHUNT -> C1.2, K2.11, R3.1
AC_GND    -> J10.4, J11.4, K2.14, R1.2, R2.2, R3.2, T1.3
HPOUTP -> T1.1   HPOUTN -> T1.2   T1_SEC -> R4.1, T1.4
```

  The line worth reading twice is **`GPIO_RLY_SPKR -> J4.2`**. The drivers landed on John's existing
  CM5-side connector by net name, and `5V_NODE` picked up `J2.8`, and `GND` picked up `J1.1/J2.1/J3.1`.
  **The block is wired into the sheet, not drawn beside it.**

### The pinout `[gap]` from §11.4 is CLOSED — and my caution was right

`[fetched]` The SM-LP-5001 schematic graphic, rendered at 900 dpi from Bourns' page 1 and read
(crop at `kicad/aeronode-lite-audio/doc/smlp5001-pinout.png`):

**Pins 2 and 5 are NO-CONNECT, not centre taps.** The windings are **1–3** (dot on 1) and **6–4**
(dot on 6). §11.4 said *"Do not assume 2 and 5 are the taps"* on the strength of the datasheet
calling the part symmetrical — that inference would have been wrong, and it is exactly the class of
error the ICM-45686 footprint scar is about.

### What is deliberately NOT right yet

1. **The symbols are generic.** `Relay:Relay_DPDT` numbers its pins EN50005 (11/12/14/21/22/24/A1/A2);
   the G6K's package pins are 1–8. `Device:Transformer_1P_1S` numbers 1–4; the SM-LP-5001's are
   1/3/4/6 with 2 and 5 unconnected. **No footprints are assigned, deliberately** — same decision as
   `kicad/imu-board/` U1. A sheet note on the drawing says so, so the mismatch cannot be inherited
   silently. **Author real symbols and footprints before any layout.**
2. **This sits on a block-diagram sheet.** The page is A4 and already carries the whole AeroNode
   block diagram, so the circuit occupies leftover space. It is legible — the labels were rotated
   vertical after the first render showed them colliding — but it would sit better on its own
   hierarchical sub-sheet, the way `cm5.kicad_sch` already is. That is a copy-paste when Peter wants
   it, not a redraw.
3. **`J10`/`J11` are generic 4-pin connectors.** Real GA hardware is a dual plug (PJ-055/PJ-068) or a
   6-pin panel connector. Placeholders until the mechanical interface is chosen.


---

## 13. MOVED 2026-09-09 — its own sheet, `audio-mute.kicad_sch`

Peter: *"can we please put this on its own schematic so no text overlays."* Done. §12's open item 2
is closed.

**`AUDIO MUTE + ISOLATION`** is now a hierarchical sub-sheet (`audio-mute.kicad_sch`, page 3),
matching the pattern `cm5.kicad_sch` already set in this project. The sheet symbol sits on the
parent at (115, 128), 55 x 45 mm.

**The parent was restored to its original bytes first** — `md5 052f149b996dfdf74993d68451ab7aa5`,
verified identical to the pre-edit backup — rather than unpicking ~45 labels by hand. Then only the
sheet symbol and its six pins were added. A second timestamped `.bak-LIMA-<stamp>` was taken before
that restore.

### The interface is six sheet pins

Written as hierarchical labels on the child and imported with KiCAD's own *Import Sheet Pins*:

| Pin | Crosses to |
|---|---|
| `GPIO_RLY_SPKR`, `GPIO_RLY_MIC` | the CM5-side connector `J4` on the parent |
| `5V_NODE` | `J2.8` |
| `GND` | `J1.1` / `J2.1` / `J3.1` |
| `HPOUTP`, `HPOUTN` | nothing yet — the codec is not placed. Deliberate. |

`validate_sheet_pins`: **0 issues.** `[measured]`

Everything aircraft-side (`AC_L`, `AC_R`, `HS_L`, `HS_R`, `MIC_LINE`, `MIC_SHUNT`, `AC_GND`,
`MUTE_L/R`, `T1_SEC`) stays **local to the sub-sheet** and does not leak into the parent's namespace —
which is the scoping you want, and a second reason the sub-sheet is the right home.

### Layout — why there are no overlays now

Full A4 to itself, and one change did most of the work: **`K1` and `K2` are rotated 90°**, so the
contacts face left and right at 2.54 mm pitch. Horizontal labels then stack like connector pin names
instead of colliding. On the old A4 the same labels had to be rotated vertical to fit at all.

### Verified — and one instrument caught lying

- **ERC: 41 errors, identical to the untouched baseline.** `[measured]` Zero added.
- **Netlist correct on both sides of the boundary** `[measured]`:

```
/5V_NODE       -> D1.1, D2.1, J2.8, K1.A1, K2.A1
/GND           -> J1.1, J2.1, J3.1, Q1.S, Q2.S, R7.2, R8.2
/GPIO_RLY_SPKR -> J4.2, R5.1        /GPIO_RLY_MIC -> J4.1, R6.1
~/RLY_SPKR_G   -> Q1.G, R5.2, R7.1  ~/RLY_MIC_G   -> Q2.G, R6.2, R8.1
~/AC_GND -> J10.4, J11.4, K2.14, R1.2, R2.2, R3.2, T1.3
~/MIC_LINE -> C1.1, J10.3, J11.3, R4.2    ~/MIC_SHUNT -> C1.2, K2.11, R3.1
```

**The instrument scar, and it is the §3 pattern exactly.** Konnect's `validate_wire_connections`
reported **`0 floating endpoints, valid: true`** on the child sheet. KiCAD's own ERC, run at the same
moment, reported **two wires connected to nothing** — and the netlist confirmed KiCAD was right:
`Q1.G`, `R5.2` and `R7.1` were on **no net at all**. The gate wires were drawn, looked correct in the
render, and passed the convenient check.

The fix was a net label on each gate node (`RLY_SPKR_G`, `RLY_MIC_G`); junction dots alone did not do
it. Two lessons worth keeping:

1. **`validate_wire_connections` is not a substitute for ERC.** It answers "does every wire end touch
   something", not "does every pin end up on a net". Believe the netlist.
2. **A rendered schematic that looks connected is not a connected schematic.** The only proof a node
   exists is its appearance in the netlist with all the pins you expect on it. `[measured]` beats
   `[looks right]`.

`[gap]` **KiCAD is running on this machine** (`pgrep kicad` returns a process). If Peter has this
project open in eeschema, he must reload it — and must not save from a stale in-memory copy, or
these edits are lost.

---

## 14. ADAU1860 analog in + out — 2026-09-09

Peter: *"add the adau1860 analog out and in connectivity."* Both directions now exist on
`audio-mute.kicad_sch`.

### Analog OUT — already there, now labelled as such

`HPOUTP`/`HPOUTN` → `T1` primary → secondary → `R4` (10k) → `MIC_LINE`. That is §11.2 unchanged.
A sheet caption now names it: *"ADAU1860 ANALOG OUT (differential HPOUTP/HPOUTN, 1.0 Vrms FS)"*.

### Analog IN — new, and it needed a second transformer

```
MIC_LINE ──[ R9 2k2 ]── MIC_TAP ──┤├── AINP2 / AINN2      (T2, SM-LP-5001)
                    T2 primary return → AC_GND
```

**Why `T2` and not a direct tap.** §11.3 claims *"T1 is the ONLY signal crossing"* the isolation
boundary. A capture path wired from the aircraft mic line straight to an ADAU1860 ADC input would be
a **second galvanic crossing** and would silently destroy that claim. So the capture gets its own
transformer. Two transformers, no galvanic path in either direction — the boundary survives, and
the design note that asserts it stays true.

**`R9` = 2k2 sets the tap impedance.** `[derived]` Against a ~470 Ω mic node, a bare 600 Ω primary
would load it by ~6 dB. Through 2k2 the load is (2k2+600) ∥ panel-Z, costing about **1.3 dB** of the
pilot's mic level to the radio. LF corner is `2200+600 / (2π·3.8 H)` ≈ **92 Hz**, below the
300 Hz–3 kHz comms band. Bigger R9 is gentler on the mic line but walks the corner up into the voice
band — the §11.1 trade-off, in the other direction.

**Level.** `[derived]` T2 sees `V_node × 600/(2200+600)` = 0.214 × V_node. Normal speech at the node
(~50 mV rms) arrives at roughly **8.5 mV**, which is −41 dBFS against the ADAU1860's 0.98 V rms
differential full scale — comfortable with the 0–24 dB PGA. §2's 600 mV at 114 dB SPL lands near
−20 dBFS, so **the PGA must not be run near maximum** or loud speech clips.

### Three things recorded on the sheet rather than buried

1. **CAVEAT — as drawn, muting the mic also deafens AeroNode.** `K2` shunts the *shared* `MIC_LINE`
   node (§10.2), and the capture taps that same node. So energising `GPIO_RLY_MIC` silences the
   pilot to the radio **and** to us. If the intent is *"the radio cannot hear the pilot but AeroNode
   can"* — which is what a push-to-talk-to-the-assistant feature needs — then `K2` must become a
   **series break** with this tap on the headset side, and that **reopens the DC-thump question that
   §10.2 closed**. This is a real fork and it is Peter's call; I have not taken it.
2. **`R4` injects TTS onto the same node the capture reads**, so AeroNode hears its own voice. That
   is not automatically a fault — it is a free echo reference for cancellation — but it must be
   known.
3. `[gap]` **The design assumes the ADAU1860's `AINx` pins self-bias.** `[fetched]` EVB Figure 8
   shows only 22 µF in series into `AINP2`/`AINN2` with no bias network, which implies they do. If
   they do not, two bias resistors from each `T2` secondary leg to `CM` (0.85 V) are needed. The
   abridged datasheet has no input-stage description, so this is not settled.

### Why the codec symbol is still not placed

Deliberate. `docs/h1-audio-board-codec-selection.md` §4 records that the ADAU1761-vs-ADAU1860 choice
is **John's**, not one to be taken here — *"if the part changes, it changes the bit map, and it has
to go to him"*. Placing an ADAU1860 symbol would quietly make that decision. The interface is
therefore expressed as sheet pins (`HPOUTP`, `HPOUTN`, `AINP2`, `AINN2`), which is what the block
needs to be correct either way.

### Verified

- **ERC: 41 errors — the untouched baseline.** `[measured]` Zero added.
- `validate_sheet_pins`: **0 issues** across 8 pins. `[measured]`
- **Netlist** `[measured]`: `~/MIC_TAP -> R9.2, T2.1` · `~/MIC_LINE -> C1.1, J10.3, J11.3, R4.2,
  R9.1` · `~/AC_GND` now includes `T2.2` · `/AINP2 -> T2.4` · `/AINN2 -> T2.3`.
- **The §13 wire scar repeated, exactly.** The new `R9`→`T2` wire produced one fresh
  *"Wires not connected to anything"* ERC error until a net label (`MIC_TAP`) was put on it — the
  same failure, same fix, second time. It is now a rule, not an anecdote: **a Konnect-drawn wire
  segment carrying no net label does not reliably form a net. Label every wire, then read the
  netlist.**

---

## 15. RULED 2026-09-09 — the headset mic does not go to AeroNode. §14's capture path is REMOVED.

Peter: *"the electret mic does not need to go to the aeronode we will use another analog mic via
i2s."*

**§14's analog-IN chain is deleted from the schematic**, not merely deprecated: `R9`, `T2`, the
`MIC_TAP` net, the `AINP2`/`AINN2` hierarchical labels, and the two matching sheet pins on the
parent are gone. `[measured]` The netlist confirms it — no `AIN*` net exists and `R9`/`T2` appear
nowhere. Both sheets were backed up first (`.bak-LIMA-20260909-111922`).

### What the block does now

The headset electret runs **headset → `MIC_LINE` → aircraft panel**, and `K2` mutes it. That is its
only destination. AeroNode's own audio input is a **separate analog mic into the codec, reaching the
CM5 over I2S** — a different part of the design, not this sheet. So the ADAU1860's analog **IN** is
simply not used by this block, and only the analog **OUT** (`HPOUTP`/`HPOUTN` → `T1`) crosses here.

**Three things this ruling cleans up, and they are all improvements:**

1. **Back to one crossing of the isolation boundary.** §11.3's claim — *"T1 is the ONLY signal
   crossing"* — is literally true again. §14 had to add a second transformer purely to keep it true.
2. **Open item 12 is closed, not carried.** §14 flagged that muting the mic would also deafen
   AeroNode's capture, and that fixing it would reopen the DC-thump question §10.2 settled. With no
   capture from this mic, the conflict does not exist. §10.2's AC-only shunt stands unchallenged.
3. **One less transformer, one less resistor**, and the aviation-mic overdrive arithmetic in §2/§14
   no longer applies to anything on this sheet.

### But it exposes a conflict that is still open, and it is more serious

Removing the capture leaves `MIC_LINE` carrying two things: the pilot's mic to the radio, and
**AeroNode's TTS, injected by `R4`** (§11.2). Trace where that TTS actually reaches the pilot:

```
HPOUT → T1 → R4 → MIC_LINE → aircraft panel mic input → intercom mixes it
      → intercom headphone out → AC_L / AC_R → K1 NC contact → HS_L / HS_R → pilot
```

**The TTS arrives through `K1`'s NC contact — the exact contact `K1` opens when it mutes.** So
energising `GPIO_RLY_SPKR` to "mute the headset while AeroNode speaks" cuts the only path AeroNode's
voice has. The pilot hears nothing at all. And `K2` compounds it: its shunt sits on `MIC_LINE`, so
muting the mic shorts the injected TTS too (`[derived]` ~100 µF against `R4`'s 10 kΩ is about
−66 dB at 300 Hz).

**As drawn, the two relays and the injection point cannot all be right.** The fix is the one John's
AERONODE block diagram drew before the mute-only ruling: make `K1` a **changeover** — `NO` contact to
AeroNode's audio rather than to `AC_GND` — so muting the intercom *substitutes* AeroNode's voice
instead of substituting silence. That is `R_MUTE` → `T1` secondary instead of `R_MUTE` → `AC_GND`,
a two-net change.

`[gap]` **Not taken.** Peter ruled mute-only on 2026-09-08, before the injection point was chosen;
this is new information rather than a reason to overturn him quietly. It is written on the sheet and
recorded here as the next thing needing a ruling.

---

## 16. RULED 2026-09-09 — K1 is a CHANGEOVER to AeroNode audio

Peter: *"yes make K1 a changeover to the aeronode audio."* §15's conflict is closed, and this
supersedes the mute-only half of the 2026-09-08 ruling for **K1 only** (`K2` stays a mute).

### The change — two nets

`R1.2` and `R2.2` moved from `AC_GND` to a new net **`AERONODE_AUDIO`**, which is the `T1` secondary
hot leg (`T1.4`). `R1`/`R2` are now commoned by a wire and labelled once.

```
K1 de-energised:  HS_L/HS_R  <-- AC_L/AC_R          pilot hears the radio
K1 energised:     HS_L/HS_R  <-- AERONODE_AUDIO     via R1/R2; intercom side OPEN
```

The return path completes through `AC_GND`: the earphone commons and `T1.3` are the same net, so
`T1.4 → R1 → K1 → HS_L → earphone → AC_GND → T1.3`. Muting the intercom now **substitutes AeroNode's
voice instead of substituting silence** — which is what John's AERONODE block diagram drew before
the mute-only ruling, and what §3's original *"fail-passive changeover"* label meant.

Fail-passive is unchanged and still holds: de-energised is still the metal contact that connects the
pilot to the radio.

`[measured]` Netlist: `~/AERONODE_AUDIO -> R1.2, R2.2, R4.1, T1.4` · `~/MUTE_L -> K1.14, R1.1` ·
`~/MUTE_R -> K1.24, R2.1` · `~/AC_GND` no longer carries `R1.2`/`R2.2`. ERC **41 errors — baseline**.

### Two consequences, both on the sheet

1. **`R4` is now redundant, and it is a transmit hazard. Recommend DNP.**
   With `K1` a changeover, AeroNode's voice reaches the pilot directly. `R4` still injects it into
   `MIC_LINE`, which goes to the **panel** — so it will trip the intercom's VOX, and it will be
   **transmitted over the air if PTT is pressed while AeroNode is speaking**. Left populated pending
   a ruling rather than removed, because "AeroNode audible on the radio" might be wanted (a
   position report, say). **DNP it unless it is.**
2. `[gap]` **Level needs ears, and the arithmetic says it may be quiet.**
   `[derived]` `T1` has **115 Ω DCR per winding**. Against 160 Ω of paralleled earphones that is a
   divider: `1.0 V rms × 160/(115+115+160)` = **0.41 V rms**, about **1.05 mW** into the pair. A GA
   intercom typically drives 1–2 V rms, so AeroNode may land 8–14 dB below a comfortable radio
   level in a noisy cockpit.
   **If it is too quiet the fix is a lower-DCR transformer or a gain stage after the codec — not
   more digital gain**, which only lifts the noise floor with the signal. This is the same class as
   the 2026-09-08 "audibility is Unknown" caveat: it cannot be settled from a desk.

`[gap]` Also unchanged: `R1`/`R2` at 0 Ω hard-parallel the two earphones onto one mono secondary.
Fine for speech; give them a small series value if channel isolation ever matters.

---

## 17. Does `K2`'s shunt also shunt the AeroNode audio? — checked 2026-09-09

Peter asked. **No — `−0.0036 dB`.** `[derived]` It was a fair question, and it *would* have been
yes before §16.

### Why it does not

The two live on different nets now. `[measured]` from the netlist:

```
~/AERONODE_AUDIO -> R1.2, R2.2, R4.1, T1.4     ~/MIC_LINE  -> C1.1, J10.3, J11.3, R4.2
~/MUTE_L -> K1.14, R1.1                        ~/MIC_SHUNT -> C1.2, K2.11, R3.1
~/MUTE_R -> K1.24, R2.1                        ~/AC_GND    -> ..., K2.14, ...
```

AeroNode's audio reaches the pilot **`T1.4 → R1/R2 → K1's NO contact → HS_L/HS_R`**. `K2`'s shunt
sits on `MIC_LINE`, which that path never touches. The only connection between the two nets is
**`R4`, 10 kΩ** — and 10 kΩ across a 160 Ω earphone load is nothing:

| | Load on `AERONODE_AUDIO` | Level at the earphones |
|---|---|---|
| `K2` de-energised (`R4` sees the ~470 Ω mic node) | 157.59 Ω | 0.4066 V rms |
| `K2` energised (`R4` sees ~AC ground through `C1`) | 157.48 Ω | 0.4064 V rms |

`[derived]` **−0.0036 dB**, and 16.5 µW goes down `R4` against 1.03 mW into the earphones.

**Before §16 the answer was yes, and badly so.** When AeroNode's voice travelled *via* `MIC_LINE`
(`R4` → panel → intercom → back to the earphones), `K2`'s shunt sat directly across it — `C1`'s
~5 Ω against `R4`'s 10 kΩ is about **−66 dB**. That was half of §15's conflict. Making `K1` a
changeover moved the audio off `MIC_LINE` entirely, so the shunt no longer has anything of ours to
short. **The question is worth keeping because it is the check that proves §16 actually fixed it.**

### The useful flip side — `K2` currently masks the `R4` hazard

Running the logic the other way: energising `K2` **shorts `R4`'s injection into the mic line**, by
that same −66 dB. So if software always energises `K2` while AeroNode speaks, §16's transmit hazard
never fires.

**Do not rely on that.** It is a software policy, not a property of the circuit — one missed GPIO and
AeroNode's voice is on the mic line with PTT live. **DNP on `R4` is still the robust fix**; this only
means the hazard is masked in normal operation, which is exactly the kind of thing that hides a
defect until the day the software gets it wrong.

---

## 18. RULED 2026-09-09 — `R4` is DNP

Peter: *"DNP R4."* Open item 15 closed. `R4` stays on the sheet so the footprint and the option
survive; it must not be fitted.

### What is marked, and the one thing that is not

| | State |
|---|---|
| Custom property `DNP` | **`yes`** `[measured]` |
| Custom property `Note` | the reason, on the symbol `[measured]` |
| Sheet text beside `R4` | **"R4 = DNP (do not populate)"** |
| Sheet note block | the full rationale |
| **KiCAD `(dnp …)` attribute** | **still `no`** `[measured]` |

**The last row is a real residual and I am not rounding it up.** Konnect's
`edit_schematic_component` / `batch_edit_schematic_components` set *properties*; neither exposes
KiCAD's `dnp` symbol **attribute**, and the Konnect operating rules forbid hand-editing a
`.kicad_sch` to reach it. So `(dnp no)` is unchanged, which means:

- eeschema will **not** draw `R4` with the DNP cross-out, and
- **a BOM or position-file export will still list `R4` as fitted.**

**One click closes it:** in eeschema, right-click `R4` → *Properties* → tick **"Do not populate"**.
Until that is ticked, this is exactly the failure mode §10 of `CLAUDE.md` names — *a control that is
written down, believed and cited, but not actually live*. Four kinds of marking on the drawing do
not stop a fab house populating a part the BOM says to populate.

`[gap]` **Ticked?** Not yet, as of this commit.

### Electrically

`[derived]` Unfitted, `R4` removes the only tie between `AERONODE_AUDIO` and `MIC_LINE`:

- **The transmit hazard is gone at the circuit level**, not merely masked by `K2`'s shunt (§17).
- `MIC_LINE` now carries the pilot's mic and nothing else.
- The load on `AERONODE_AUDIO` rises from 157.6 Ω to 160 Ω — **+0.08 dB** at the earphones. Nothing.

A cosmetic note for whoever edits next: the value was briefly set to `10k  DNP`, which overflowed the
resistor body and collided with the `AERONODE_AUDIO` and `MIC_LINE` labels. It is back to `10k`, with
the DNP marking as separate sheet text in clear space. **Render and look after any field edit** —
a longer Value string is a layout change.

---

## 19. Three analog mics on ADC0/1/2 — 2026-09-09

Peter: *"can we wire up another 3 analog mics to the adau1860 analog inputs one for boom mic voice
when electret is muted and the other 2 for the feedback feed forward anc."* Done, on a third
hierarchical sheet **`analog-mics.kicad_sch`** (page 4).

| Ch | Connector | Purpose | To |
|---|---|---|---|
| 0 | `J20` | **Boom voice** — hears the pilot when the headset electret is muted to the radio | `AINP0`/`AINN0` |
| 1 | `J21` | **ANC feedforward** — outside the earcup, senses ambient | `AINP1`/`AINN1` |
| 2 | `J22` | **ANC feedback** — inside the earcup, senses residual error at the ear | `AINP2`/`AINN2` |

### The channel budget is now full — exactly, with nothing spare

`[fetched]` The ADAU1860 has **three ADCs and one DAC** (datasheet: *"The three ADC channels and one
DAC channel have an SNR of approximately…"*, and the pin list carries `AINP0`, `AINP1`, `AINP2`).
Three mics uses **all three, zero spare.** Nothing else analog can ever be added without changing
part — which is exactly the trade `docs/h1-audio-board-codec-selection.md` §1 flagged when it
counted the ADAU1761's two channels against a mic plus an accelerometer.

### They are AeroNode's mics, so the isolation boundary is untouched

This is the part worth getting right. All three are **our** mics — biased from our rail, referenced
to our `GND`, wired to our connectors. They never touch `AC_GND`. So **no transformers are needed
here**, and §11.3's claim that `T1` is the only crossing of the isolation boundary still stands
literally. Had these been taps off the headset, each would have needed its own transformer.

### Front end, per channel

`Rn` (100 Ω) + `Cn` (1 µF) filter the module supply at the connector. `C2n`/`C3n` couple the
module's `OUT` and its **local ground** into `AINPn`/`AINNn` — pseudo-differential, so ground noise
picked up along the cable is rejected rather than summed in. `[fetched]` This mirrors the EVB, which
puts 22 µF in series with **both** legs and no bias network (UG-2017 Figure 8).

**Amplified modules, not bare capsules.** The ADAU1860 has **no `MICBIAS` pin** and its PGA is only
**0–24 dB** against a 0.49 V rms single-ended full scale. A bare electret's few mV × 16 lands about
−24 dBFS at best, and the rest would have to come from digital gain, which lifts the noise floor with
the signal. Modules must deliver a few hundred mV.

`[gap]` **`3V3_MIC` has no source yet, and that is deliberate.** ANC noise performance is set by the
mic supply, so it must be its own quiet rail rather than the CM5's 3V3. **ERC is 42, not the usual
41** — the extra one is `Label not connected: '3V3_MIC'` on the parent, which is ERC correctly
saying *this rail has no source*. Tying it to `3V3_CM5` to make the number pretty would be the wrong
trade.

### ANC — one architectural blocker, and a correction to myself

**Blocker: `K1` is a changeover, so the DAC only reaches the earcup while `K1` is energised.**
ANC anti-noise has to be permanently connected, continuously. As drawn, ANC would only work while
AeroNode is also muting the radio — which is not what anyone wants. Either `K1` sums instead of
switching (§3's `R_MUTE`-DNP variant plus a summing resistor), or the ANC output needs its own
always-on path to the earcup. **Needs a ruling; not taken.**

**Correction — `T1` is NOT a blocker, and I said it was.** I first wrote on the sheet that the
`SM-LP-5001`'s **200 Hz–4 kHz** specified band would cut ANC off below 200 Hz, where cockpit ANC is
most valuable. That was wrong, and I caught it before committing by doing the arithmetic instead of
reading the spec line as a hard limit. `[derived]` 200 Hz–4 kHz is Bourns' **600 Ω telecom**
condition. In *this* circuit — 160 Ω of paralleled earphones, driven from a low-impedance amp — the
Thevenin resistance across the 3.8 H magnetising inductance is 81.6 Ω, so the corner is:

```
f = 81.6 / (2π × 3.8 H) = 3.4 Hz        50 Hz: −0.020 dB    100 Hz: −0.005 dB
```

Essentially flat across the whole ANC band. **A spec band is the condition the vendor guaranteed,
not the physics of your circuit** — worth remembering, because reading it as a limit would have sent
someone shopping for a different transformer for no reason. `[gap]` LF *distortion* at real power is
still unmeasured, which is a separate question from response.

**Latency.** `[derived]` At 48 kHz the ADC → DSP → DAC loop is roughly 1 ms, far too slow for
feedforward ANC above a few hundred Hz. The ANC path must run through **FastDSP at a high rate** —
`[fetched]` the datasheet characterises it at **768 kHz** for exactly this class of application.

`[gap]` **Does the headset already have ANR?** A Bose A20 does its own. Two ANC systems fighting
over one earcup is worse than either alone. If the target headset is an off-the-shelf ANR set, this
whole path needs rethinking; if it is a passive headset or a custom earcup, it makes sense.

### Verified

- ERC **42** — the 41 baseline plus the one deliberate `3V3_MIC` error above. `[measured]`
- `validate_sheet_pins`: **0 issues** across all three sheets, 14 pins. `[measured]`
- Netlist `[measured]`: `/AINP0 -> C20.2` … `/AINN2 -> C32.2`, `/3V3_MIC -> R10.1, R11.1, R12.1`,
  and `/GND` now spans all three sheets — `C10.2, C11.2, C12.2, C30.1, C31.1, C32.1, J1.1, J2.1,
  J20.3, J21.3, J22.3, J3.1, Q1.S, Q2.S, R7.2, R8.2`.

---

## 20. RULED 2026-09-09 — ANC runs only while AeroNode is the active path. `K1` stays a changeover.

Peter, mid-change: *"cancel that anc is only active when aeronode is the active audio path."*
**Open item 17 is closed, not carried** — §19's "architectural blocker" was not a blocker at all,
it was the intended behaviour. `K1` keeps the §16 changeover and does **not** sum.

### The change was reverted byte-exactly

I had begun the summing edit and had removed three labels when the cancel arrived. A timestamped
backup taken immediately before the first deletion restored it: `[measured]` the live
`audio-mute.kicad_sch` now `cmp`s **identical** to the copy committed at `c485dde`, and
`git diff` on the mirrored file is **empty**. Netlist re-verified: `~/MUTE_L -> K1.14, R1.1` and
`~/MUTE_R -> K1.24, R2.1` are intact, so the changeover is exactly as it was.

**Backing up before starting, not after finishing, is what made the cancel cost nothing.** Two
minutes of `cp` beat any amount of careful un-picking.

### Summing was investigated. It is NOT a free swap — keep this, so nobody "improves" it later.

`[derived]` Two findings from the analysis done before the cancel, both worth keeping:

**1. The summing resistors could not have stayed 0 Ω — that would be a short across the panel.**
Under the changeover, `R1` and `R2` at 0 Ω tie `HS_L` and `HS_R` together, which is harmless
*because the intercom is open at the same instant*. Summing keeps the intercom connected, so those
same 0 Ω resistors would **short the panel's left and right outputs to each other**. Any move to
summing must give `R1`/`R2` a real value first. That is the kind of fault that survives a schematic
review because the part didn't change — only the switch behaviour around it did.

**2. How much of AeroNode survives summing depends entirely on the panel's output impedance**, which
is `[gap]` and varies by aircraft. AeroNode's level at the earphone, against `T1`'s ~230 Ω source:

| Panel Z_out | `R_sum` = 0 Ω | 330 Ω | 1 kΩ |
|---|---|---|---|
| 10 Ω | **−27.9 dB** | −35.4 dB | −42.1 dB |
| 100 Ω | −12.1 dB | −18.4 dB | −24.7 dB |
| 330 Ω | −7.7 dB | −13.0 dB | −18.7 dB |
| 600 Ω | −6.5 dB | −11.3 dB | −16.8 dB |

**You cannot passively sum into a node a low-impedance amplifier is already driving.** Against a
stiff 10 Ω panel output AeroNode lands ~28 dB down — useless for ANC, which needs to be comparable
to the noise at the ear. Making it work would mean either a series resistor in the *intercom* path
(costing radio level, on the safety-critical path) or series injection through a second transformer.

So the ruling is also the cheaper engineering: **ANC while AeroNode owns the earcup** avoids the
whole problem, because the intercom is open at exactly the moments ANC is running.

### What still stands from §19

`[gap]` `3V3_MIC` needs a quiet LDO (ERC 42 = 41 baseline + that one deliberate error) ·
`[gap]` ANC must run on FastDSP at a high rate, not 48 kHz · `[gap]` whether the target headset
already has its own ANR. `T1` remains a non-issue for bandwidth — 3.4 Hz corner in this circuit.

---

## 21. RULED 2026-09-09 — §20 retracted. `K1` sums; ANC is always on.

Peter: *"actually i'm taking rubbish forget my previous statement"*, clarified as **forget the
cancel — go back to summing**. §20's ruling is withdrawn; §19's open item 17 is closed by *doing*
the summing change rather than by declaring the blocker intended.

I asked which statement was being withdrawn rather than guessing: the two readings led to opposite
circuits, and picking wrong would have put a false ruling into the record as well as the wrong
copper.

### The change

| | Before (changeover) | Now (summing) |
|---|---|---|
| `R1`/`R2` | `K1.14`/`K1.24` → `AERONODE_AUDIO` | **`HS_L`/`HS_R` → `AERONODE_AUDIO`, permanent** |
| `K1` NO (14/24) | AeroNode feed | **unused, no-connected** |
| `K1` role | swap intercom ↔ AeroNode | **break the intercom only** |
| `R1`/`R2` value | 0 Ω | **220 Ω** |
| `MUTE_L`/`MUTE_R` | nets | gone |

```
K1 de-energised:  HS_L/HS_R  <-  AC_L/AC_R  +  AeroNode      summed
K1 energised:     intercom OPEN,  AeroNode alone
```

`[measured]` `~/HS_L -> J11.1, K1.11, R1.1` · `~/HS_R -> J11.2, K1.21, R2.1` ·
`~/AERONODE_AUDIO -> R1.2, R2.2, R4.1, T1.4` · `MUTE_*` gone · ERC **42** (41 baseline + the
deliberate `3V3_MIC`).

### `R1`/`R2` could not stay at 0 Ω — this is the part that would have bitten

`AERONODE_AUDIO` ties the two channels together, so **0 Ω summing resistors short the panel's left
and right outputs to each other.** Under the changeover that was harmless, because the intercom was
open at the same instant the two were commoned. Summing keeps the intercom connected, so the same
part value becomes a fault. **The value had to change because the switch behaviour around it
changed, not because the part did** — exactly the sort of thing a parts-focused review misses.

`[derived]` 220 Ω chosen: it gives a **440 Ω** left-to-right path (safe against a stereo panel) and
costs only **1.4 dB** of AeroNode level versus 100 Ω.

| `R_sum` | AeroNode, intercom live (Z_out = 10 Ω) | AeroNode active (K1 open) | L–R path |
|---|---|---|---|
| 0 Ω | −27.9 dB | −4.7 dB | **0 Ω — short** |
| 100 Ω | −30.9 dB | −6.2 dB | 200 Ω |
| **220 Ω** | **−33.5 dB** | **−7.6 dB** | **440 Ω** |
| 470 Ω | −37.3 dB | −10.1 dB | 940 Ω |

### The honest limit — ANC *authority*, not connectivity

The DAC now always reaches the earcup, so ANC is connected continuously. But **a passive sum cannot
fight a low-impedance source.** While the intercom is live, AeroNode sits about **−33 dB** at the
earphone; the moment `K1` opens the intercom it jumps to **−7.6 dB**, because the panel that was
swamping it is disconnected. That ~26 dB step is automatic and free — but it means **ANC authority
in normal flight is set by the panel's headphone output impedance, which is `[gap]` unmeasured.**

- A stiff panel (10 Ω) → ANC is ~33 dB down and will not do useful work.
- A soft one (330–600 Ω) → ANC lands −13 dB, which is arguable.

**Measure it before trusting ANC in the summed configuration.** If the panel turns out stiff, ANC
needs its own path to the transducer rather than sharing the intercom line — which is a bigger
change than any resistor value, and worth knowing early. `[gap]` also unchanged: is the target
headset already an ANR set?
