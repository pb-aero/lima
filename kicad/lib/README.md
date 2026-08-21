# ConnectCore 93 KiCad library

Symbol + footprint for the **Digi ConnectCore 93** SOM (NXP i.MX93), castellated variant.

| File | What |
|---|---|
| `Digi.kicad_sym` | `ConnectCore93` symbol — 118 pins (70 bidirectional, 28 no_connect, 20 power_in) |
| `Digi.pretty/Digi_ConnectCore93_Castellated.kicad_mod` | 118-pad land pattern, 1.27 mm pitch |
| `cc93_pads.json` | The extracted pad table: pad number, LGA pad, signal name, power group |

## Provenance

Built 2026-08-21 from **ConnectCore 93 System-on-Module Hardware Reference Manual, Digi doc
90002549** (`https://docs.digi.com/resources/documentation/digidocs/pdfs/90002549.pdf`).

- **Pin names and numbers** — `[fetched]` parsed from the HRM's castellated pad table (pages
  29+). All 118 pads captured with no gaps; spot-checked against the raw page text.
- **Pad geometry** — `[fetched]` read from the DETAIL A drawing on page 83: 1.27 mm pitch,
  0.9 × 2.0 mm pads, R0.25 corners. Corner pin callouts (PIN 1/32/33/59/60/91/92/118) give the
  counter-clockwise numbering, and 32+27+32+27 = 118 independently confirms the pad table.
- **Overlap check** — `[measured]` every pad pair tested; zero overlaps.

## ~~Read this before using it on real hardware~~ — SUPERSEDED 2026-08-21

> **This whole section was wrong and is kept only as a record.** The 33.56 mm it treats as the
> pad row span is the **host PCB cutout width**. See *Resolved* at the foot of this file.

### original text

**The corner offsets are approximated.** The HRM dimensions the row span (33.56 mm) and the pad
pitch, but not the gap between where a column run ends and a row run begins. Placing rows and
columns on their own spans put the corner pads **on top of each other** — visible as crosses in
the first render. The rows are now pushed out by two pitches to clear the columns, which is
geometrically sound and DRC-clean but is **not** a transcription of a dimensioned corner.

Page 84 of the HRM says: *"See the ConnectCore 93 support page for links to vector files,
additional mechanical drawings, and other design documents."* **Get that vector file and check
the corners against it before committing this to fabrication.** It is fine for layout studies as
it stands.

Two smaller refinements outstanding: `NVCC_SD2` and `1V8` are typed `bidirectional` but are
power rails and should probably be `power_in`; and the symbol's Footprint/Datasheet/Description
properties are empty — Konnect's `create_symbol` silently dropped those arguments, so they are
set on the instance rather than the symbol.

---

# 2026-08-21 · 3D model attached — and what it exposed

## The model

`Digi.pretty/Digi_ConnectCore93_Castellated.kicad_mod` now carries one model block:

```
(model "${KIPRJMOD}/../lib/Digi.3dshapes/Digi_ConnectCore93.step"
  (offset (xyz -20 -22.5 1.547)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))
```

The path is project-relative, so it resolves with **no environment variable to configure**, for any
board kept at `kicad/<project>/`. A board somewhere else needs the path changed.

**The STEP is not committed** — it is 13 MB, and `CLAUDE.md` §5 says large binaries stay out of git.
Restore it with:

```
scripts/fetch-3d-models.sh
```

That script pins both the archive and the extracted file by SHA-256 and fails loudly if Digi
revises the asset, rather than silently installing different geometry.

### Provenance

`[fetched]` 2026-08-21 from *ConnectCore 91 and 93 SoM 3D Model (STEP+PDF)* on
`hub.digi.com`, asset dated 2024-08-18. Contrary to the portal's wording there is **no login and no
licence click-through** — `GET /dp/path=/support/asset/…` returns the zip directly.

- archive `b633376ed52c5c4950fc849b43d04ca3f592d467650570a6dada0ada96c76a0b`
- extracted STEP `24786966510d9b91ee8fe41b55416782a5bd909ca828af090ee64e131fbfa80a`
  (`3001753x-02_A_CC93_3D/CC93_55002169-01_1P_STEP.step`, Open CASCADE, AP214, millimetres)

The archive is **not labelled with a variant**. It is the SOM body, which is common to the LGA and
castellated builds, so it is correct for this footprint — but it is not itself proof of the pad style.

### How the offset was derived

`[measured]` — STEP tessellated via OCCT (`cascadio`) and measured with true assembly transforms.
A naive regex over `CARTESIAN_POINT` gives a 62.5 mm X span; that is **wrong**, because it mixes each
component's local frame with the assembly frame. Use a real kernel.

| Quantity | Value |
|---|---|
| Module outline | **40.000 × 45.000 mm** exactly |
| STEP origin | module **corner**; centre at (20, 22.5) → offset `x=-20, y=-22.5` |
| SOM PCB slab | z **−1.547 … 0.000** — so z=0 is the SOM's **top** copper |
| Offset z | **+1.547**, to bring the SOM's bottom face onto the host board |
| Top-side components | up to z **+1.303** above the SOM PCB top |
| Bottom-side components | down to z **−2.247**, i.e. **0.700 mm below the SOM PCB bottom** |

