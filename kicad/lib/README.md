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

## Read this before using it on real hardware

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

## ⚠ What the render exposed: the side pad columns are in the wrong place

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

**The fix is not yet made, deliberately.** By analogy with the rows (centre 0.275 mm inboard of the
edge) the columns belong at **x = ±19.725** — but that is `[derived]`, not read from a drawing, and
it silently moves 64 electrical pads. Confirm it against the HRM pad table or Digi's Altium
`CC93_LGA.SchLib` / `CC93_DVK.PcbLib` before applying. The body outline should become 40 × 45 mm.

## ⚠ The host board needs a keepout under the module

`[measured]` from the STEP: **105 solids sit entirely below the SOM's PCB**, protruding **0.700 mm**
past its bottom face. The module cannot seat flat on a plain host board.

Occupied band, expressed in footprint coordinates (origin = pad-array centre):

```
X  -11.750 … +15.400   (27.150 mm)
Y   -4.425 …  +7.850   (12.275 mm)
```

The footprint carries no keepout for this. It should.

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
