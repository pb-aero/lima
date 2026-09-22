# The sensor head — ADXL354 into the ADAU1861

**Date:** 2026-09-22 · **Agent:** LIMA · **Status:** design note. **Nothing measured on hardware.**
**Scope:** the three accelerometer channels on the audio board — buffering, coupling, values, and the
sign convention. The PDM mic needs none of this (§8). The codec choice is
`docs/audio-board-decision-record.md`; the phase budget is `docs/dvnc-phase-budget.md`.

Provenance: `[fetched]` = read from the vendor PDF, page cited · `[derived]` = arithmetic shown ·
`[repo]` = in this repository · `[measured]` = run on hardware · `[gap]` / `[assumed]` = **not
established, do not build on it without checking**.

---

## 1. The chain

```
ADXL354 XOUT/YOUT/ZOUT            per axis, x3
  0.9 V DC offset, 32 kΩ source   [fetched]
        │
        ├── C_couple  100 nF C0G ±5%          ← DC block AND the high-pass corner
        │
        ├── R_bias    1 MΩ 1% metal film ──► 0.85 V reference (§6)
        │
        └── op-amp, non-inverting unity gain, FET/CMOS input
                │
                └──► AINN0 / AINN1 / AINN2    with AINP0/1/2 tied to CM
                     ADAU1861 in single-ended mode, AINx_INPUT_MODE = 1   [fetched]
```

One quad op-amp serves the head: **three buffers plus one spare**, and §6 spends the spare.

## 2. Set the accelerometer to ±8 g, not ±2 g

`[derived]` The ADAU1861's single-ended full scale is `[repo]` **0.49 V rms = 0.69 V peak**.

| Range | Sensitivity | Codec clips at |
|---|---|---|
| ±2 g | 400 mV/g | **1.73 g** — below the 4.4 g flight peak `[repo]`. Unusable |
| **±8 g** | **100 mV/g** | **6.93 g** — 3.9 dB of margin |

`[repo]` JULIETT already specified ±8 g for the eval board. **It has to carry into the product**, and
it is a strap, so it is easy to get wrong silently.

## 3. Why the buffer is not optional in the product

`[fetched]` The ADXL354 drives through a fixed on-chip **32 kΩ** series resistor. `[fetched]` The
ADAU1861's single-ended input resistance is **9 kΩ** without the PGA, **1.2–41.2 kΩ** with it, and
*"the resistors inside the ADAU186x vary by as much as ±20%."*

`[derived]` At ±8 g with a 4.4 g flight peak (0.311 V rms):

| | Divider | Level | From FS |
|---|---|---|---|
| Direct into 9 kΩ | 0.220 | 0.068 V rms | **−17.1 dB** |
| Direct into 41.2 kΩ (PGA high-Rin) | 0.563 | 0.175 V rms | −8.9 dB |
| **Buffered** | 1.000 | 0.311 V rms | **−3.9 dB** |

Three reasons the buffer earns its place, in order of importance:

1. **PGA gain *is* the input resistance.** Turning gain up to recover the 13.2 dB changes the divider
   **and** the coupling corner at the same time. Two things moving while you tune a third.
2. **±20% tolerance is a `[derived]` 2.76 dB level spread** board-to-board, and an *unmatched* spread
   between X, Y and Z on the same board. Inter-axis matching is the whole point of a three-axis
   reference.
3. **Level.** Buffered, the signal lands 3.9 dB below full scale with **no PGA gain at all**.

`[repo]` For **first light on the bench, direct is fine** — JULIETT's *"can go direct, no buffers,
expect roughly 10–12 dB lower level"*. `[derived]` The number is 13.2 dB. This note is about the
product.

## 4. Coupling: 100 nF C0G into 1 MΩ

