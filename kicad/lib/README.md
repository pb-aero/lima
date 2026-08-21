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
