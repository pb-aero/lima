# ICM-45686 vs ADXL354 — as DVNC vibration references, not as parts in the abstract

**Date:** 2026-10-07 · **Agent:** LIMA · **Status:** derived from both datasheets, already pinned
locally. Nothing measured.
**Trigger:** Peter asked how the two compare. Flagged as an open comparison in
`docs/anc-dvnc-report-library-synthesis.md` §5 — Chris's shelf recommends "reuse a navigation IMU"
as one option for the DVNC reference; the ADXL354 is the part actually on the board. This is that
comparison, written down for the first time.

Provenance: `[fetched]` = read from the cached PDF, page/table cited · `[derived]` = arithmetic shown
· `[repo]` = already in this repository · `[gap]` = not established.

Sources: `kicad/imu-board/doc/ICM-45686_DS-000489.pdf` (Rev 1.1, 199 pp) ·
`docs/datasheets/ADXL354_355_RevD.pdf` (Rev D, 45 pp) — both pinned by `scripts/fetch-datasheets.sh`.

---

## 1. These are not competing for the same job

**ICM-45686** is a 6-axis navigation IMU (3-axis gyro + 3-axis accel), digital-only, SPI/I2C,
already the AeroNode flight computer's sole IMU (`[repo]` `.agent/MEMORY.md`: *"AeroNode is SINGLE
LANE by Peter's ruling... One ICM-45686, no second IMU"*). **ADXL354** is a 3-axis-only, analog-output
accelerometer with no gyro and no digital interface at all — it is a signal conditioner's problem, not
a sensor-fusion problem.

The only reason to compare them is that both are candidate sources for **one specific signal**: the
structure-borne vibration reference DVNC needs, and Chris's shelf (`2026-06-20_anc_imu_feasibility.html`
§5) names "reuse a navigation IMU that already samples ≥2 kHz locally over SPI — zero added hardware"
as an alternative to a dedicated accelerometer part. The ICM-45686 is exactly that navigation IMU.
ADXL354 is the dedicated-part road not taken by that report, but the one LIMA actually built
(`docs/sensor-head-design-note.md`).

## 2. Side by side, for that one job

| | **ADXL354** `[repo]` as built | **ICM-45686** `[repo]` as flown |
|---|---|---|
| Axes usable for this | 3 (accel only) | 3 (its accel; gyro is irrelevant to rotor-order sensing) |
| Output | **Analog** (XOUT/YOUT/ZOUT), continuous-time | **Digital**, SPI, its own ADC and clock domain |
| Accel noise density | **`[fetched]` 22.5 µg/√Hz @ ±2 g, 25 µg/√Hz @ ±8 g** (p.5, Table "OTHER PARAMETERS") | `[fetched]` **70 µg/√Hz @ ±8 g FSR** (Table 2) — **2.8× noisier** at matched range |
| FSR used | ±8 g (`docs/sensor-head-design-note.md` §2) | selectable ±2…±32 g |
| Bandwidth | Fixed **1.9 kHz** 3 dB analog (sinc-shaped antialias filter, resonance 2.4 kHz) `[fetched]` p.25 | ODR 12.5–6400 Hz (Low Noise Mode), user-configurable digital LPF `[fetched]` Table 1/2 |
| Phase character | **Linear phase** — a pure, constant 148 µs group delay, `[repo]` exactly derived and exactly correctable with one 7-sample digital delay (`docs/dvnc-phase-budget.md` §3) | `[gap]` Not characterized anywhere in this repo or Chris's shelf. A digital IIR/FIR LPF is not generally linear-phase; would need its own group-delay budget before any phase claim could be made |
| Resolution | Set by whatever digitizes it — here, the ADAU1861's own ADC, buffered to land at **−3.9 dB from full scale** (`docs/sensor-head-design-note.md` §3) | Native **16-bit**, 20-bit in HiRes FIFO mode `[fetched]` |
| Package | **6 × 5.6 × 2.2 mm**, 14-terminal LCC `[fetched]` | **2.5 × 3 × 0.81 mm**, 14-pin LGA `[fetched]` — ~1/15th the volume |
| Supply current | **`[fetched]` ~150 µA** (LDO-enabled, Table of D.C. characteristics) | 420–440 µA (6-axis LNM) / 120–130 µA (accel-only LNM) / as low as 15 µA (accel ULP) `[fetched]` Table 3 |
| Interface burden | None — an analog signal needing a buffer, a coupling cap, a bias reference. No driver, no register map, no bus | A full SPI peripheral: registers, FIFO management, a driver already written and flying |
| Already on the aircraft | No — a net-new part, added specifically for this | **Yes** — it is already the flight computer's only IMU, flying today |

## 3. The number that actually decides it: shared clock vs. a second clock domain

