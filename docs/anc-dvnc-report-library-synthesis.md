# Chris's report library on ANC/DVNC — what it certifies, and how it maps onto LIMA's own hardware work

**Date:** 2026-10-07 · **Agent:** LIMA · **Status:** analysis of documents in another repo; nothing
measured here.
**Source:** `~/Documents/GitHub/Aerosense-Dev-Team-Sync/reports/chris/aerosense/` — read-only per
`.agent/WHOAMI.md` (other lanes' reports are not mine to edit). This file lives in `lima`, not there.

Provenance: `[external]` = a claim from Chris's shelf, cited to its file · `[repo]` = already in this
repo · `[derived]` = arithmetic done here connecting the two · `[gap]` = genuinely open on both sides.

---

## 1. The five documents, and what each actually settled

| Doc | Date | Status on shelf | What it nails down |
|---|---|---|---|
| `2026-06-20_anc_imu_feasibility.html` | 2026-06-20 | historic | Calibrate→predict→cancel split; the 2.5–5 ms structure-borne lead time; phase-error-vs-dB table; **the reference should be synthetic (RPM→NCO), not a streamed waveform** |
| `2026-07-01_huey_machinery_and_anc.html` | 2026-07-01 | historic | First real-flight proof the airframe IMU and cabin mic share the same rotor-order comb (83% of vibration energy <70 Hz, ~63% tonal) |
| `2026-07-15_DVNC_SCIENCE.html` | 2026-07-15 | **current** | The IMU sample-rate plateau (~400–500 Hz) and the coherence test that failed |
| `2026-07-15_ANC_SCIENCE_update.html` | 2026-07-15 | **current** | Causal ANC recovers 99.9–100.4% of the offline ceiling at ~0.3 s latency; same coherence result restated for the ANC baseline |
| `2026-07-15_john_murray_reconciliation.html` | 2026-07-15 | historic · **CONFIDENTIAL** | Grades all of the above against the Audio Core Deep Dive PDF, one row per claim |

All five carry the fleet's "Iron Rule" (every number cites a source finding commit) and were
independently re-graded by a different agent before landing — worth noting because the numbers below
are about as close to "measured, not asserted" as this kind of document gets.

## 2. The certified numbers that matter

**Sample rate.** Recoverable rotor-order tonal energy vs. candidate IMU rate, computed from a real
2 kHz non-aliased Huey accelerometer batch `[external]` (`aerosim/docs/findings/2026-07-14_t5a_...md`):

| Rate | Cumulative tonal energy |
|---|---|
| 25 Hz (old live IMU) | 75.6% |
| 83 Hz | 89.6% |
| 200 Hz | 99.35% |
| **400–500 Hz** | **99.93–100%** (plateau) |
| 4 kHz | 100% (flat — ~10× overkill) |

**Causal ANC.** A ~0.3 s bounded-latency buffer recovers 7.27–7.30 dB of engine-band reduction, which
is 99.9–100.4% of the *offline, acausal* ceiling — up from an earlier 66–68% causal haircut estimate
`[external]` (`aerosense/docs/findings/2026-07-13_fixed_latency_buffer_anc_validated.md`).

**The coherence result — this is the one that matters most for hardware.** Cross-aligning 250 real
vibration bursts to 1800 s of cabin audio via GPS/UTC regression (two independently-recorded devices,
two clocks):

| Rotor order | Freq | Coherence |
|---|---|---|
| 1 | 5.37 Hz | 0.024 |
| 6 (peak) | 32.20 Hz | **0.241** |
| 20 | 107.33 Hz | 0.016 |

**0.0% of the 3–150 Hz band clears the 0.5 "cancellable" bar.** Controls prove the *method* is sound
(self-coherence 0.9999, shuffled-pairing control 0.003) — the failure is real and specific to this
dataset, not a broken measurement. Cause, quantified: **~9 ms of residual cross-clock jitter** between
the two recording devices. At the dominant 32.2 Hz line, a period is 31.06 ms, so 9 ms is **0.29 of a
full cycle — ≈104°** of phase error. Verdict stated explicitly: **UNPROVEN, not disproven** — the fix
is a same-device, same-clock capture, "not yet run" as of 2026-07-15.

That 104° number is worth sitting with for a second: it is an order of magnitude past the point
(§4 below) where any cancellation survives at all.

## 3. Where LIMA's own work already is the fix Chris's team called for

This is the useful part. Chris's shelf names the decisive next experiment as *"a same-Pi, same-clock
capture... which removes the GPS/NTP cross-file alignment step by construction."* [repo]
`docs/accel-vs-pdm-mic-skew.md` and `docs/dvnc-phase-budget.md` are exactly that architecture, already
analysed at the register level — not aircraft-flight-tested, but the clock topology the shelf asks for
is the one LIMA has been designing into the ADAU1860 since September.

**§2's two-device, two-clock, ~9 ms/104° problem does not exist in LIMA's design, by construction.**
`[repo]` `docs/accel-vs-pdm-mic-skew.md` §1: the accelerometer and the PDM mic "arrive on the same
serial port, under the same BCLK and FSYNC... through the same translator package" — one ADC/DMIC
front end into one codec's Fast-to-Slow Decimator, one master clock. There is no GPS/NTP reconciliation
step to carry a 9 ms error, because there are no longer two files to reconcile.

**But — and this is the finding worth flagging back — sample-synchronous is not automatically
phase-correct**, and LIMA's own §7 says so explicitly: *"parity is not correctness... two channels
agreeing on a sample clock proves alignment of the clock, not of the signal."* The residual skew that
*does* survive a shared clock is the front-end mismatch between the ADC path and the DMIC path (neither
specified by ADI — a vendor-documentation gap), quantified `[repo]`:

| Skew | at 40 Hz (shaft order) | at 500 Hz |
|---|---|---|
| 1 sample (48 kHz) | 0.30° | 3.75° |
| 5 samples | 1.50° | 18.8° |
| 10 samples | 3.00° | 37.5° |

Compare the two failure modes directly: Chris's two-device recording carries a **variable, unmeasured**
~104° error at the rotor fundamental. LIMA's shared-clock path carries a **static, bounded, measurable**
error of a few degrees at that same frequency band — small enough, per the phase-sensitivity table both
sides independently derived (§4), to leave real cancellation margin rather than none. The qualitative
claim "same-clock fixes this" is not just asserted here, it is sized.

**`docs/dvnc-phase-budget.md` goes one step further and answers the shelf's own "what a valid proof
requires" clause with a second decimal place.** The shelf's §5 (anc_imu_feasibility.html) gives a
generic phase-error-to-dB table; LIMA's version (`docs/dvnc-phase-budget.md` §6) is the identical
formula (20·log₁₀(2·sin(θ/2))) applied to the *specific* parts on this board — ADXL354 (a sinc-shaped,
148 µs linear-phase delay, exactly correctable with a 7-sample digital delay) against the IM72D128V DMIC
(a frequency-dependent roll-off below ~300 Hz that is *not* delay-correctable and needs a real filter).
Both independently-derived phase-error tables agree to the decimal place where they overlap
(e.g. 20° → −9.2 dB both sides), which is a small but real cross-check that both groups have the physics
right.

**One more point of convergence, unprompted:** the feasibility report (§2–3, June) argues the live
reference should be a parameter — RPM in, NCO regenerating the waveform locally at the headset — *not*
a streamed vibration waveform, specifically so link latency on a slowly-changing number doesn't eat the
causality budget. `[repo]` `docs/anc-dvnc-summing-amp.md` §1 describes exactly this for the shipping H1
architecture: "DVNC parameter frames ride slot 2... per-harmonic *parameter* frames — synthesised tonal
cancellation... not streamed audio." LIMA's team arrived at the same architecture independently of (or
at least without restating) Chris's shelf reasoning — worth noting as corroboration, not as one side
copying the other.

