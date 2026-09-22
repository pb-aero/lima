# Relative phase between the analog accelerometer and the PDM mic on one ADAU1860

**Date:** 2026-09-22 · **Agent:** LIMA · **Status:** analysis. Nothing measured on hardware.
**Trigger:** Peter, on the level-shifter phase question — *"I'm thinking more the phase lag between
accelerometer and pdm mic."*

Provenance: `[fetched]` = read from the vendor PDF this session, page cited · `[measured]` = run on
hardware · `[derived]` = arithmetic shown · `[repo]` = in this repository · `[gap]` = not
established, do not assume.

---

## 1. First, the level shifter drops out of this question entirely

**A translator contributes exactly zero relative phase between two channels that share it.** The
accelerometer and the PDM mic arrive on **the same serial port, under the same BCLK and FSYNC, on the
same stereo lanes, through the same translator package.** Whatever delay it adds is **common-mode**
and cancels in the difference.

`docs/rig-logic-levels.md` §8 answered the absolute-delay question and is correct as far as it goes.
**It is the wrong budget for this question** — and the right answer to *this* one is that the level
shifter is not a term in it at all.

## 2. But a relative skew exists by construction, and here is the sentence that proves it

`[fetched]` **UG-2257 Rev. 0, p.20, Digital Microphone Inputs:**

> *"The digital microphone signals and the ADCs are **completely independent and do not share
> decimation filters**."*

That is the whole mechanism. Two different front ends, two different filters:

| | Analog accelerometer channel | PDM mic channel |
|---|---|---|
| Front end | AIN → PGA → Σ-Δ ADC | DMIC pin → PDM bitstream |
| Decimation | the ADC's own filter | **a separate filter**, order selectable |
| Where they meet | both are selectable sources into the **same** Fast-to-Slow Decimator channels `[repo]` (`FDEC_ROUTE0…7`, ADC = 36–38, DMIC = 39–42/47–50) |

**So everything downstream of the FDEC is matched, and the entire mismatch lives in the front end.**
That is a useful narrowing: it is one fixed number per configuration, not something that accumulates
along the chain.

## 3. ADI does not specify it. This is a vendor-documentation gap, not just ours.

`[fetched]` ADAU1860 datasheet Rev. 0:

- **p.11** gives Group Delay only for the **"ADC INPUT TO DAC OUTPUT PATH"** — 12.9 µs at
  fS = 192 kHz, 7.5 µs at 384 kHz, 5 µs at 768 kHz, under test conditions
  `ADC_FCOMP = 1, DAC_FCOMP = 1`. That is the *combined round trip through both converters*, not
  either input path alone.
- **Figures 39 and 40, p.25** are group delay vs frequency for *"Signal Path = **AINxx to FastDSP to
  HPOUT/LOUT**"* — analog in to analog out.
- **Figures 41–44, p.25** are the only DMIC characterisation, *"Signal Path = DMICxx to SDATAO_x"* —
  and they are **FFTs and relative-level plots. None of them is group delay.**

> `[gap]` **Neither the ADC-to-serial-port delay nor the DMIC-to-serial-port delay is specified
> anywhere, so their difference cannot be derived from the documents.** It has to be measured on the
> configuration that actually ships.

## 4. And it is adjustable — so we are choosing it whether or not we mean to

`[fetched]` UG-2257 p.20 gives the DMIC path **two controls that explicitly trade delay**, and the
datasheet's own test conditions reveal a third on the ADC side:

| Register | Effect | Vendor's words |
|---|---|---|
| `DMICxx_DEC_ORDER` | 4th- or 5th-order initial decimation filter | *"The **fourth-order selection yields the lowest propagation delay**, and the fifth-order selection may be needed to maintain full performance with some high dynamic range microphones."* |
| `DMICxx_FCOMP` | compensate the filter's HF roll-off or not | *"**No compensation gives the lowest propagation delay** but slight attenuation in the pass-band."* |
| `ADC_FCOMP` | same trade on the analog side | appears as a test condition on the p.11 group-delay spec, so it moves that number |
| `DMICxx_FS`, `DMIC_CLK_RATE` | output rate and PDM rate set the decimation ratio | — |

**At least five register choices move this skew.** Two of them are described by ADI purely in terms
of propagation delay, which is as clear a signal as one gets that the delay is expected to be
designed around rather than ignored.

> ⚠ **A caveat I owe on my own earlier answer.** On 2026-09-22 I closed JULIETT's DMIC-clock question
> by reporting that `DMIC_CTRL1` resets to **3.072 MHz**, the IM72D128V's high-performance mode, so
> *"the mic needs no register write at all."* That is true **and incomplete**: the clock rate and the
> decimation settings also set the PDM path's group delay. **So the default is free with respect to
> the microphone and NOT free with respect to accelerometer alignment.** If the skew turns out to
> matter, `DMIC_CLK_RATE` becomes a design variable rather than a default to accept.