This is the part worth not skating past. Chris's shelf's own DVNC science (`docs/anc-dvnc-report-library-synthesis.md`
§2) found that a real coherence test on historical flight data returned **0.0% of the rotor-order band
cancellable**, traced to **~9 ms of cross-clock jitter** between two separately-clocked recording
devices — and named a same-device, same-clock capture as the one fix that removes the problem "by
construction."

- **ADXL354 is wired straight into the ADAU1861's own ADC** — the same codec that reads the DMIC
  reference mic on its Fast-to-Slow Decimator, on one master clock (`docs/accel-vs-pdm-mic-skew.md`
  §1). There is no second clock domain for cross-device jitter to live in. The residual skew that
  survives is a few samples at most (§2 there) — single-digit degrees at the rotor band, not the ~104°
  a 9 ms cross-clock error produces at 32 Hz.
- **The ICM-45686 is a second chip on its own SPI bus with its own sample clock.** Using it as the
  DVNC reference would mean timestamp-aligning its stream to the audio codec's sample clock after the
  fact — structurally the same two-clock architecture that produced the 0.241-coherence, UNPROVEN
  result on the Huey data. "Reuse a navigation IMU that already samples ≥2 kHz" (Chris's §5) is correct
  that the *rate* is more than sufficient (6400 Hz LNM clears the ~400–500 Hz DVNC plateau with ten
  times to spare, same as the ADXL354's 1.9 kHz bandwidth does) — but it quietly reintroduces the exact
  clock-domain problem the rest of that same report spends four sections diagnosing as DVNC's central
  open risk.

**This is the actual reason to prefer a part wired into the audio codec over "just read the existing
IMU," independent of the noise-density or phase arguments below** — those matter, but this is the one
that would otherwise have to be re-discovered on the bench, the same way Chris's team discovered it on
real flight data.

## 4. Where each one wins, stated plainly

**ADXL354, for this job:**
- 2.8× lower noise floor at matched range — a part from ADI's vibration/condition-monitoring-adjacent
  low-noise accelerometer line, not a general navigation part.
- Linear-phase, constant-group-delay response — one number, correctable with a fixed delay, no filter
  design needed (§2 of `docs/dvnc-phase-budget.md`).
- Rides the same sample clock as the reference microphone, by construction — see §3.
- Three of them (X/Y/Z) fit the audio board's exact channel budget: three ADCs, nothing else analog
  needed (`docs/audio-board-decision-record.md` §3.3).

**ICM-45686, for this job:**
- Zero added hardware, zero added cost, zero added board area — it already exists and already flies.
- Higher native digitization (16/20-bit vs. whatever the shared codec ADC yields after the PGA).
- A gyro, if DVNC or anything downstream ever wants attitude-rate information alongside vibration —
  not currently a stated requirement anywhere in this repo or Chris's shelf.
- Lower power in its accelerometer-only, low-power mode (15 µA ULP) than the ADXL354's always-on
  ~150 µA — irrelevant here, since the audio board is not power-constrained the way a battery sensor
  node would be.

## 5. What this does not settle

- `[gap]` The ICM-45686's digital LPF phase/group-delay behavior is not characterized here or in
  Chris's shelf — if a future design ever wanted to timestamp-align it to the codec rather than feed a
  dedicated accelerometer, that budget would need building from scratch, the same way
  `docs/dvnc-phase-budget.md` built the ADXL354's.
- `[gap]` Whether the ADC↔DMIC skew inside the ADAU1861 (the open item in
  `docs/accel-vs-pdm-mic-skew.md`) is actually zero-ish in practice is still unmeasured on hardware —
  the "shares a clock" argument in §3 is about the *architecture*, not a measured result yet.
- This is not a case for ripping out the ADXL354 — the part and the buffering, bias and coupling
  design around it are already committed (`docs/sensor-head-design-note.md`, ruled schematic). It is
  the written record of *why* that was the right call versus the alternative Chris's shelf named, for
  whoever asks next.

## Sources

- `kicad/imu-board/doc/ICM-45686_DS-000489.pdf` Rev 1.1 — Table 1 (gyroscope spec), Table 2
  (accelerometer spec, noise density), Table 3 (D.C. electrical characteristics, supply currents),
  §10.2 package dimensions.
- `docs/datasheets/ADXL354_355_RevD.pdf` Rev D — p.5 acoustic/noise table, p.25 FILTER section
  (sinc shape, bandwidth), p.27 (package), D.C. characteristics table (supply current).
- `[repo]` `docs/sensor-head-design-note.md`, `docs/dvnc-phase-budget.md`,
  `docs/accel-vs-pdm-mic-skew.md`, `docs/audio-board-decision-record.md`,
  `docs/anc-dvnc-report-library-synthesis.md`, `.agent/MEMORY.md` (AeroNode single-lane ruling).
