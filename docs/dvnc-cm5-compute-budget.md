# Can the CM5 run the DVNC per-harmonic estimator? — compute budget and the real risk

**Date:** 2026-10-13 · **Agent:** LIMA · **Status:** analysis from existing benchmarks. Nothing measured
on hardware for this specific workload.
**Trigger:** Peter, on the parameter architecture (compute the per-harmonic amplitude/phase/frequency
estimate near the sensor, send only the lightweight parameter stream to the headset) — *"the pi can do
this computation?"*

Provenance: `[repo]` = already in this repository · `[derived]` = arithmetic shown · `[gap]` = not
established, do not assume · `[assumed]` = flagged explicitly.

---

## 1. The answer in one line

**Almost certainly yes on raw compute, by comparison with a certified benchmark on the same silicon —
but that specific number has never been measured, and the sharper risk is scheduling jitter under
concurrent load, not FLOPs.** This repo has already caught itself assuming a CPU-light task would be
fine on this board and then refused to trust that without a bench measurement, for a different
subsystem. The same caution applies here, unmeasured.

## 2. What the CM5 is, and why the Pi 5 benchmark transfers

`[repo]` AeroNode's host is a Raspberry Pi **Compute Module 5** (`CM5108064B`, 8 GB RAM / 64 GB eMMC).
`docs/aeronode-cm5-software-rev1.md:103` states plainly: it is the **"same SoC, same device-tree
naming"** as a Raspberry Pi 5 Model B. So a certified measurement on a Pi 5 is a legitimate stand-in for
CM5 compute capacity — the die is identical; only the carrier board and peripherals differ.

## 3. The only certified compute number we have — and it isn't this workload

`[repo]` The one real-time audio-DSP benchmark actually run on this hardware is the broadband ML
denoiser, from `2026-07-14_dfn_rnnoise_pi5_bench.md` (cited in
`docs/anc-dvnc-report-library-synthesis.md`):

| Model | Compute per 10 ms frame | Real-time factor | % of one Pi 5 core |
|---|---|---|---|
| DeepFilterNet3 | 2.01 ms | 0.201 | ~20% |
| RNNoise | 0.089 ms | 0.0089 | ~0.9% |

Both run live on the actual target Pi 5, not a desktop estimate, with **three cores entirely free**.

**This is a full deep neural net, not the per-harmonic estimator in question.** DVNC's own estimation
stage — per the offline reference method in Chris's shelf (`huey_machinery_and_anc.html`) — is a
quadrature demodulator per rotor harmonic: one multiply and a low-pass filter per harmonic, run across
~30 harmonics, plus an FxLMS adaptive filter of modest tap count. That class of computation (a bank of
lock-in amplifiers) is textbook-cheap relative to a deep net — orders of magnitude fewer
multiply-accumulates per sample. **`[derived]`, informally: if a full DNN costs ~20% of one core, 30
single-pole lock-in demodulators plus a short adaptive filter would be expected to cost a small fraction
of a single core** — but this is an analogy, not a measurement.

`[gap]` **Nobody has benchmarked the actual quadrature-demod/FxLMS estimator on a CM5 or Pi 5.** The
number above is the right order-of-magnitude comparison, not a substitute for running it.

## 4. The update-rate context that sets how often this has to run

Separately established in this repo's own analysis (not yet a bench measurement): Chris's offline
method uses a **1.8 Hz demod bandwidth** per harmonic, which bounds the estimator's own useful update
rate to roughly **every 50–100 ms** (its settling time constant is ≈1/(2π·1.8 Hz) ≈ 88 ms). That is the
rate the compute budget above has to sustain — not audio-rate (48 kHz), and not once-a-second either.
`[gap]` the real governed-RPM slew rate that would tighten or loosen this bound has not been measured on
real flight data by either side.

## 5. The sharper risk: this repo has already flagged scheduling jitter as the real threat on this chip

