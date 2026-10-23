# Cup power budget on the 8 V A2B bus — 32 Ω vs 150 Ω earcup driver

**Date:** 2026-10-23 · **Agent:** LIMA · **Asked by:** Peter — *"prepare the new power budget per cup assuming a 32 ohm
speaker and 150 ohm"* (read as: two candidate driver impedances). **Numbers:** `scripts/cup_power_budget.py`
(imports the bus model from `scripts/a2b_bus_budget.py`). Every input is tagged in the scripts.

## Summary

| Per cup, at its own VIN (~6.7–6.9 V) | 32 Ω worst | 32 Ω typical | 150 Ω worst | 150 Ω typical |
|---|---|---|---|---|
| Audio level | 0 dBFS sine | −15 dBFS | 0 dBFS sine | −15 dBFS |
| **Current from VIN_CUP** | **69.7 mA** | **42.8 mA** | **62.7 mA** | **41.6 mA** |
| **Power** | **463 mW** | **294 mW** | **420 mW** | **287 mW** |
| Cup R VIN (8 V bus) | 6.65 V | 6.87 V | 6.70 V | 6.88 V |
| Main-node VSSN (both cups) | 139 / 300 mA | 86 / 300 mA | 125 / 300 mA | 83 / 300 mA |
| Battery draw, both cups `[derived]`, boost η 85 % `[assumed]` | ~1.31 W | ~0.81 W | ~1.18 W | ~0.78 W |

**Both impedances fit comfortably** — VIN stays 3 V above the AD2428's 3.7 V minimum and the VSSN switch is at
under half its rating. **The driver impedance barely moves the power budget** (worst case 463 vs 420 mW), because the
headphone current is a small share once the AD2428, the K2 LEDs and the HiFi 3z are counted. **What it does move is
loudness** — see below.

## Line items (worst case, mA)

| Rail | Load | 32 Ω | 150 Ω | Source |
|---|---|---|---|---|
| 1V8 | ADAU1861 AVDD quiescent (ANC) | 3.04 | 3.04 | DS Table 7 `[fetched]` |
| 1V8 | ADAU1861 headphone, 0 dBFS sine | 28.1 | 6.0 | I = 2·Vpk/(π·R), Vpk = 1.41 V `[derived]`; matches T7's +4.8 mA at −15 dBFS/32 Ω |
| 1V8 | ADAU1861 DVDD + HiFi 3z | 33.1 | 33.1 | 3.06 T7 `[fetched]` + 30 `[assumed]` (T7 measured with HiFi 3z bypassed) |
| 1V8 | ADAU1861 IOVDD | 0.32 | 0.32 | T7 `[fetched]` |
| 1V8 | LSM6, IM72D128V, MAXM86161 VDD, AD2428 IOVDD | 4.0 | 4.0 | `[assumed]` |
| VIN | 1V8 buck input (η 85 %) | 21.9 | 14.7 | `[derived]` |
| VIN | AD2428 VIN (incl. its VOUT1/VOUT2) | 29 | 29 | DS max `[fetched]` |
| VIN | 3V3_MIC LDO | 1 | 1 | `[assumed]` |
| VIN | VLED LDO, MAXM86161 average | 5 | 5 | `[assumed]`; 124 mA pulses ride on C6 |
| VIN | K2 LEDs, two strings, 680 Ω | 12.8 | 13.0 | AQW61xS VF `[fetched]` |

**The three biggest items are not the speaker:** the AD2428 (29 mA × ~6.7 V ≈ 195 mW — its internal LDOs drop the whole
bus voltage), the HiFi 3z (assumed), and the K2 LEDs (~85 mW, on whenever the cup is in normal mode).

## The real difference: loudness and bypass

- **Normal mode is voltage-limited.** The ADAU1861's DAC tops out at **1.0 Vrms differential** `[fetched]`, which is its
  30 mW rating into 32 Ω. Into 150 Ω the same voltage is only **6.7 mW** — **6.7 dB less power**. Whether that is
  quieter depends on the drivers' sensitivity (dB SPL/mW), which is not in hand; a 150 Ω driver needs about 6.7 dB more
  sensitivity to match a 32 Ω one at full scale.
- **Bypass is ratio-limited.** The SP-74s are wired for 32 Ω (secondaries in parallel, 3.143:1). At the GMA 340's full
  output (3.87 Vrms `[fetched]`) a 32 Ω driver gets 47 mW and a **150 Ω driver only 10 mW**; the panel sees 158 Ω or
  **741 Ω** for the pair. **For a 150 Ω driver, wire the SP-74 secondaries in series** (1.57:1): the driver then gets
  ~40 mW, the panel sees ~185 Ω for the pair, and each SP-74 carries ~40 mW of its 50 mW rating `[derived]`.

## Not established

- HiFi 3z current (the largest assumption) and the ZLLS400 drop — both want a bench measurement.
- Driver sensitivity for whichever 32 Ω / 150 Ω part is chosen.
- Possible saving, not needed: feeding the AD2428's VIN from a ~4 V pre-regulator instead of the full bus voltage would
  cut its ~195 mW roughly in half.