## 4. What is genuinely still open on both sides

- `[gap]` **The decisive experiment itself has still not been run anywhere, including by LIMA.** Chris's
  shelf asks for a same-Pi, same-clock vibration↔audio coherence measurement; LIMA's
  `accel-vs-pdm-mic-skew.md` §6 has designed the *method* (cross-correlate at 3–4 known mic distances,
  fit `lag(d) = skew_electronic + d/c`, verify the slope is ≈343 m/s) but flags it as not yet run on
  hardware. Running it would simultaneously answer LIMA's own open question and produce the exact result
  Chris's team has been waiting on since July.
- `[gap]` **ADC↔DMIC relative group delay inside the ADAU1860 is unspecified by ADI and unmeasured here**
  (`accel-vs-pdm-mic-skew.md` §3, `dvnc-phase-budget.md` §7). This is the one number standing between
  "sample-synchronous" and "phase-correct" on LIMA's board, and nothing in Chris's shelf resolves it —
  it's below the resolution any of their flight data could see.
  - Note: register choices affect it — `DMICxx_DEC_ORDER`, `DMICxx_FCOMP`, `ADC_FCOMP`,
    `DMIC_CLK_RATE` all trade propagation delay — so it must be measured on the shipping register
    configuration, not a default.
- `[gap]` **FxLMS convergence over time is a separate, still-open failure mode from the clock problem.**
  Chris's shelf (`DVNC_SCIENCE.html` §"honest open items") found that a *fixed*-frequency adaptive
  filter decorrelates against a real governor-driven rotor whose RPM jitters — a live f0/PLL tracking
  problem, not a hardware clock problem. Nothing in LIMA's hardware docs addresses this; it is squarely
  John's DSP territory, flagged here only so it doesn't get mistaken for solved once the clock-skew
  question closes.