`[derived]` fc = 1.59 Hz → **+1.82° at 50 Hz**, +0.30° at 300 Hz. AC loss from the 32 kΩ source into
1 MΩ is **−0.27 dB**. DC across the cap is ~50 mV (0.9 V against the 0.85 V reference), so the voltage
rating is a formality — 16 V or 25 V keeps it in 0805.

**C0G/NP0 is not a preference here, it is a requirement.**

1. **Class II ceramics are piezoelectric.** This is the *vibration reference* channel. An X5R or X7R
   in this position is a second, uncalibrated accelerometer in series with the real one, excited by the
   same 50–300 Hz airframe energy, producing signal indistinguishable from the measurement. It is the
   single worst place on the board for a microphonic part.
2. **No DC-bias derating**, so the corner does not move with operating point.
3. **Tempco 0 ± 30 ppm/°C** — across the 1861's −40 to +105 °C that is ~±0.4% on capacitance. X7R can
   move 15% over the same span, taking the corner and the phase with it.

`[derived]` Channel-to-channel spread with ±5% C0G and 1% resistors: **0.22°** across the three axes.

**Do not put the coupling cap at the codec pin.** There the corner would be set by the internal
9 kΩ ±20% that changes with PGA gain (§3). Putting it at the buffer input makes the corner a function
of two parts we choose.

**Do not oversize it either.** `[repo]` `docs/dvnc-phase-budget.md` §4.1: chasing a smaller corner, or
trying to match the mic's roll-off with a different value, buys a few dB at one frequency and nothing
across the band. The correction belongs in the FastDSP.

## 5. The op-amp — two hard requirements

1. **FET or CMOS input.** `[derived]` 1 MΩ × input bias current becomes DC offset: 100 nA (bipolar)
   gives 100 mV, 1 pA (FET) gives 1 µV.
2. **Voltage noise ≤ ~10 nV/√Hz.** `[derived]` The source already contributes
   **22.7 nV/√Hz** from its own 32 kΩ — and with the bias resistor shunted by that source
   (32 k ‖ 1 M = 31 kΩ) the network adds essentially nothing beyond it. An amplifier much noisier than
   10 nV/√Hz would start to dominate a floor the accelerometer sets at `[repo]` 8 nV/√Hz referred.

> **A note on topology: do not make these buffers inverting.** `[derived]` An inverting stage needs a
> series input resistor; to avoid loading the 32 kΩ source it must be ~1 MΩ, whose Johnson noise is
> **127 nV/√Hz — 15.9× the accelerometer's own**, about 15 dB thrown away on the reference channel.
> Any sign inversion belongs in the DSP (§7), where it is free.

## 6. The 0.85 V reference — spend the spare op-amp on it

The buffers' non-inverting inputs need a clean 0.85 V, matching the codec's CM so the buffer output can
sit at the same DC level as the input it drives.

`[fetched]` The `CM` pin is **0.85 V with a 5 kΩ source impedance** and wants a 1 µF decoupling cap.
`[gap]` The ADAU1787's datasheet warns the equivalent reference holds only *"as long as these circuits
are not drawing current"* — and here three bias resistors plus three op-amp inputs would hang off it.

**Use the quad's fourth amplifier to buffer CM**, and distribute the buffered copy to all three
channels. It costs nothing — the part is already there — and it removes a shared-impedance coupling
path between the three axes, which is exactly the kind of thing that turns into inter-axis crosstalk.

## 7. Sign convention

`[fetched]` UG-2257 Table 7: **Analog In → ADC → Digital Output (Serial Port) = 180°.** The ADC
inverts; *"there is no phase inversion in the digital blocks."*

So the accelerometer arrives at the host **inverted**, while `[fetched]` the PDM mic — which never
touches an ADC — does not, and `[fetched]` both Infineon mics are non-inverting at the transducer
(*"Increasing Vout / Increasing SPL"*, *"positive pressure increases density of 1's"*).

**Correct it with a gain of −1 in the FastDSP**, not in hardware. It is free, exact, adds no noise and
no tolerance, and — the real argument — **it is cheap to be wrong.** If the bench says the sign is
backwards, a coefficient is a one-line change; three inverting buffers are a rework.

