# GMA match board — ADAU1372 ↔ GMA 245R matching networks, broken out for the bench

**Status (2026-11-13):** schematic done, PCB not started. Peter, 2026-11-13: *"from the audio board i need to
breakout the impedance matching portion from the adau1372 to the gma245r"*. His choices: **both directions**,
**standalone test PCB**, **K1 left out**.

The point is to tune and measure the two aircraft-side networks on a real GMA 245R, driven by an ADAU1372 EVB,
before the full audio board is built. Every part keeps its **audio-board reference designator, value and
footprint** (`kicad/audio-board`, ruling 10 and the comms-tap block), so a value changed here maps one-to-one
back onto that board.

## What's on it

| Path | Chain | Audio-board source |
|---|---|---|
| **TX** (PureVoice → panel mic input) | J1.1/J1.2 `DAC_P`/`DAC_N` → **T4** Bourns SM-LP-5001 600:600 → **R10** 10k → **C37** 220 nF film → `MIC_HI`; T4.4 → `MIC_LO` | ruling 10 |
| **RX** (panel earphone → codec) | `EAR_HI`/`EAR_RTN` → **T2 + T3** Triad SP-74 primaries in parallel → T2 secondary `SPK_L_A` → **R7/R8** 10k/10k → `COMMS_TAP` → **C27** 1 µF → `AIN1`, clamped by **D1** BAT54S to GND/`+3V3A`; **C26** 10 µF on `AIN1REF`; **R9** 0R grounds `SPK_L_B` | comms tap, default 5 |

**Deliberately different from the audio board:** no K1 (U10/U11 AQW612S, Q2, R23/R24, R25) and no failsafe
electret (J6). `PV_OUT` is wired straight to `MIC_HI` and `PV_RTN` straight to `MIC_LO`, so the board sits
permanently in what the audio board calls NORMAL. T3 is kept even though the tap only reads T2: together
they put the same **~158 Ω** load on the GMA's headphone output that the audio board will (README, "SP-74 power").

## Connectors

**J1 — codec side, 2.54 mm 1×8** (jumper wires to the ADAU1372 / EVAL-ADAU1372Z):

| Pin | Net | Connect to |
|---|---|---|
| 1 | `DAC_P` | HPOUTL+ — EVB **J16** (mono differential left output access, UG-807) |
| 2 | `DAC_N` | HPOUTL− — EVB J16 |
| 3, 7 | `GND` | codec AGND |
| 4 | `AIN1` | codec AIN1 pin (after this board's C27 and D1 clamp) |
| 5 | `AIN1REF` | codec AIN1REF (C26 10 µF to GND is on this board) |
| 6 | `+3V3A` | codec **AVDD**: this is D1's clamp rail only. Leave it open and the upper clamp does nothing. |
| 8 | `COMMS_TAP` | divider output, before C27. To use the EVB's own input chain, feed this pin to **J20 tip** (EVB AIN1 jack, 47 µF series cap on the EVB) instead of pin 4. |

`[repo]` EVB jack and header roles are from `linux/adau1372-evb/UG-807-FINDINGS.md`. That file does not give
J16's pin order, so **check J16's pinout against UG-807 before wiring**.

**J5 — panel, JST GH 4-pin**, same part and pinout as the audio board's J5, so the same harness fits both:
1 `EAR_HI` (headphone tip, GMA J2402-16), 2 `EAR_RTN` (sleeve, J2402-1), 3 `MIC_HI` (mic ring, J2401-33),
4 `MIC_LO` (mic sleeve, J2401-35). Contacts are from the GMA 245R install manual, per the audio-board README, 2026-11-13.
**J2** is the same four nets on 2.54 mm pins for clip leads.

**J3 / J4 — 2.54 mm 1×2:** SP-74 secondaries to the cup L / cup R drivers (`SPK_L_A/B`, `SPK_R_A/B`).

## Expected levels — carried over, not measured

- TX `[derived, audio-board ruling 10]`: 1.94 Vrms differential full scale at AVDD 3.3 V. That gives ~1.54 Vrms
  on the T4 secondary at 0 dBFS, and **~69 mVrms into an assumed ~470 Ω panel mic input**. The GMA 245R mic input
  impedance is the unknown this board exists to settle (spec §9).
- RX `[fetched, GMA 340 spec sheet]`: 100 mW per channel into 150 Ω = 3.87 Vrms. That is a different panel,
  so measure the GMA 245R itself.

## Checks run

- `python3 -I doc/design_nets.py check <netlist.xml>`: **OK** against `kicad-cli sch export netlist --format kicadxml`.
  Negative control: moving one pin (C37.2 → C37.9) in a copy of the netlist makes it fail with 4 problem groups. `[measured]`
- ERC: **0 errors, 0 warnings** once the Triad and Bourns footprint libraries were registered in this project's
  `fp-lib-table` (through Konnect). `[measured]`

## Open

1. **PCB not started.** Konnect's schematic→PCB sync needs KiCad running with this board open (IPC). Plan: two layers,
   aircraft nets in the 0.5 mm `Aircraft` netclass as on the audio board, GND pour on the codec side only, aircraft
   corner kept copper-free, non-plated M3 holes so neither ground reaches the chassis.
2. **SP-74 secondary polarity** (3/5 and 4/6 paralleled): still unverified, carried over from the audio board. If it is
   wrong, the secondaries short each other.
3. **Mono plug:** the GMA failsafe check expects the headphone plug's ring shorted to the sleeve (audio-board README,
   2026-11-13). This board's harness should use the same 2-circuit plug.
4. Cosmetic: C26's value text overlaps its GND label on the sheet.
