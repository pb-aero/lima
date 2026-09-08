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

1. `[gap]` **The mic-node DC operating point** (§4). Three meter readings close it. Everything about
   the mic mute's shunt value waits on them.
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
