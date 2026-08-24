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

---

# 2026-08-21 · LGA footprint — `Digi_ConnectCore93_LGA`

Built for AeroNode, which needs A2B and therefore a complete I2S/TDM port the castellated variant
cannot provide. Both footprints are kept; they are different products.

**Source:** Digi's own `CC93_DVK.PcbLib` (`CC93-LGArevA`), converted with **KiCad's built-in Altium
importer** driven from KiCad's bundled Python — no transcription, no hand-measurement:

```python
pi = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.ALTIUM_DESIGNER)
fp = pi.FootprintLoad(lib_path, "CC93_DVK")
pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP).FootprintSave(out_pretty, fp)
```

474 pads, 0.70 mm square, 1.27 mm pitch, array 40.640 x 35.560 mm centred on the origin. Rows A..AN
run along +X, numbers along -Y. Body **45.000 x 40.000 mm** — the module's 45 mm axis lies along X in
this orientation, i.e. rotated 90 deg from the castellated footprint.

## ⚠ A vendor footprint carries the vendor's board, not just the part

The converted footprint arrived with the DVK's own artwork, which had to be stripped:

| Layer | What was in it | Action |
|---|---|---|
| **Edge.Cuts** | a 21.5 x 34 mm rounded polygon | **deleted — this would have cut a hole in the AeroNode board** |
| F.SilkS | +/-43.5 x +/-36.5 mm rectangle (the DVK outline, not the module) | replaced |
| Dwgs.User | 31 items of DVK routing artwork | deleted |
| User.3 / User.20 | 13 items of DVK frame and origin marks | deleted |
| pads MH1-6 | zero-size pads at +/-37, +/-27 — DVK board mounting holes, far outside the 45 x 40 module | removed |

There was **no courtyard at all**. Replaced with a proper F.Fab body (chamfered at the A1 corner),
F.SilkS outline at +/-22.65 x +/-20.15, and F.CrtYd at +/-22.75 x +/-20.25.

## The 3D model orientation, and how it was actually settled

The model is the same STEP as the castellated footprint, rotated. Getting this right is harder than
it looks: **the module outline is a plain rectangle, so a 180 deg error renders perfectly plausibly.**
A visual check cannot catch it. Two of six swept candidates seated the module on the pads.

Settled numerically instead. `cc93_pads.json` maps each castellated pad to its LGA pad, giving **108
pads whose real coordinates are known in both footprint files**. Correlating the two coordinate sets
under each candidate rotation:

| Mapping | corr X | corr Y |
|---|---|---|
| identity | +0.044 | -0.044 |
| rot +90 | **-0.9982** | **-0.9976** |
| **rot -90** | **+0.9982** | **+0.9976** |
| rot 180 | -0.044 | +0.044 |

The LGA frame is the castellated frame rotated **-90 deg**. Note the +90 row: a near-perfect
*anti*-correlation. That is precisely the 180 deg error the eye cannot see, and it shows up here as a
sign flip across 108 points.

**KiCad negates the Z value in `(rotate (xyz ...))`.** `[measured]` — the file value that produces a
geometric -90 deg is `+90`. Final transform:

```
(model "${KIPRJMOD}/../lib/Digi.3dshapes/Digi_ConnectCore93.step"
  (offset (xyz -22.5 20 1.547)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 90)))
```

Verified: `kicad-cli pcb render` seats the module on the array; `kicad-cli pcb drc` **0 violations**.
Evidence in `doc/cc93_lga_3dmodel_top.png`.

**Residual, stated honestly:** this establishes the LGA model orientation is *consistent with* the
castellated one. Whether the STEP's own orientation is correct in absolute terms — that the modelled
U.FL connector really sits where a physical module's does relative to pad A1 — is **not verified**.
Digi's 2D model asset would settle it; the endpoint returned HTTP 504 on 2026-08-21, and the 3D PDF's
poster page is blank. Check it against a real module before trusting the model for enclosure fit.

