# What UG-807 actually says — read 2026-09-17

Peter supplied the PDF; earlier sessions could not fetch it (analog.com times out from here, mirrors
403). Everything below is `[fetched]` from *EVAL-ADAU1372Z User Guide UG-807 Rev. 0*, Figure 34
(schematic, page 14), Table 1 (connectors) and the Inputs and Outputs section.

## The power jumpers — read this first

> "To connect power to the ADAU1372, connect the **J8, J10, J12, and J17** jumpers."

| jumper | what it connects |
|---|---|
| **J8** | IOVDD on the ADAU1372 <- the board's power supply section |
| **J10** | IOVDD <- VDD (3.3 V board supply) |
| **J12** | DVDD <- the codec's internal regulator |
| **J17** | **AVDD <- VDD (3.3 V board supply)** — the analog supply |
| J15 | **power down** — fitting it powers down all analog and digital circuits (Peter confirmed it is clear) |

**All four must be fitted.** `J17` is the one that matters for the ADC hunt: with it off, the analog
supply is absent while every digital function still works — which is the exact signature of this
fault. Against that: the DAC output was audible, and the headphone drivers run from AVDD too, so
AVDD is probably present. Worth confirming by eye rather than by inference.

Board power itself: a single AAA battery, the USB bus, or 3.8-6 V into `J2`, selected by `J3`.
`D1` lights when the board is powered.

## Connectors

| ref | what it is |
|---|---|
| J1 | control port header — mates with the USBi |
| J4 | **serial audio header** — LRCLK, BCLK, SDATA, plus MCLK in/out pins |
| **J18** | **Analog Input 0** |
| **J20** | **Analog Input 1** |
| **J22** | stereo line input jack (TRS, tip = left, ring = right) -> analog inputs 2 and 3 |
| **J23** | **headphone output** (TRS mini-jack) |
| J11 | adds MICBIAS0 to AIN0 |
| J14 | adds MICBIAS1 or MICBIAS0 to AIN1 (A/B positions) |
| J13, J16 | access to the mono differential right/left outputs |
| J6, J7 | PDM digital microphone headers |

## The analog input circuit — and a correction to CONFIG-PLAN

Traced from Figure 34 for Analog Input 0 (Input 1 is identical with R48/R47/C8):

```
J18 pin 1 (signal) ──── R42 (0 ohm) ──── AIN0        R41 49k9 from that node to ground
J18 pin 2           ──── ground
MICBIAS0 ── R44 2k00 ── J11 ── to the AIN0 node      C34 2.2uF from MICBIAS0 to ground
C1 47uF: AIN0REF ──── ground
```

> ## ⚠ CORRECTION 2026-09-18 — the signal IS AC-coupled. I read this wrong.
>
> Re-traced from a 6x render of Figure 34 (`scratchpad/j18.png`), because JULIETT's question turned
> on it. The path is:
>
> ```
> J18 tip  -> R42 0R00 -> node (R41 49k9 to GND, C33 OPEN) -> C2 47.0uF -> AIN0   (pin 9)
> J18 ring -> tied to GROUND            -> C1 47.0uF -> AIN0REF (pin 8)
> ```
>
> **C2 47 uF is a series coupling capacitor in the AIN0 signal path.** The schematic note says it
> outright — *"49k9 resistors on inputs reference AC coupling capacitors to ground"* — the 49k9
> references **C2**, the coupling cap. Analog Input 1 is identical (R48 / R47 / C38 / **C10 47 uF**
> in series to AIN1, and **C8 47 uF** from the grounded ring to AIN1REF).
>
> **What I got wrong and what it costs:** I reported the inputs as DC-coupled and told CONFIG-PLAN
> the low-frequency corner "does not exist". It does. `[derived]` 47 uF into ~20 kOhm is **0.17 Hz**,
> so it changes nothing for AC vibration above 20 Hz — but the *statement* that the AIN pins are
> DC-coupled to the source was false, and the argument built on it (that a DC-sinking source would
> fight the internal bias through its own output impedance) does not apply: the cap blocks it.
> **A source's DC offset cannot reach the AIN pin on this board.** Anything wanting DC or tilt from
> the accelerometer must bypass or replace C2/C10.