Verified at the point of use: placed on a throwaway board and rendered headlessly with
`kicad-cli pcb render`. Evidence in `doc/cc93_3dmodel_top.png` and `doc/cc93_3dmodel_front.png`.
The front view confirms the module seats flat on the host board.

## ⚠ What the render exposed: the side pad columns were in the wrong place  — NOW FIXED

This is the caveat the old README flagged as "the corner offsets are approximated", and it is worse
than approximate. The module is **40 mm wide**, not the 33.56 mm that was read off the HRM.

`[measured]` against the STEP outline:

| Pads | Centre | Pad outer edge | Module edge | Result |
|---|---|---|---|---|
| Top / bottom rows (54, `size 0.9×2`) | y = ±22.225 | 23.225 | 22.500 | **+0.725 mm — straddles the edge, correct** |
| Side columns (64, `size 2×0.9`) | x = ±16.510 | 17.510 | 20.000 | **−2.490 mm — buried under the body** |

The rows are right. The columns sit **3.49 mm inboard per side**, entirely underneath the module,
where a castellation cannot reach them. In `doc/cc93_3dmodel_top.png` the top and bottom rows are
visible past the module edge and the left and right columns are simply not there.

Pad **counts and pitch are fine** — 32 pads × 1.27 = 39.37 mm inside the 45 mm edge, 27 × 1.27 =
33.02 mm inside the 40 mm edge. Only the columns' X coordinate and the body outline are wrong.

**Fixed — see *Resolved* below.** The derived ±19.725 was close but wrong; the drawing gives
**±20.000**, pads centred exactly on the module outline.

## ⚠ The host board needs a keepout under the module  — NOW MARKED

`[measured]` from the STEP: **105 solids sit entirely below the SOM's PCB**, protruding **0.700 mm**
past its bottom face. The module cannot seat flat on a plain host board.

Occupied band, expressed in footprint coordinates (origin = pad-array centre):

```
X  -11.750 … +15.400   (27.150 mm)
Y   -4.425 …  +7.850   (12.275 mm)
```

Now marked on `Dwgs.User` — see *Resolved* below. Digi's own dimensioned cutout is larger than
this measured envelope, and Digi's is the one to build to.

## ⚠ Digi ships the wrong file under the footprint/cutout asset

The asset titled *"ConnectCore 91 and 93 — Host PCB footprint and cutout drawing document"*
contains, on 2026-08-21 `[measured]`:

```
ConnectCore 8X - Host PCB footprint and cutout.dwg
ConnectCore 8X-Host PCB footprint and cutout.pdf
```

**ConnectCore 8X — a different module.** This is the exact document the earlier README told us to
check the corner geometry against. It is not the right part, and its file dates (2022-09-08) predate
the CC93. Do not use it for CC93 corner geometry; raise it with Digi.

---

# 2026-08-21 (later) · RESOLVED — geometry sourced from the HRM drawing

Digi's Altium `CC93_DVK.PcbLib` was opened (via KiCad 10's own built-in Altium importer, through
`pcbnew` Python) and it **does not answer the question**: it holds one footprint, a **474-pad LGA
array** at 1.27 mm pitch spanning 40.64 × 35.56 mm with six mounting holes. That is the LGA variant's
land pattern — a different part from the 118-pad castellated one. Recorded so nobody spends the time
twice. It does corroborate the body size indirectly: its array sits inside a 45 × 40 body with a
uniform 2.18 mm margin on both axes.

The answer came from **HRM 90002549 rev 4P, page 83, "Host PCB footprint and cutout"** — which shows
LGA *and* CASTELLATION footprints side by side. The drawing is an embedded bitmap, not vector, so it
was measured by projection profile and calibrated against the pad pitch. `[measured]`

**Guard against the instrument:** autocorrelation on the right-hand column locked onto the *second*
harmonic (100.8 px vs the true 50.4 px), which would have halved every result. The three concordant
runs outvoted it. The calibration was then checked against four of the drawing's own dimension
labels before any of it was believed:

| Drawing label | Reproduced from the bitmap | Error |
|---|---|---|
| `33,56` | 33.632 mm | 0.07 |
| `20,86` | 20.880 mm | 0.02 |
| `12,07` | 12.057 mm | 0.01 |
| `3,22` | 3.225 mm | 0.005 |

## What 33,56 actually is

**`33,56` dimensions the HOST PCB CUTOUT width.** It is not the pad span, and never was. The earlier
session read it as the row span and built all 118 pads around it — which is how 64 pads ended up
3.49 mm inboard of where they belong.

## Corrected geometry — applied

Pad centres sit **on the module outline**, confirmed three ways: the drawing measures ±20.046 /
±22.504; the STEP gives the body as exactly 40.000 × 45.000; and DETAIL A dimensions the pad as
2 mm long with **1** from its centreline, i.e. 1 mm either side of the edge.