- `[gap]` **Tonal fraction vs. cancellability are still two different numbers, and it's worth restating
  for this repo too:** 62–67% tonal-energy-fraction (how much of the sound is at trackable frequencies)
  is not a cancellation result. The shelf is explicit that conflating the two was a real error they
  caught and corrected twice (in `huey_machinery_and_anc.html` and again in both July 15 updates). LIMA's
  own documents don't currently make this mistake, but it's the kind of number that's easy to misquote
  secondhand, so it's worth keeping the distinction live in any investor- or spec-facing material drawn
  from this synthesis.

## 5. One live-wire caveat on citing the feasibility report

`2026-06-20_anc_imu_feasibility.html`'s §6 recommends two specific dedicated vibration parts (ST
IIS3DWB, ADI ADXL1002) as *alternatives* to "reuse a navigation IMU that already samples ≥2 kHz locally
over SPI." LIMA's board uses the **ADXL354** (an analog-output accelerometer feeding the ADAU1860's ADC,
per `dvnc-phase-budget.md`), which is none of the three — a different, already-made part decision this
synthesis is not re-opening. Flagging only so a future reader doesn't assume the shelf's part
recommendation and LIMA's actual BOM agree; they weren't compared against each other before now, and
this document is the first place that comparison has been written down.

## Sources

- `Aerosense-Dev-Team-Sync/reports/chris/aerosense/2026-06-20_anc_imu_feasibility.html`
- `Aerosense-Dev-Team-Sync/reports/chris/aerosense/2026-07-01_huey_machinery_and_anc.html`
- `Aerosense-Dev-Team-Sync/reports/chris/aerosense/2026-07-15_DVNC_SCIENCE.html`
- `Aerosense-Dev-Team-Sync/reports/chris/aerosense/2026-07-15_ANC_SCIENCE_update.html`
- `Aerosense-Dev-Team-Sync/reports/chris/aerosense/2026-07-15_john_murray_reconciliation.html`
  (CONFIDENTIAL — unfiled IP; cited here only for grading cross-references already public in the four
  reports above, nothing from its confidential framing is restated)
- `[repo]` `docs/dvnc-phase-budget.md`, `docs/accel-vs-pdm-mic-skew.md`, `docs/anc-dvnc-summing-amp.md`