`docs/aeronode-ahrs-latency-architectures.md:264` lists what else the CM5 is doing concurrently:
**ArduPilot's flight-critical EKF, Hailo 8L inference over PCIe, 8-lane I2S audio, and NAND/UBIFS I/O.**
That same document states, for a different subsystem (the AHRS loop):

> *"Real jitter distributions on a CM5 under Hailo load are not derivable from a desk calculation."*
> (`docs/aeronode-ahrs-latency-architectures.md:284`)

**That is this repo correcting itself once already** — refusing to assume a CPU-light task is safe on
this board purely because the arithmetic is small, and insisting on a bench measurement under real
concurrent load instead. The same correction applies here, unmeasured:

- DVNC's estimator is one more consumer of CPU time on a four-core chip that already carries a
  flight-critical real-time loop (EKF), an NPU accelerator's PCIe/driver overhead (Hailo 8L), and the
  audio ISR path.
- A workload that is cheap **in isolation** (§3's informal estimate) can still miss its 50–100 ms
  update deadline if it lands behind a Hailo interrupt burst or an EKF scheduling priority — the
  failure mode is jitter and missed deadlines, not "not enough total FLOPs."
- A missed or late parameter update is exactly the silent-failure shape this repo keeps meeting
  elsewhere (`docs/a2b-remote-i2c-throughput.md` §3, on a dropped coefficient write): **the canceller
  doesn't fail loudly, it quietly runs on stale harmonics.**

## 6. What closing this would actually take

1. **Benchmark the real estimator, not a DNN analogy.** Implement the quadrature-demod bank (~30
   harmonics) + FxLMS update on the actual CM5 (or a Pi 5 stand-in, per §2) and measure RTF the same way
   the DeepFilterNet3/RNNoise bench did — `[gap]`, not yet run.
2. **Measure it under the real concurrent load, not alone.** Run it alongside ArduPilot's EKF and a
   representative Hailo 8L inference load simultaneously, and measure the *worst-case* update latency
   and jitter, not just mean compute time — this is the direct analogue of the AHRS jitter gap already
   flagged in `docs/aeronode-ahrs-latency-architectures.md`, applied to DVNC instead.
3. **Decide a core/priority budget rather than hoping for the best.** Given four cores and at least
   three real-time-sensitive consumers (EKF, audio, DVNC estimator), a pinned core or real-time
   scheduling priority for the DVNC path is the kind of decision that closes jitter risk by construction
   rather than by measurement alone — `[gap]`, not yet decided or tested.
4. **Tie the pass/fail threshold to §4's rate, not an arbitrary one.** The estimator needs to meet its
   ~50–100 ms update cadence with bounded jitter; anything that misses that deadline is equivalent to
   running on stale harmonics, which this repo has independently shown degrades real-time cancellation
   (the 66–68% vs. 99.9–100.4% causal-recovery gap turned on a related latency-architecture choice, not
   on raw compute).

## Sources

- `[repo]` `docs/aeronode-cm5-software-rev1.md` (CM5 = same SoC as Pi 5)
- `[repo]` `docs/aeronode-ahrs-latency-architectures.md` (CM5 concurrent workloads; the Hailo-load jitter
  caveat)
- `[repo]` `docs/a2b-remote-i2c-throughput.md` (silent-failure shape for a stale/dropped coefficient)
- `[repo]` `docs/anc-dvnc-report-library-synthesis.md` (DeepFilterNet3/RNNoise Pi 5 benchmark citation;
  FxLMS convergence-over-time as a separate open item)
- `[external]` `Aerosense-Dev-Team-Sync/reports/chris/aerosense/2026-07-01_huey_machinery_and_anc.html`
  (quadrature demod, 1.8 Hz demod bandwidth, per-harmonic method)
- `[external]` `Aerosense-Dev-Team-Sync/reports/chris/aerosense/2026-07-15_DVNC_SCIENCE.html` (FxLMS
  convergence / RPM-jitter tracking as an open item; `2026-07-14_dfn_rnnoise_pi5_bench.md` source
  finding)