| | was | now | source |
|---|---|---|---|
| Side columns (64 pads) | x = ±16.510 | **x = ±20.000** | HRM p.83 + STEP outline |
| Top/bottom rows (54 pads) | y = ±22.225 | **y = ±22.500** | HRM p.83 + STEP outline |
| F.Fab body | 33.56 × 44.45 | **40.000 × 45.000**, pin-1 chamfer | STEP |
| Courtyard | ±17.76 × ±23.475 | **±21.25 × ±23.75** | pad envelope + 0.25 |
| Host cutout | — | **33.56 × 20.86 centred**, on `Dwgs.User` | HRM p.83 |

Pad numbering, pitch, counts (32/27/32/27) and sizes (0.9 × 2.0) are unchanged — they were always
right. The correction is a pure translation of each run outward.

Verified `[measured]`: all four runs straddle the module edge by exactly **1.000 mm**, matching
DETAIL A's `1`; 118 pads present and numbered 1..118 with no gaps; **0 overlapping pad pairs**;
`kicad-cli pcb drc` **0 violations**; and the render `doc/cc93_3dmodel_top.png` now shows
castellations on all four edges where before two sides were bare.

The 1.000 mm overhang was not a target — it fell out of the drawing measurement and then matched
DETAIL A. That agreement is the strongest evidence here.

## The keepout, and which number to build to

Two figures, and they are not the same thing:

- **Digi's dimensioned cutout: 33.56 × 20.86 mm**, centred. Heavy line on `Dwgs.User`. **Build to this.**
- **Measured protrusion envelope: X −11.75…+15.40, Y −4.425…+7.85** `[measured]` from the STEP.
  Thin line on `Dwgs.User`, for reference only. It sits comfortably inside Digi's cutout, which is
  what you would hope — Digi's allows for tolerance and assembly.

Deepest bottom-side protrusion is **0.700 mm** below the SOM's PCB, across 105 solids.

## Still open

- The symbol (`Digi.kicad_sym`) is untouched and still has `NVCC_SD2` / `1V8` typed `bidirectional`
  where they are power rails, and empty Footprint/Datasheet/Description properties.
- Digi's *"ConnectCore 91 and 93 — Host PCB footprint and cutout drawing"* asset still ships
  ConnectCore **8X** files. Worth reporting to Digi; the HRM page 83 drawing is the usable source.

---

# 2026-08-21 (later still) · CORRECTION — the pad table was primary-function only

**I claimed the castellated CC93 has no SPI. That was wrong.** Peter challenged it and he was right.

The claim came from grepping the `signal` field of `cc93_pads.json` for `SPI`. That field holds only
each pad's **primary** function. The HRM's pad tables (pp.29–42) carry a full **multiplexing column**
— up to eight ALT functions per pad — and the original extraction dropped all of it. A confident
negative produced by an instrument that could not have found a positive.

`cc93_pads.json` has been rebuilt: **296 ALT entries across 47 pads**, every one of the 118 pads now
classified, no unexplained gaps. Each record gains `alts` (an ALT0–ALT7 map) and `alt_source`.

## LPSPI3 is a complete 4-wire SPI master

All four lines are ALT1 of one block — the UART7 pins:

| Function | Pad | Primary signal | Mux |
|---|---|---|---|
| `LPSPI3_SCK` | 80 | UART7_RTS | ALT1 |
| `LPSPI3_SIN` (MISO) | 14 | UART7_RX | ALT1 |
| `LPSPI3_SOUT` (MOSI) | 81 | UART7_CTS | ALT1 |
| `LPSPI3_PCS0` (CS) | 13 | UART7_TX | ALT1 |

**Cost: using LPSPI3 consumes UART7**, the flow-control UART. UART6 (the U-Boot console, pads 74/75)
is unaffected.

The other six LPSPI instances are reachable but **incomplete** — verify before relying on any of them:

| Instance | Missing | Note |
|---|---|---|
| LPSPI6 | `SIN` | has SCK (pad 89) + SOUT (pad 88) — **cannot read**, write-only |
| LPSPI7 | `SCK` | everything else present, no clock |
| LPSPI4, LPSPI5 | `SCK`, `SOUT` | chip-select and SIN only |
| LPSPI1, LPSPI2 | `SCK`, `SIN`, `SOUT` | a single PCS1 each |

Nine GPIO are free for extra chip-selects and interrupts: pads 2, 19, 20, 35, 90, 91, 92 at 3V3, and
25, 26 at **1V8** — do not drive those two from 3.3 V logic.

## The 22 pads with no ALT column are genuinely dedicated

Confirmed against the HRM text, not assumed: MIPI-DSI1 pairs (37/38/40/41/43/44/46/47/49/50), USB PHY
(111–114, 116, 118), ADC_IN0/1 (82/83), TAMPER0/1 (86/87), SYS_RESET (56), NVCC_SD2 (12). These have
no multiplexing row in the manual at all.