## `ConnectCore93_LGA` symbol — 474 pins, 11 units

Generated deterministically from the HRM's LGA pad tables (pp.43-82, 518/518 ALT entries captured),
not typed. Units:

| # | Unit | Pins | | # | Unit | Pins |
|---|---|---|---|---|---|---|
| 1 | POWER | 29 | | 7 | SERIAL | 33 |
| 2 | GND | 166 | | 8 | DISPLAY | 26 |
| 3 | ENET1 | 14 | | 9 | WIRELESS | 9 |
| 4 | ENET2 | 12 | | 10 | GPIO_CTRL | 27 |
| 5 | USB_SD | 23 | | 11 | NC | 125 |
| 6 | AUDIO | 10 | | | **total** | **474** |

Electrical types: 175 `power_in` (166 GND + VSYS/VSYS2), 13 `power_out` (3V3, 1V8, NVCC_SD2, 3V3_RF),
125 `no_connect` (NC + RESERVED), 158 `bidirectional`, 2 `input` (SYS_RESET, ON_OFF), 1 `output`
(PWR_ON — Digi says never drive it externally).

**Verified `[measured]`:**
- 474 pins parsed back out; every pad number present, **zero name mismatches** against the HRM table.
- **Symbol pin numbers == footprint pad names, exactly, both directions.** This is the check that
  matters: a symbol and footprint that disagree produce a netlist that silently wires the wrong pads.
- All 11 units placed in `kicad/aeronode` sit inside the A0 frame.
- ERC 526 violations, all reconciled: 349 `pin_not_connected` (474 − 125 no-connect), 175
  `power_pin_not_driven` (166 GND + 9 VSYS), 2 `pin_not_driven` (the two input pins). No structural errors.

### ⚠ A malformed .kicad_sym reports as EMPTY, not as an error

The first generation attempt left **one extra closing paren** at end of file. Nothing raised an error.
`list_symbols_in_library` simply returned `count: 0` — and the pre-existing `ConnectCore93` symbol
vanished from the listing too. A library that fails to parse looks exactly like a library with
nothing in it.

**Always read a generated library back and assert the count.** The file was restored with
`git checkout` and regenerated; the paren balance is now asserted as part of generation.

## ublox.pretty/ublox_DAN-F10N.kicad_mod — authored 2026-08-22 [measured]

u-blox DAN-F10N GNSS module, 56-pad LGA + 44-pad ground array (100 pads), 20 x 20 mm body,
21 x 21 mm keepout.

**Source.** The land pattern is NOT in the datasheet. It is in the Integration Manual
`UBXDOC-963802114-13252 R02`, Fig 18 / Table 27 (copper) and Fig 19 / Table 28 (paste).
Both figures are bitmaps; geometry was recovered by connected-component analysis of the
rendered page and cross-checked against the dimension tables until every symbol reconciled.

**Calibration scar.** Blob *sizes* fitted 130 px/mm exactly across 1.50 / 1.10 / 0.80 — and were
wrong. Pitches fitted 127.3. The anti-alias fringe inflates blob sizes by a constant amount but
leaves centroids alone, so **calibrate on distances, never on measured feature sizes**. Calibrating
on Table 27 J made every other dimension land on spec and zeroed the off-grid count.

**Orientation scar.** Datasheet Fig 3 puts pin 1 top-left of the left column; Integration Manual
Fig 18's "Pin 1" leader points at the leftmost pad of the *bottom* row — the two figures are 90 deg
apart. The inner ground array is 4-fold symmetric, so nothing in the drawing reveals the conflict.
**This footprint uses the Fig 3 orientation** (pin 1 top-left), CCW: left 1-14, bottom 15-28,
right 29-42, top 43-56.

**Ground array.** The 44 inner pads carry no pin number in Fig 3 but do carry paste in Fig 19, so
they are real contacts. Assigned pad number **1 (GND)**, the same convention KiCad uses for QFN
thermal pads.

