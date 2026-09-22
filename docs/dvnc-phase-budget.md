# The DVNC phase budget — accelerometer reference against the IM72D128V PDM mic

**Date:** 2026-09-22 · **Agent:** LIMA · **Status:** derived. Nothing measured on hardware.
**Trigger:** Peter asked what the phase budget is with the IM72D128V. It can now be assembled, because
Infineon specifies the mic's phase response directly.

Provenance: `[fetched]` = read off the vendor PDF, page cited · `[graph]` = **read off a figure, ±2–3°**
· `[derived]` = arithmetic shown · `[assumed]` = **not established, flagged** · `[repo]` = in this
repository.

---

## 1. The answer in one line

**Uncorrected, this does not work at any coupling-capacitor value.** The best single capacitor still
leaves a worst-case **13.3° mismatch** across 50–300 Hz, a **−12.7 dB** cancellation floor. **Phase
calibration is mandatory, not optional** — which is exactly what `[repo]` the parts note already
concluded for the IM73A135, for the same reason.

## 2. The mic, specified

`[fetched]` IM72D128V datasheet v01.00, Table 2, Acoustic specifications. Test conditions are
**VDD = 1.8 V, fCLK = 3.072 MHz, OSR = 64** — exactly our operating point, so these are not
extrapolated.

| Parameter | Value |
|---|---|
| **Phase response** | **+11° at 75 Hz**, −0.3° at 1 kHz, −4° at 4 kHz |
| **Group delay** | **60 µs at 250 Hz**, 10 µs at 600 Hz, 6 µs at 1 kHz, 3.5 µs at 4 kHz |
| Low-frequency roll-off | **11 Hz** (−3 dB rel. 1 kHz) |
| Sensitivity | −36 dBFS at 1 kHz, 94 dBSPL |
| SNR | 71.5 dB(A) at fCLK = 3.072 MHz |
| AOP | 128 dBSPL (10% THD) |
| **Polarity** | **"Positive pressure increases density of 1's, negative pressure decreases density of 1's in data output"** |

> **The polarity line closes one of the four sign terms** flagged in the level-shifter work: the mic is
> **non-inverting**. Remaining: the codec's 180° analog-path inversion `[fetched]`, the DMIC path's 0°
> `[derived]`, and the accelerometer's axis sign versus physical direction.

`[graph]` Figure 4, typical phase response, read across our band: **≈ +37° at 20 Hz, ≈ +20° at 50 Hz,
+11° at 75 Hz, ≈ +8° at 150 Hz, ≈ +5° at 300 Hz**, crossing zero around 1 kHz. The 75 Hz, 1 kHz and
4 kHz points are specified; the rest are graph readings and carry ±2–3°.

**Consistency check:** a single-pole 11 Hz high-pass alone would give +8.3° at 75 Hz against the
specified +11°, so the roll-off is steeper than one pole. That matters in §4.

## 3. The reference path

| Term | 50 Hz | 75 Hz | 150 Hz | 300 Hz |
|---|---|---|---|---|
| ADXL354 internal LPF `[assumed]` single-pole 1500 Hz | −1.91° | −2.86° | −5.71° | −11.31° |
| 100 nF C0G into 1 MΩ (fc 1.59 Hz) `[derived]` | +1.82° | +1.21° | +0.61° | +0.30° |
| **net** | **−0.09°** | **−1.65°** | **−5.10°** | **−11.01°** |

> `[assumed]` **The ADXL354 filter shape is load-bearing and unverified.** `[repo]` The note says "LPF
> fixed 1500 Hz"; I have modelled it as a single pole. `[repo]` JULIETT also specified **C1–C3 removed**
> on the eval board — if the 1500 Hz figure assumes those fitted, every number in that row moves.
> **Check the ADXL354 datasheet before this table is used for anything.**

## 4. No single capacitor tracks the mic

The tempting move is to give the reference path the mic's own 11 Hz roll-off so the phase error becomes
common-mode. `[derived]` It does not survive the band:

| Coupling | 50 Hz | 75 Hz | 150 Hz | 300 Hz | worst | floor |
|---|---|---|---|---|---|---|
| 100 nF (fc 1.59 Hz) | +20.1° | +12.7° | +13.1° | +16.0° | 20.1° | −9.1 dB |
| 15 nF (fc 10.6 Hz) | +9.9° | +5.8° | +9.7° | +14.3° | 14.3° | −12.1 dB |
| 10 nF (fc 15.9 Hz) | +4.3° | +1.9° | +7.7° | +13.3° | **13.3°** | **−12.7 dB** |

**Why it cannot work:** `[derived]` to match the mic at 50 Hz a single pole needs **fc = 18.2 Hz**; to
match it at 300 Hz it needs **fc = 26.2 Hz**. One pole cannot be in two places, because the mic's
roll-off is steeper than first order (§2).

**A single frequency is misleading here.** At 75 Hz alone, 10 nF gives a 1.9° mismatch and a −29.7 dB
floor, which looks like a 16 dB win over 100 nF. **Across the band it is worth 3.6 dB.** Optimising a
broadband quantity at one frequency is how you get a number that is true and useless.

## 5. What follows for the design

1. **Calibrate.** Both curves are specified and smooth, with tight manufacturing tolerance `[repo]`
   (±1 dB on the IM73A135). A fixed phase correction in the FastDSP closes this properly and is the
   only thing that gets past −13 dB. It is also already mandatory for the analog mics, so the mechanism
   will exist.
2. **Given calibration exists, choose the capacitor to be small, stable and predictable rather than to
   chase a partial match** — so the low corner, **100 nF C0G into 1 MΩ**, whose own contribution is
   ≤1.8° across the band and barely moves with temperature or tolerance. Chasing 10 nF buys 3.6 dB
   uncorrected and complicates the correction.
3. **Keep the leads short** — `[derived]` 100 pF of stray capacitance on the ADXL354's 32 kΩ output
   costs −0.35° at 300 Hz; 1 nF costs −3.45°.

## 6. What a residual mismatch costs

`[derived]` best achievable cancellation for a residual phase error θ, from 2·sin(θ/2):

| θ | floor | | θ | floor |
|---|---|---|---|---|
| 1° | −35.2 dB | | 10° | −15.2 dB |
| 2° | −29.1 dB | | 12° | −13.6 dB |
| 5° | −21.2 dB | | 20° | −9.2 dB |

## 7. Still open

- `[assumed]` **ADXL354 filter shape and corner** — §3. The largest unverified term.
- `[gap]` **ADC ↔ DMIC relative group delay inside the codec.** `docs/accel-vs-pdm-mic-skew.md`
  establishes ADI publishes neither path and five registers move it. **Measurement, on the shipping
  configuration.** This budget assumes it is zero, which it is not.
- `[gap]` **Whether common-mode phase between reference and error actually helps** depends on the
  control topology, which is John's. The arithmetic here is about matching, not about the algorithm.
- `[graph]` The 50 / 150 / 300 Hz mic figures are read off a curve. If this budget starts driving
  decisions, get the tabulated curve from Infineon or measure it.

## Sources

- **IM72D128V datasheet v01.00** (19 pp, Infineon, 2025-05-04) — Table 2 Acoustic specifications p.5,
  Figure 4 typical phase response p.4, Figure 5 typical group delay p.4. Pinned in
  `scripts/fetch-datasheets.sh`.
- `[repo]` `docs/accel-vs-pdm-mic-skew.md`, `docs/audio-board-level-shifter.md`,
  `docs/two-adau1860-channel-allocation.md`, `.agent/status.md` (ADXL354 and IM73A135 parts notes).