> `[repo]` **This must be proven, not derived.** The scar is that *parity is not correctness*. A sign
> error turns cancellation into reinforcement — **+6 dB instead of −13 dB** — and presents as "ANC
> doesn't work", not as "the sign is wrong". Put a known stimulus in and confirm the anti-tone
> subtracts.

## 8. What the PDM mic needs from this note: nothing

`[fetched]` The IM72D128V is a digital part on its own `DMIC_CLK` — no coupling, no buffer, no analog
routing, and `[repo]` on the ADAU186x family the DMICs route independently of the ADCs with no pairing
mode. It takes the codec's **1.8 V** rail (`[fetched]` supply range 1.62–3.6 V) — **not 3.3 V**;
`[repo]` that correction is already on JULIETT's `2026-09-17-004`.

## 9. Layout

- **Keep the accelerometer leads short.** `[derived]` Stray capacitance on the 32 kΩ output is a
  low-pass: **100 pF costs −0.35° at 300 Hz, 1 nF costs −3.45°.** Under a few hundred pF is
  negligible; a metre of unscreened cable is not.
- **Match the three channels physically** — same routing, same part lot, same thermal environment.
  Inter-axis phase matching is worth more here than absolute accuracy.
- `[repo]` **`3V3_MIC` stays its own quiet rail.** Mic supply noise sets ANC noise performance; do not
  fold it into the codec rail to save a regulator. The ADXL354 has its own supply requirement again
  (`[fetched]` 2.25–3.6 V) separate from the codec's 1.8 V.

## 10. Open — check these before layout

1. `[gap]` **Can the buffer output DC-couple into `AINNx`?** The HRM says *"ac-couple the pins to
   ground"*, which reads as ADI expecting a series cap at the pin. If the buffer sits exactly at CM
   there is no DC across the internal bias, so it should be fine — but that is my reasoning, not their
   statement. **Footprint a series cap with a 0 Ω alternative** so the board supports both. It costs
   nothing and it is the difference between a jumper change and a respin.
2. `[gap]` **CM pin loading** — §6, even with the buffer.
3. `[assumed]` **The ADXL354's ±8 g sensitivity and 0.9 V offset** are `[repo]` repo figures; confirm
   against the datasheet now that it is pinned in `scripts/fetch-datasheets.sh`.
4. `[gap]` **The 148 µs group delay** `docs/dvnc-phase-budget.md` derives for the ADXL354 is from the
   stated sinc shape, not a vendor number — ADI publishes no phase or group delay for the analog path.
   Measure it with the codec's ADC↔DMIC skew in one experiment; the two sit in series in this channel.
5. `[repo]` **P11's ~64 dB shortfall** — `docs/two-adau1860-channel-allocation.md` now argues it is an
   open `P13`/`P15` jumper rather than a defective ADC2, which would unblock the Z axis. **EVB
   topology either way**, but the ninety-second tone test should be run before three axes are
   committed to a layout.

## Sources

- **ADXL354/ADXL355 datasheet Rev. D** — FILTER p.25 (sinc, 1.5 kHz antialias, 1.9 kHz overall),
  32 kΩ output resistor, supply range.
- **ADAU186x HRM UG-2257 Rev. 0** — p.18 (input resistance, single-ended mode, ±20% tolerance,
  precharge), Table 7 (phase inversion).
- **ADAU1861 datasheet** — `CM` pin 25, absolute maximums.
- **IM72D128V datasheet v01.00** — supply range, polarity.
- `[repo]` `docs/dvnc-phase-budget.md`, `docs/audio-board-decision-record.md`,
  `docs/two-adau1860-channel-allocation.md`, `linux/adau1860-pi5/MIC_INPUT_P11.md`.

All datasheets restore or verify via `scripts/fetch-datasheets.sh`.