**Verified:** 56/56 pin numbers match the `ublox:DAN-F10N` symbol, no gaps, no extras, 0 overlapping
pad pairs, min copper gap 0.300 mm, paste margin confirmed live through pcbnew.
**Not verified:** no 3D model available.

## U9 MMC5983MA — stock `Package_LGA:LGA-16_3x3mm_P0.5mm` VERIFIED, not authored [measured]

Checked against MEMSIC's own LAND PATTERN drawing (MMC5983MA Rev A, p20) by colour-separated
connected-component measurement. Stock matches exactly: pad 0.45 x 0.30 (measured 0.454 x 0.306),
radial centre offset 1.275 (measured 1.275 +/- 0.000), tangential +/-0.25 / +/-0.75, body 3 x 3.

**Why it matches:** the stock footprint's `descr` cites `MMC5883MA-RevC` — a sibling MEMSIC
magnetometer in the same package. It is not a generic guess. It was still verified, because a
sibling part is not the same part.

**Misreading caught:** the drawing's `2.550` is centre-to-centre, NOT outer-edge to outer-edge.
The outer-edge reading gives 1.050 instead of 1.275 — 0.225 mm wrong on all 16 pads, and it would
have looked finished. At 1.275 the pad outer edge is flush with the 3.0 mm body, normal for a
leadless LGA.

**Measurement scar (same class as DAN-F10N, different cause):** the first run pooled the package
drawing and the land pattern, because BOTH figures sit on p20 and I rendered the whole page —
20 blobs instead of 16, an 11 mm "package", nonsense offsets. Crop to the one figure being measured
before believing any number from a datasheet page.

## Bosch.pretty/Bosch_BMP390_LGA-10_2x2mm.kicad_mod — authored 2026-08-22 [measured]

Bosch Sensortec BMP390 barometer, 10-pin metal-lid LGA 2.0 x 2.0 x 0.75 mm.

**Rejected the obvious candidate.** `ST_HLGA-10_2x2mm_P0.5mm_LayoutBorder3x2y` is ST's pattern for
the **LPS22HH**: a *3-2-3-2* layout with 0.425 x 0.35 pads. The BMP390 is **2-3-2-3** with
0.275 x 0.250 pads — same envelope, same 0.7625 radial offset, completely different part. It would
have looked placed and would not have soldered.

**Bosch publish no separate land pattern.** Datasheet section 7.2 directs that the package outline
dimensions (Fig 26 bottom view) be used AS the landing pattern: copper 1:1 with the package pads,
no expansion. Same philosophy as u-blox DAN-F10N.

- radial offset 0.7625 (= 1.525/2)
- left/right columns: 3 pads each, 0.275 x 0.250, at tangential 0, +/-0.5
- top/bottom rows: 2 pads each, 0.250 x 0.275, at tangential +/-0.25

**Closure beats measurement here.** 0.7625 + 0.1375 + 0.100 = 1.000 = half the 2.00 package. Three
independently-stated dimensions agreeing exactly is stronger evidence than a bitmap measurement, so
this footprint was built from the numbers, not from pixels. Built file reproduces it: max pad extent
0.9000, edge gap 0.100.

**Orientation:** drawn in TOP view per Fig 23, so **pin 1 (VDDIO) is at TOP RIGHT** — deliberately
not the usual top-left, so the footprint stays directly comparable to the datasheet figure.

**Port hole:** 0.25 mm vent on the top face, marked on F.Fab at (+0.40, -0.40). Must not be
obstructed; Bosch also require >= 0.1 mm clearance above the metal lid. Enclosure constraint.

**Verified:** 10/10 pad positions vs Fig 23, 10/10 symbol pin names vs Table 52, 0 overlaps,
min copper gap 0.250 mm. **Not verified:** no 3D model.

## AeroNode.kicad_sym — project-generic symbols, created 2026-08-22

### `NMOS_GSD` — why it exists

