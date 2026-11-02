# AeroNode power budget — rev 0.0.2 + island + vault + headset, at the battery

**Date:** 2026-11-02 · **Agent:** LIMA · **Asked by:** Peter — *"what is the power budget as seen from the battery
for aeronode, audio board and cups"*, then *"use the schematics for the aeronode rev 0.0.2 as well as imu and vault"*.
**Numbers:** `scripts/aeronode_power_budget.py` (`python3 -I scripts/aeronode_power_budget.py`); every input tagged
in the script. The headset half is `docs/h1-power-budget.md` of 2026-10-30.
**Boards:** the vendor schematics *Schematic for {Aeronode, AeroImu, AeroVault} HW ver 0.0.2 rev 1*, drawn
2026-10-01, in the shared Drive. **Nothing is measured.**

## Answer

| Mode | AeroNode side | H1 headset | **System** | at 6.4 V | at 5.0 V |
|---|---|---|---|---|---|
| **Idle** — CM5 idle, Hailo off, no heat | 2.96 W | 1.73 W | **4.69 W** | 733 mA | 938 mA |
| **Cruise** — CM5 idle, Hailo typical, heater on | 5.83 W | 1.73 W | **7.56 W** | 1181 mA | 1512 mA |
| **Peak** — CM5 operating, Hailo at TDP, heater on | 14.27 W | 1.73 W | **16.01 W** | 2501 mA | 3201 mA |

**On the specified pack** `[repo]` (2S LiFePO4 6000 mAh = 38 Wh): **8.2 h idle · 5.1 h cruise · 2.4 h peak.**

> **The headset is the small half.** It is 23 % of the cruise total. Every efficiency lever in the H1 budget
> moves ~0.4 W; the AeroNode moves ten times that.

## Where it goes — cruise, 6.4 V

| Block | Power | Share | Basis |
|---|---|---|---|
| **CM5** | 2222 mW | 29 % | 400 mA idle at 5 V `[fetched]` CM5 datasheet, ÷ buck 90 % |
| **Hailo-8L** | 1667 mW | 22 % | 1.5 W typical `[fetched]` Hailo-8L M.2, on 3V3 |
| **Heater** | 1111 mW | 15 % | 1 W `[repo]` AeroNode decisions, 4 Aug |
| **BCM54210PE Ethernet PHY** | 556 mW | 7 % | **`[assumed]` 0.5 W — datasheet not obtained** |
| **GPS (DAN-F10N)** | 88 mW | 1 % | 24 mA `[fetched]` u-blox, I_VCC |
| Sensors + CO chain + LEDs + island IMUs + vault flash | 184 mW | 2 % | mixed `[fetched]`/`[assumed]` |
| **H1 headset** | 1733 mW | 23 % | `[repo]` the 2026-10-30 budget |

## The three boards, as drawn

**AeroNode rev 0.0.2 is a CM5 carrier** — `CM5____ <Raspberry Pi>` is in the BOM. `[correction]` our own
`kicad/aeronode` project is a **ConnectCore 93** carrier; that is the i.MX9 commercialisation path, not this board.
They are different designs and this budget is for the vendor's CM5 one. Hailo is present (7 references);
**no A2B or ADAU** on it, so the audio board stays a separate budget.

Also on it: BQ25798 charger, 2× TPS564252 bucks, 3× NCV8163 LDOs, BCM54210PE PHY, DAN-F10N, MMC5983MA,
BMP390, BMP581, BME690, the TGS5141 → TLV8811 → ADS1115 CO chain, LP5815 LED driver, USB-C PD.

**AeroImu 0.0.2 is the thermal island** — ICM-45686 + LSM6DSV320X on a TPS7A2033 300 mA LDO, with a DMN2053U
FET switching the heater off `Vcm5_heat`. Tiny except for the heater.

**AeroVault 0.0.2 is the fireproof section** — one F35SQB004G on `Vcm3.3` over a 10-way flex. Electrically
negligible. `[note]` its own sheet says **W25N01GVZEIG is footprint-compatible but only 1 Gbit** — that is the
part benched in September, so the bring-up work transfers to a drop-in.

## What this means

1. **Hailo at TDP is the largest single load in the system — 7.3 W, more than the CM5.** Whether it ever reaches
   TDP depends entirely on the model and duty. If inference is bursty, peak is a thermal and wiring question
   rather than an endurance one; if it runs continuously, endurance halves. **This is the number worth measuring
   first**, and it is cheap to measure.
2. **The Ethernet PHY costs ~0.56 W for something that may not fly.** A 1000BASE-T PHY at full link is a
   significant fraction of idle. If Ethernet is ground-support only, gating it is the easiest watt on the board.
3. **The 5 V contact problem is now worse, not better.** `[repo]` the H1 budget found the audio board takes power
   on one contact behind a 100 mA hold / 250 mA trip fuse, which already failed for the headset alone at 271 mA.
   The AeroNode side draws **911 mA in cruise**; whatever feeds it needs sizing for amps, not hundreds of mA.
4. **Endurance is set by the AeroNode.** 5.1 h cruise on the specified 6 Ah pack is comfortable for a GA sortie,
   but it is 2.4 h if Hailo runs hard, and that is before any derating for temperature or pack ageing.

## Biggest uncertainties, largest first

- **`[assumed]` BCM54210PE at 0.5 W.** The Broadcom datasheet was not obtained. Could plausibly be 0.3–0.8 W
  depending on link speed and whether EEE is enabled. ±0.3 W on the system.
- **`[fetched]` CM5 400 mA / 900 mA are datasheet typicals** that explicitly exclude the module's own 3V3 and
  1V8 regulator outputs, and reviewers measure 1.5–2.7 W idle at the wall. The real figure depends on what
  DSMA, DVNC and the capture stack do to four cores. **Treat 2.2 W idle as a floor.**
- **`[assumed]` buck efficiency 90 %** across all rails. Real curves vary with load; at light load the 3V3 buck
  will be worse.
- **Heater duty is not modelled.** 1 W is the element rating `[repo]`; in a cold cockpit it runs a high duty, in
  a warm one almost none. It is modelled as fully on in cruise and peak, which is pessimistic in summer.
- **`[assumed]` small loads** (sensors, CO chain, LEDs, island IMUs, vault): 184 mW combined. Even a 2× error
  here moves the system under 3 %.

## What would make this real

One afternoon on the bench, in this order: **Hailo under the actual model**, then **CM5 running the real
software load**, then **the PHY with the link up and down**. Those three are 58 % of cruise and carry nearly all
the uncertainty. Everything else is arithmetic.
