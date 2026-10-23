# A2B bus power: is a 2S LiFePO4 battery enough for two bus-powered cups?

**Date:** 2026-10-23 · **Agent:** LIMA · **Asked by:** Peter — *"work out the VIN_CUP margin at 5.0 V battery through
both cups and the cup power budget, and say whether we need a bus boost."*
**Numbers:** `scripts/a2b_bus_budget.py` (run `python3 -I scripts/a2b_bus_budget.py`; every input is tagged there).

## Answer

**Implemented 2026-10-23 (Peter: "yes"):** audio board U12 LM2731X → VBUS8 = 8.00 V, ruling 12 in
`kicad/audio-board/README.md`; cup R7/R8 → 680R.

**Yes — add a regulated ~8 V bus supply (boost from VBAT) on the audio board.** Fed straight from the battery, the
last cup (cup R) falls below the AD2428's **3.7 V VIN minimum** whenever the battery is under **5.26 V** at worst-case
load, and cup L is already below it at 5.0 V. At typical load there is only **0.10 V** of margin at 5.0 V, and a single
unverified assumption (the diode drop) moves the answer by twice that. With an 8 V bus, cup R sits at **6.4 V** worst
case: 2.7 V of margin, independent of battery state.

| Bus source | Cup L VIN (worst / typ) | Cup R VIN (worst / typ) | vs 3.7 V |
|---|---|---|---|
| 5.0 V (battery empty) | 3.68 / 3.94 V | **3.44** / 3.80 V | **fails worst-case** |
| 5.5 V | 4.18 / 4.44 V | 3.94 / 4.30 V | OK |
| 6.4 V (battery nominal) | 5.08 / 5.34 V | 4.84 / 5.20 V | OK |
| 7.3 V (battery full) | 5.98 / 6.24 V | 5.74 / 6.10 V | OK |
| **8.0 V (boost)** | 6.68 / 6.94 V | **6.44** / 6.80 V | OK, 2.7 V margin |

Cup R reaches 3.7 V at a source of **5.26 V worst case / 4.90 V typical** `[derived]`.

## Why it matters even though it fails safe

A cup that browns out drops its bus power and falls back to bypass (K2 de-energised), so the pilot still hears the
aircraft. But it happens **before** the AeroNode itself is empty — the comms path dies while the box looks alive —
and on the way down the K2 LED current falls to **~2 mA at 3.44 V**, below the AQW612S's 3 mA guaranteed-operate
figure `[fetched]`, so K2 could chatter during a brownout.

## The model `[fetched]` AD242x DS Rev C, Fig. 36 and Table 16

- V_NODE = V_NODE(previous) − I_A × R_between; VIN = V_NODE − V_diode. Cup L carries both cups' current.
- **R_between = 2.39 Ω + 0.242 Ω/m of cable**: four bias inductors (4 × 0.26 Ω), the 1.05 Ω short-circuit protection
  resistor (our R18 / cup R12), the 1.2 Ω VSSN switch, connectors (4 × 0.01 Ω). Plus the AO3401A, which ADI's table
  omits: **< 85 mΩ at −2.5 V** `[fetched]` AOS data sheet.

## Cup current (from VIN_CUP, at ~4 V)

| Load | Worst | Typical | Source |
|---|---|---|---|
| AD2428 VIN (incl. its VOUT1/VOUT2) | 29 mA | 20 mA | DS IVIN max 29 mA `[fetched]`; typ `[assumed]` |
| 1V8 rail via TPS62161 (85 % / 80 %) | 43 mA | 12 mA | below |
| ↳ ADAU1861 AVDD (ANC config) | 7.9 mA @ 1.8 V | 7.9 mA | DS Table 7 `[fetched]` |
| ↳ ADAU1861 headphone into 32 Ω | 40 mA | 5 mA | `[assumed]` loud / normal listening |
| ↳ ADAU1861 DVDD incl. HiFi 3z | 30 mA | 5 mA | `[assumed]` — **DS Table 7 was measured with the HiFi 3z bypassed** |
| ↳ LSM6DSV16BX, IM72D128V, MAXM86161 VDD, AD2428 IOVDD | 4 mA | 4 mA | `[assumed]` |
| 3V3_MIC (two IM73A135) | 1 mA | 1 mA | `[assumed]` |
| VLED average (MAXM86161) | 5 mA | 2 mA | `[assumed]`; peaks to 124 mA ride on C6 |
| K2 LEDs, two strings, 220 Ω | 16 mA | 16 mA | AQW61xS VF 1.14 V `[fetched]` |
| **Total per cup** | **94 mA** | **51 mA** | |

**VSSN limit:** the main node's VSSN switch carries both cups: **188 mA worst of the 300 mA** `[fetched]` limit; cup L's
carries 94 mA. Inside the rating either way.

## Sensitivity (cup R VIN at 5.0 V, worst load)

| Change | Effect |
|---|---|
| Diode drop +0.1 V (two diodes in the path) | −0.20 V |
| Cup current +20 mA | −0.17 V |
| AeroNode-to-cup cable +1 m | −0.05 V |

The diode drop and the HiFi 3z current are the two numbers that most need measuring; the cable length hardly matters.

## What the boost changes

- **Bus source ~8 V regulated from VBAT**, ahead of D3. That is ADI's own example bias (TRM `A2B_SWCTL`: *"bias
  voltage (8 V) on the SENSE pin"*), with no-load cup VIN about 7.2 V against the 9.0 V maximum `[derived]`.
- **Main-node VIN can stay on VBAT** (via D2), but then program `A2B_SWCTL.MODE = 2` — the TRM case for *"the voltage
  on the VIN pin (for example, 5 V) differs significantly from the bias voltage (8 V) on the SENSE pin."* Or feed the
  main node's VIN from the boost too and keep MODE = 0.
- **Cup R7/R8 should go to ~680 Ω.** At 6.4–7.2 V, 220 Ω would push ~20 mA per LED string (≈ 0.27 W per cup, wasted).
  680 Ω gives 5.1 mA at 6.4 V with worst-case VF, 7.2 mA at 7.2 V `[derived]` — inside the 5–30 mA recommendation.
- **Load on the battery:** ~1.5 W at 8 V worst case → ~0.33 A from a 5.0 V battery at 90 % efficiency `[derived]`;
  ADI also recommends sizing the master supply for ≥ 150 mA inrush.

## Not done here

- Boost now drawn (LM2731X, see the audio-board README); no transient or efficiency measurement yet. The cup buck input range (TPS62161, 3–17 V) and the ADP7118s (to 20 V) are
  already fine at 8 V.
- No transient analysis (MAXM86161 124 mA pulses, A2B discovery inrush).
- The two biggest assumptions — ZLLS400 forward drop at 0.1–0.2 A and ADAU1861 current with the HiFi 3z running —
  want a bench measurement; the boost makes the answer insensitive to both.
