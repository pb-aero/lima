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

### The transformer is the better answer for the aircraft

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