Q1 (the LTC4364 OVP pass FET) used `Device:Q_NMOS`, KiCad's **generic** MOSFET symbol whose pin
*numbers* are the letters `D`, `G`, `S`. A SOT-23 footprint has pads `1`/`2`/`3`, so all three pads
bound to **nothing** during netlist import — the pass FET was electrically absent from the board.
ERC never saw it: the schematic is fine, the defect only exists at the symbol-to-footprint boundary.

KiCad 10 ships **no** `Q_NMOS_*` pin-numbered variants (JFETs kept theirs, MOSFETs did not), so there
was nothing stock to swap to. `NMOS_GSD` is `Device:Q_NMOS`'s exact graphics with pins renumbered
**1=G, 2=S, 3=D** — the standard SOT-23 N-MOSFET pinout. Pin at-positions are unchanged, so existing
schematic wires stay attached through the swap.

**Do not "fix" this class of problem by editing the cached `lib_symbols` block in the .kicad_sch** —
"Update Symbols from Library" silently reverts it. It is a fix that looks done and isn't.

**Lesson worth generalising:** a generic symbol with letter pin numbers is a schematic-only
placeholder. It will pass ERC and produce an unconnected part on the board. Check pin *numbers*, not
just pin names, whenever a symbol comes from a `Device:`-style generic library.

## ublox.3dshapes/u-blox_DAN-F10N.step — added 2026-08-24 [measured]

Source: **Sparkfun-KiCad-Libraries** GitHub repo (`3dmodels/GNSS.3dshapes/u-blox_DAN-F10N.step`),
CC-BY 4.0. Not from u-blox directly — u-blox publish no STEP for this part. SparkFun's file traces
back to u-blox's own SolidWorks engineering assembly (`DAN_with_Taoglas_Antenna_110225.STEP`).
5,119,414 bytes, SHA-256 `ac4e12deeab905551cd0424d0b4f7989850cd446ad4ea172667a5f08f06ca568`.

**Scar: text-parsing a multi-part STEP assembly gives nonsense bounding boxes.** Summing every
`CARTESIAN_POINT` in the raw file suggested a 337 x 245 mm part — the file has 10 sub-parts
(interposer, PCB layers, antenna, solder mask), each in its own local coordinate frame, and pooling
coordinates across frames without composing the assembly transforms mixes unrelated geometry. Don't
trust a STEP bounding box computed by regex; render it through a real kernel (KiCad's OCCT via
`kicad-cli pcb render`) and measure the rendered pixels instead.

**Scar: `--quality high` renders are unsuitable for pixel-based measurement.** Its floor/shadow
layer produces a thin anti-aliased line (from silk/keepout geometry) that bridges two unrelated
regions under 4-connectivity, inflating a measured bounding box by ~15x. Use `--quality basic`
(orthographic, no perspective, no floor) for anything measurement-based, and apply a light
morphological erosion (keep only pixels whose 3x3 neighbourhood is mostly the target color) to kill
1px anti-aliasing bridges before connected-component analysis.

**Scar: two symmetric diagonal calibration points are ambiguous under swap.** A pair at local
(-25,-25)/(25,25) can't distinguish "correct assignment, no flip" from "swapped assignment, Y
flipped" — both fit the same |scale| ratio. Use three axis-aligned, distinctly-sized markers
instead: one at the origin, one purely on +X, one purely on +Y. This resolves scale, sign, and
assignment simultaneously with no ambiguity.

**Real KiCad quirk, confirmed empirically: a footprint 3D model's `offset.y` is inverted relative
to board-frame Y; `offset.x` is not.** Verified by measuring the required board-frame shift, applying
it directly (wrong direction, ~2x error), then negating only Y (exact). Document this before anyone
next hand-computes a model offset from a rendered image.

**Board footprints are copies of the library footprint, not live references.** Adding the model to
the library `.kicad_mod` alone did not update the footprint instance already placed on
`aeronode.kicad_pcb`; the board's own U7 instance needed the same `(model ...)` block inserted
directly. `pcbnew.LoadBoard`/`SaveBoard` round-trip is instant to check this on any given footprint.
