# Cup B board — first-pass schematic

**Status:** preliminary, not reviewed. First attempt at the per-cup ANC/DVNC codec board for
the **right earcup**, per `docs/two-adau1860-channel-allocation.md` §2 and
`docs/audio-board-decision-record.md` Decision A/B — **except the DVNC reference sensor is now
the LSM6DSV16BX over its TDM interface, not the ADXL354 on an analog ADC input**, per Peter.

## What's in this pass

- **U1 — ADAU1861**, same as `cup-a-board`.
- **MK1/MK2 — IM73A135V01** differential mics on AINP0/AINN0 (feed-forward) and AINP1/AINN1
  (feedback), same as Cup A.
- **U2 — LSM6DSV16BX** (new symbol, `kicad/lib/STMicroelectronics.kicad_sym`), ST's 6-axis IMU
  with a TDM slave output mode. Wired per the datasheet's pin table (Table 2) and the
  Mode-2/TDM connection diagram (fetched from ST's hosted datasheet, confirmed against a
  ST community thread reporting a working ESP32 TDM capture at the same clock rates):
  - `TDMout` → U1 `SDATAI_1` (SPT1) — accelerometer data into the codec's second serial port.
  - `BCLK` → U1 `BCLK_1`, `WCLK` → U1 `FSYNC_1` — **the IMU is TDM slave**, so SPT1 must be
    configured as the clock **master** in firmware. That's a register setting on U1, not a
    wiring question, but it doesn't happen by itself — flagged below.
  - `CS` → 1V8 (selects I²C host mode over SPI), `SDO/SA0` → GND (I²C address LSB = 0).
  - `SCL`/`SDA` → the same shared bus as U1, with **R1/R2 (10 kΩ to 1V8)** added as pull-ups —
    the datasheet calls for 10 kΩ and `cup-a-board` doesn't have any on this bus yet.
  - `AH1/QVAR1`, `AH2/QVAR2` (Qvar electrodes) → GND, unused.
  - `INT1`/`INT2` → no-connect for this pass (open item below).
  - Decoupling: 100 nF each on `VDD` (C5) and `VDD_IO` (C4), per the datasheet's Section 7
    application hints.
- **AIN2/AINP2/CM on U1 are now fully unused** (no boom mic, no analog accel) — no-connected.
- **J2 — right earcup driver**, **J3 — power in** (1V8/3V3_MIC/GND, source still TBD), same
  pattern as Cup A.

ERC: 0 errors. 8 warnings — the same benign strap-pin pattern as Cup A (SELFBOOT,
ROM_BOOT_MODE, PD, plus U2's SA0 this time), and single-pin reserved labels on U1's SPT0
(I2S0_*), still held open for a future A2B subnode exactly as in Cup A.

## Datasheet grounding

LSM6DSV16BX pin table, TDM register map (`TDM_CFG0`/`TDM_CFG1` at 0x6C/0x6D), clock rates
(WCLK 8/16 kHz, BCLK 2.048 MHz), and the 100 nF decoupling recommendation were fetched from
ST's own hosted datasheet (`st.com/resource/en/datasheet/lsm6dsv16bx.pdf`, via a text-extraction
proxy since `curl`/`WebFetch` can't reach `st.com` directly in this environment — same
bot-protection pattern already noted for `analog.com` in this repo's `fetch-datasheets.sh`).
Nothing here was guessed from memory of similar ST parts; it's worth doing a proper hand-download
and pinning the PDF (per that script's `verify_manual()` convention) before this leaves
"preliminary."

## Explicitly NOT in this pass — real gaps, not decisions

- **SPT1 master/slave configuration is a firmware TODO, not yet verified against the register
  map.** The wiring assumes the ADAU1861 drives BCLK_1/FSYNC_1; nothing here proves that's how
  Rev G intends the clock topology to work, or that FSYNC_1 can even be configured as an
  output while FSYNC_0 is separately driven.
- **No AD2428W A2B subnode** — same gap as Cup A.
- **No resolved power-delivery path** onto the cup — same gap as Cup A.
- **INT1/INT2 left unconnected.** Whether DVNC needs a data-ready interrupt from the IMU instead
  of polling over the TDM stream is undecided.
- **I²C pull-ups placed here are the only ones on this shared bus so far.** If a future A2B
  subnode or other bus device gets its own pull-ups, these need to be reconciled (one set per
  bus, not per device).
- **No footprints assigned**, schematic only.

Next real step is probably the same as Cup A: the A2B subnode + power question gates everything
else, and now there's a second open question sitting next to it — proving the ADAU1861 can
actually master a TDM-slave IMU on SPT1 while SPT0 is reserved for something else.

## Scar: routing lanes can silently merge on the schematic grid

Found reviewing the rendered preview, not by `find_shorted_nets` (which only compares *labeled*
nets and missed this): the SDA and TDMout long-haul routes were given clear-zone bend heights of
205 mm and 204 mm respectively, intending a 1 mm gap. Both snapped to the same 1.27 mm grid line
(204.47 mm), so the two wires ran collinear and overlapped for several mm — a real short, not a
visual crossing, confirmed by `get_pin_connections` reporting `TDMout` on the `SDA` net. Fixed by
moving TDMout's bend to 203.2 mm (a different grid line) and re-verifying every long route's bend
height is unique via `get_pin_connections` on both ends, not just `find_shorted_nets`.
**Lesson: pick routing-lane coordinates that are already exact multiples of the 1.27 mm grid, and
don't assume two nearby values land on different grid lines — verify labeled *and* unlabeled nets
after any multi-segment reroute.**
