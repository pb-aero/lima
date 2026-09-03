# Vibration reference conditioning — MPU-9250 on scopenode

**Date:** 2026-09-03 · **Agent:** LIMA · all figures `[measured]` on hardware unless marked.

## Read this first — what was asked for vs what is deliverable

The ask was "sample the accelerometer and calculate FIR coefficients for vibration noise
cancelling." I have done the sampling and designed a verified filter, **but it is not an ANC control
filter, and one cannot be computed from this data.** That is a mathematical limit, not a shortcut.

A feed-forward active control filter `W(z)` depends on the **primary path** `P(z)` (disturbance →
error sensor) and the **secondary path** `S(z)` (actuator → error sensor). Neither is present in an
accelerometer recording. `W` is not calculated in closed form at all in practice — it is *adapted*
online by FxLMS against a live error signal, using a measured estimate of `S`.

**To produce a real control filter I need three things I do not have:** an actuator driving the
structure, an error sensor where the vibration is to be cancelled, and a swept-sine measurement of
the secondary path between them. Given those, the design becomes routine.

What *is* derivable from a reference recording, and what is delivered here, is the
**reference-conditioning filter** — the block that sits between the accelerometer and the adaptive
stage. That is a genuine, required part of the chain, and getting it wrong degrades everything
downstream.

## The bench is quiet — these coefficients are fitted to a desk, not an aircraft

`[measured]` 6010 samples, 12.02 s at 500 Hz, no FIFO overflow, mean |a| = 0.981 g.

| Axis | AC RMS | noise floor |
|---|---|---|
| X | 4.79 mg | 86 µg/√Hz |
| Y | 2.45 mg | 84 µg/√Hz |
| Z | 4.13 mg | 136 µg/√Hz |

Strongest spectral content: **8.30 Hz at +24.7 dB** over the median floor, then 11.47, 4.88 and
15.14 Hz, with small residuals near 51 and 103 Hz. Total AC content is a few mg.

That is a bench sitting on a desk — building sway, a fan mount, someone walking past. **There is no
machine running.** The noise floor is respectable and consistent with the part, so the measurement is
sound; there is simply nothing to cancel. **Re-run the capture with the real vibration source
running before trusting any band choice here.** The method transfers; the numbers do not.

## The result that generalises: you cannot low-pass your way to low latency

This is the finding worth keeping. For a linear-phase FIR, the group delay needed to achieve a given
transition width **in Hz** is set by physics, and decimating does not help — it cuts arithmetic, not
delay. `[measured]`, DC rejection of a 3–25 Hz bandpass:

| fs | taps | DC rejection | group delay |
|---|---|---|---|
| 500 Hz | 255 | −20.6 dB | 254 ms |
| 500 Hz | 1023 | −77.7 dB | 1022 ms |
| 100 Hz | 255 | −94.3 dB | **1270 ms** |
| 50 Hz | 127 | −105.3 dB | **1260 ms** |

Decimating from 500 Hz to 50 Hz made the latency **five times worse** for comparable rejection. For
active control this matters directly: feed-forward ANC is only causal if the reference sensor leads
the disturbance by more than the total processing delay. A second of group delay will not be
available.

**So do not ask an FIR to remove gravity.** A one-pole IIR DC blocker does it far better:

```
y[n] = x[n] - x[n-1] + 0.995 * y[n-1]        # corner 0.40 Hz
```

`[measured]` it takes the DC term from **−0.6041 g to +2.2×10⁻⁵ g** — about 89 dB — with **0.0 ms
measured delay at 8.3 Hz**, against the FIR's −20.6 dB for 254 ms. Minimum phase beats linear phase
badly here, and the linear phase buys nothing a control loop needs.

## Delivered chain

**DC blocker (above) first, then this FIR.** Total latency **62 ms**.

`fir_lp25_fs500_63tap.txt` — 63-tap Blackman-windowed lowpass, fc = 25 Hz, fs = 500 Hz.

| | |
|---|---|
| −6.02 dB at 25 Hz | passband edge |
| −79.4 dB at 50 Hz | stopband |
| −97.2 dB at 100 Hz | |
| 62 ms | group delay (31 samples) |
| linear phase | symmetry verified exactly |

`[measured]` end to end on the captured data: gravity removed to ~10⁻⁵ g on all three axes, output
4.31 / 1.58 / 2.85 mg RMS.

Also included, `fir_bp_3_25_fs500_255tap.txt` — the 3–25 Hz bandpass — **for reference only**. Its
DC rejection is a poor −20.6 dB for 254 ms of delay. It is here to document why the DC-blocker route
was chosen over it, not to be used.

## Capture method, and two traps in it

`capture_mpu.py` drains the MPU-9250 **hardware FIFO** rather than polling. Polling from userspace
over I2C jitters by hundreds of microseconds and jitter smears an FFT; the FIFO fills at an exact
internal rate, so samples are uniformly spaced however irregularly they are collected.

Two things cost real time and are guarded in the script now:

1. **`SMPLRT_DIV` only divides a 1 kHz internal rate when `CONFIG.DLPF_CFG` is 1–6.** At 0 or 7 the
   internal rate is **8 kHz**, so the FIFO fills eight times faster than requested and overflows at
   any `--rate`. This looks exactly like a bus-bandwidth problem and is not one.
2. **After a FIFO overflow the byte stream is misaligned** and every later sample is fiction. The
   first capture produced 800 mg of "vibration" equal on all three axes and a mean |a| of 0.33 g.
   The script now aborts on overflow and refuses to save unless mean |a| is within 0.90–1.10 g and
   the sample count matches. **A spectrum computed from that data would have looked entirely
   plausible.**

`[measured]` the I2C bus runs at 100 kHz — 877 µs per 6-byte read, ~1642 samples/s sustainable via
30-byte bursts. A runtime `baudrate=400000` had no effect because `config.txt` had already
instantiated the bus. 500 Hz sampling has comfortable margin; 1 kHz does not.

## Next

1. **Capture with the vibration source running.** Everything above is method; the band is not real yet.
2. **Decide the actuator and error sensor.** Until those exist there is no control filter to compute.
3. **Measure the secondary path** by swept sine, actuator → error sensor. That is the input the
   adaptive stage actually needs.
4. Check the reference-to-disturbance lead time against the 62 ms of conditioning delay.