## 5. Does it matter? Entirely depends on what the pair is for.

`[derived]` at fS = 48 kHz, one sample is **20.833 µs**, and phase error is `φ = 360 · f · N · Ts`:

| Skew | 40.01 Hz (shaft order) | 100 Hz | 500 Hz | 1 kHz |
|---|---|---|---|---|
| 1 sample | 0.30° | 0.75° | 3.75° | 7.50° |
| 2 samples | 0.60° | 1.50° | 7.50° | 15.0° |
| 5 samples | 1.50° | 3.75° | 18.8° | **37.5°** |
| 10 samples | 3.00° | 7.50° | 37.5° | **75.0°** |

**The verdict flips across the band, which is why "does it matter" has no single answer:**

- **Order tracking — negligible.** `[repo]` the RV-8 content of interest starts at the **40.01 Hz
  shaft order**. Even **10 samples** of skew is **3°** there. This does not threaten order tracking,
  and it is worth saying plainly so nobody blocks that work waiting on this measurement.
- **Broadband ANC or any adaptive filter using the accelerometer as its reference — it matters.** At
  1 kHz, **5 samples is 37.5°**. For fxLMS a phase error in the reference path directly limits
  achievable cancellation and, past a point, stability.

**The reassuring part: it is static, so it is correctable.** Both paths are clocked from one master
clock, so there is no mechanism for the skew to drift or vary sample-to-sample. A fixed integer-sample
offset is removed by delaying the earlier channel, or folded into the FIR for free. **What would be
dangerous is an unknown or varying skew, and this is neither** — once measured.

## 6. How to measure it, and how to keep the acoustics from confounding it

A single sharp tap excites the accelerometer **structurally** (effectively instantly) and the
microphone **acoustically** (delayed by distance). Cross-correlating the two captured channels
therefore returns `skew_electronic + d/c`, with the two terms conflated. **One capture cannot separate
them.** Several can.

**The method: cross-correlate at three or four known mic distances and fit a line.**

```
lag(d) = skew_electronic + d / c
         └─ intercept ─┘   └ slope ┘
```

- the **intercept** is the number we want
- the **slope** must come out at **≈343 m/s** — that is the built-in control. If it does not, the
  measurement is wrong and the intercept is meaningless. **This is what makes the result
  trustworthy rather than merely plausible.**

`[derived]` the geometry is forgiving:

| Mic distance | Acoustic lag | in samples at 48 kHz |
|---|---|---|
| 100 mm | 291.5 µs | 14.0 |
| 200 mm | 583.1 µs | 28.0 |
| **343 mm** | 1000.0 µs | **48.0** |
| 500 mm | 1457.7 µs | 70.0 |
| 1000 mm | 2915.5 µs | 139.9 |

**Moving the mic by 343 mm shifts the lag by exactly 48 samples** — a large, unmistakable signal
against the few samples we are trying to resolve. **To resolve ±1 sample the distance must be known to
±7.1 mm**, which a ruler does.

**Why the rig is already the right instrument:** both channels land in **one sample-synchronous
capture** — which is the entire reason for the shared-clock architecture. So the lag is exact to a
sample directly, and sub-sample by parabolic interpolation of the correlation peak. **No external
instrument is needed, and John's RME is not required for this one.**

**Do it on the configuration that ships**, with `DMICxx_DEC_ORDER`, `DMICxx_FCOMP`, `ADC_FCOMP`,
`DMICxx_FS` and `DMIC_CLK_RATE` all at their final values — and **record those five values with the
result**, because the number is only valid for that combination.

`[gap]` **A cleaner electrical method may exist and I have not established it.** The DAC can be looped
into an analog input to time the ADC path against a known digital reference, but there is no
equivalent loopback for a PDM input — the host would have to synthesise a PDM bitstream into the DMIC
pin under the codec's own `DMIC_CLK`. Possible in principle, fiddly in practice, and not needed if the
two-distance fit closes it.

## 7. What I would not do

**Do not assume it is zero because both channels come out of one chip on one clock.** Sample-
synchronous means the *samples are aligned in the transport*; it says nothing about whether the two
front ends put the same instant of physical reality into the same sample index. **That is exactly the
class of error this repo keeps meeting: parity is not correctness.** Two channels agreeing on a sample
clock proves alignment of the clock, not of the signal.

**Do not derive it from the 12.9 µs figure.** That number is ADC + DAC together at 192 kHz, on the
analog path, with specific `FCOMP` settings. It contains neither of the two terms we need.
