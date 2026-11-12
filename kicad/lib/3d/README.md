# 3D models for the custom footprints

`gen_models.py` writes simplified VRML models (KiCad unit 0.1 in): a body box at the datasheet body size plus
leads/pins at the footprint's pad positions. Good for size, height and clearance checks; not vendor-accurate
artwork. Replace any of them with a manufacturer STEP when one is in hand (and gitignore large STEPs).

| Model | Footprint | Body (mm) | Source |
|---|---|---|---|
| AD_LFCSP-88-…CP-88-10.wrl | ADAU1467 | 12 × 12 × 0.85 | ADAU1463/1467 Rev A p.207 |
| Infineon_PG-TLGA-4-2_IM68A130A.wrl | IM68A130A | 3.35 × 2.5 × 0.98 | IM68A130A Rev 1.10 Fig. 6 |
| Panasonic_GU-SOP8_AQW61xS.wrl | AQW612S | 4.4 × 9.37 × 2.1 | Panasonic ASCTB137E p.5 |
| Triad_SP-74.wrl | SP-74 | 10.41 × 7.87 × 11.8, leads 3.5 below board | Triad SP-74 sheet (2024-05-30) |
| Bourns_SM-LP-5001.wrl | SM-LP-5001 | 12.8 × 9.0 × 7.5 | Bourns SM-LP-5001 product dimensions |
| Cvilux_CF31241D0R0-05-NH.wrl | CF31 24P | 16.2 × 5.07 × 1.95 | Cvilux CF3101SF |

**STEP body boxes (2026-11-09/12, for MCAD export).** STEP export cannot carry VRML, so `kicad-cli pcb export step --subst-models` left out every part whose only model here is a `.wrl`. These three `.step` files sit beside their `.wrl` twins, so the substitution picks them up: `AD_LFCSP-SS-64-1EP_9x9mm_P0.5mm_CS-64-2.step` 9 × 9 × 0.75, `Maxim_OLGA-14_2.9x4.3mm_MAXM86161.step` 2.9 × 4.3 × 1.4, `Panasonic_GU-SOP8_AQW61xS.step` 4.4 × 9.37 × 2.1 (mm, body only, no leads, origin at the body centre, bottom on z = 0) `[measured]` from the exported points. Made by exporting a throwaway board whose outline is the body and whose thickness is the body height + 0.07 mm (kicad-cli subtracts two copper layers), `--board-only`. The board files' other custom parts (audio board) have no STEP twin yet.

The ADAU1372 footprint uses KiCad's stock `QFN-40-1EP_6x6mm_P0.5mm.step` (same package).

**Why `restore_models.py` exists:** Konnect's schematic→PCB sync drops footprint `(model …)` blocks, so synced boards
carry no 3D models even for stock parts (found 2026-10-26: 0 of 120 on the audio board, 0 of 102 on the cup board).
The script copies each board footprint's model list back from its library (pads, nets, positions untouched). Run it
with KiCad closed, using KiCad's bundled Python, after any sync:
`/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 -I restore_models.py <board.kicad_pcb>`
