# H1 power budget — audio board + A2B bus + two cups, at the battery

**Date:** 2026-10-30 · **Agent:** LIMA · **Asked by:** Peter — *"can we update the h1 power budget"*, then *"Add the
audio board"*. **Numbers:** `scripts/h1_power_budget.py` (`python3 -I scripts/h1_power_budget.py`). It reuses the cup
model in `scripts/cup_power_budget_by_mode.py` and the bus resistances in `scripts/a2b_bus_budget.py`; every input is
tagged in the scripts. Datasheet figures only, from the pinned PDFs in `docs/datasheets/` plus the ADAU1372 data sheet
`[fetched]`. **Nothing measured.** Boards as built: cup board `87c68cc`, audio board at the same commit.

## Answer

**Normal use: ≈ 1.7 W from the battery — 271 mA at 6.4 V, 327 mA at an empty 5.0 V battery.** Worst case ≈ 3.1 W
(490 mA at 6.4 V, **606 mA at 5.0 V**). In bypass, with the hub still running, ≈ 1.3 W.

Normal use = both relays in NORMAL (K1 on the audio board, K2 in each cup), ANC running, speech at 1 mW into each 32 Ω
speaker, cup HiFi 3z off, audio-board ADAU1467 on ADI's "typical program", VBAT 6.4 V `[assumed]` (2S LiFePO4 nominal).

## Where it goes — normal use, 6.4 V

| Block | From battery | Share | Basis |
|---|---|---|---|
| **Both cups + bus losses**, via the 8 V boost | 781 mW | 45 % | Cups 620 mW at VIN_CUP (`kicad/cup-board/README.md`, 2026-10-30) + bus I²R and D3 59 mW `[derived]`, ÷ boost 87 % `[fetched]` LM2731 Fig. 14/16 |
| **ADAU1467 DSP core**, 1.2 V via U2 buck | 377 mW | 22 % | 220 mA typical program `[fetched]` ADAU1467 Table 2 (25 °C); buck ≈ 70 % `[derived]` between TPS62160 Fig. 15 and 17 |
| **A2B main node** (U9 AD2428), via the boost | 183 mW | 11 % | 19.9 mA at 8 V, B side only, same component model as the cups |
| **3.3 V analog**, U3 ADP7118 linear from VBAT | 150 mW | 9 % | 23.4 mA: ADAU1467 AVDD 1.7 + PVDD 10.1, ADAU1372 AVDD 11.5 `[fetched]`, cabin mic 0.1 — all burned at 6.4 V |
| **K1 PhotoMOS LEDs**, R23/R24 390 Ω from VBAT | 135 mW | 8 % | 2 × (6.4 − 2.28) / 390 = 21 mA `[derived]` |
| **3.3 V digital**, U1 buck | 107 mW | 6 % | 27.5 mA: ADAU1467 IOVDD 20 `[assumed]` (53 with every port a clock master), ADAU1372 IOVDD 2.4, oscillator 4 `[assumed]`, A2B IOVDD 1 |
| **Total** | **1733 mW** | | **271 mA at 6.4 V** |

The boost delivers 838 mW (105 mA) at 8 V. **A2B as a whole** — main node, both sub-nodes, bus losses and the cup
diodes — is ≈ 0.63 W, **≈ 37 % of the headset**. The two relay LED drives (K1 here, K2 in each cup) are ≈ 0.34 W, ≈ 20 %.

## By mode

| Mode | 6.4 V battery | 5.0 V battery |
|---|---|---|
| Bypass — K1/K2 off, hub still running | 1.29 W · 201 mA | — |
| **Normal use** | **1.73 W · 271 mA** | **1.63 W · 327 mA** |
| Worst — full volume, cup HiFi 3z +30 mA, hub maximum program, every maximum | 3.14 W · 490 mA | 3.03 W · **606 mA** |

The battery current *rises* as the battery empties because most of the load is switched.

## What this means

1. **The AeroNode power contact can't carry it.** `[repo]` `kicad/audio-board/README.md`: power arrives on one
   contact (J9.23) behind F1, **100 mA hold / 250 mA trip**. Even bypass (201 mA) is twice the hold current; normal
   use is above the trip current at any battery voltage. **This blocks the system working at all**, ahead of any
   efficiency work. The README's fix stands: 2–3 power contacts and a bigger fuse, sized for ≥ 0.65 A.
2. **Battery life:** ≈ 3.7 h per 1000 mAh of 2S pack in normal use (271 mA), not counting the AeroNode itself.
3. **The hot-cockpit number is higher.** ADAU1467 Table 3 (−40 to +105 °C) gives 330 mA typical core current, not 220:
   +0.19 W, ≈ 1.9 W normal.

## Levers, largest first — design changes, none made

1. **Hub DSP clock.** The ADAU1463 at f_CORE 147.456 MHz is specified at **110 mA typical** `[fetched]` Table 2 vs
   220 mA: ≈ −190 mW, if the DSP program fits in half the cycles. Same family and pinout question to check.
2. **Relay LED drives (K1 + 2 × K2, ≈ 0.34 W).** All three use resistors from a 6–8 V rail. Constant-current sinks at
   ~5 mA, with each part's strings in series where the headroom allows, would roughly halve them (≈ −150 mW).
3. **AD2428 linear regulators.** Each node regulates 6.4–8 V down to 1.9/3.3 V internally. A ~4 V buck ahead of VIN
   on each node saves ≈ 40 mW per node.
4. **3V3A LDO from VBAT.** 23 mA dropped from 6.4 V to 3.3 V wastes ≈ 70 mW. Feeding U3 from the 3.3 V buck through a
   low-dropout filter, or from a 4 V pre-regulator, recovers most of it — check the analog noise first.

## Biggest uncertainties

- **ADAU1467 program** (`[fetched]` 213–495 mA across ADI's test programs at 25 °C). The real H1 program isn't written.
- **A2B transceiver duty** at all three nodes (6 mA average per active side `[assumed]`): ±50 mW per node.
- **Cup HiFi 3z current** and **speaker sensitivity** — as in the cup budget.
- **VBAT** — the AeroNode's Vsys is still not stated on its J9 sheet.
- Small `[assumed]` loads: SiT8008 oscillator, ADAU1467 IOVDD at our port count, AD2428 IOVDD.