**The original (wrong) reading, kept for the record:** "The signal is DC-coupled to the AIN0 pin
through a 0 ohm resistor. There is no series coupling capacitor in the signal path." The 47 uF cap
does also sit on **AIN0REF**, as the datasheet pin description asks ("ac couple this reference pin
to ground"), and the 49k9 is a bleed to ground —
the schematic note says it exists only to "reference AC coupling capacitors to ground preventing
pops when hot-plugging inputs. **Not necessary for hardwired design.**"

`[correction]` CONFIG-PLAN §3.3 said the real low-frequency corner would be set by the EVB's series
coupling capacitor against the codec's input impedance, and listed the cap value as an unknown to
measure. **There is no series capacitor** — so that corner does not exist, and the low-frequency
limit is set by the codec's own high-pass (Off / 1 / 4 / 8 Hz) plus whatever the source brings.
For the accelerometer channels that is better news than the plan assumed.

`[note]` It also means the AIN pins are DC-coupled to whatever is plugged in, with only a 49k9
bleed. The codec biases its inputs at AVDD/2 internally, so a source that sinks or sources DC will
fight that bias through its own output impedance — another argument for the buffer the plan already
recommends on the accelerometer outputs.

## Master clock — confirmed independently

> "The master clock can be provided externally or by the on-board **12.288 MHz** passive crystal."

This matches the frame-rate measurement (480000 frames in 10.029 s = 47,862 Hz against a nominal
48000) and confirms the overlay's `clock-frequency = <12288000>` was right. `R3` (100 ohm) feeds the
crystal to MCLK; `R2` is **OPEN** from the factory and must be fitted to bring MCLK out on `J4`, and
`R3` must be removed to drive MCLK in externally.

## Still open after reading it

- `[gap]` Nothing in UG-807 explains an ADC that emits mathematically exact zeros while the DAC,
  control port, clock generation and serial port all work.
- `[gap]` The staged talkthrough probe (DAC-mute clicks, gain sweep, PGA-enable clicks) has not been
  reported on yet. Whether **stage 1** was audible decides whether the talkthrough result means
  anything at all: no clicks means my hand-built configuration never reached the output and the
  silence measured nothing.


---

## 2026-09-18 — where every AINxREF actually goes (answers JULIETT 2026-09-10-005)

Traced from 6x renders of Figure 34. **All four reference pins are AC-coupled to GROUND. Not one of
them is driven by a signal conductor.**

| pin | net | how it is terminated |
|---|---|---|
| 8 `AIN0REF` | — | J18 **ring, tied to ground** -> C1 47 uF |
| 13 `AIN1REF` | — | J20 **ring, tied to ground** -> C8 47 uF |
| 15 `AIN2REF` | `AIN2P` | J22 **sleeve (ground)** -> C16 10 uF |
| 17 `AIN3REF` | `AIN3P` | J22 **sleeve (ground)** -> C18 10 uF |

The `AIN2P` / `AIN3P` net names look like signal nets and are not — they are the CAD names for the
grounded-through-a-capacitor reference nets off the J22 sleeve. That is the trap in this figure.

**J22 carries two channels, not a signal and a reference.** UG-807 says so in words: *"The stereo
input jack, J22, accepts a standard stereo TRS 1/8 inch mini-plug (**tip is left, ring is right**)
with two channels of audio."* Tip -> AIN2 (via R53/C17), ring -> AIN3 (via R54/C19), sleeve -> both
reference pins via C16/C18.

`[gap]` This establishes what the **board** does, not what the **silicon** permits. Whether
`AINxREF` can be driven with an inverting leg is a question about the ADC input stage, and the
ADAU1372 datasheet could not be fetched (analog.com serves a download dialog to the browser and
times out to curl; no mirror found).
