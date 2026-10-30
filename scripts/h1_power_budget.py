"""H1 power budget at the battery: audio board + A2B bus + both cup boards, as built on 2026-10-30.
Audio-board power tree (kicad/audio-board netlist): VBAT -> U2 TPS62160 -> +1V2 (ADAU1467 DVDD);
VBAT -> U1 TPS62162 -> +3V3 (ADAU1467 IOVDD, ADAU1372 IOVDD, AD2428 IOVDD, W25Q32, SiT8008);
VBAT -> U3 ADP7118 -> +3V3A (ADAU1467 AVDD+PVDD, ADAU1372 AVDD, IM68A130A via R6);
VBAT -> U12 LM2731X -> VBUS8 (8 V) -> D2 -> main-node AD2428 VIN, and -> D3 -> A2B bus bias to both cups;
VBAT -> R23/R24 390R -> K1 PhotoMOS LEDs (U10/U11) while in NORMAL.
Cups come from scripts/cup_power_budget_by_mode.py, bus resistances from scripts/a2b_bus_budget.py.
Run: python3 -I scripts/h1_power_budget.py     Every input is tagged; change them here, not in prose.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a2b_bus_budget as bus          # noqa: E402
import cup_power_budget_by_mode as cupm  # noqa: E402

VBAT = 6.4            # [repo] 2S LiFePO4 nominal, audio-board README default 1 (5.0-7.3 V); Vsys not stated on AeroNode J9
VBUS8 = 8.0           # [repo] ruling 12, LM2731X set to 8.00 V
V_DIODE = bus.V_DIODE  # [assumed] 0.38 V, D2 / D3 like the cups' D1
ETA_BOOST = 0.87      # [fetched] LM2731 Fig. 14/16, X option, ~85-90 % at 50-300 mA (read off graph)
ETA_3V3 = 0.85        # [fetched] TPS62160 Fig. 12/13, 3.3 V out, 6-7 V in, ~10-100 mA
ETA_1V2 = 0.70        # [derived] interpolated between TPS62160 Fig. 17 (0.9 V, ~63 %) and Fig. 15 (1.8 V, ~78 %) at 0.2 A

# --- +1V2: ADAU1467 core ---
DSP_CORE = {"typ": 220.0, "worst": 495.0}   # [fetched] ADAU1467 DS Table 2 (25 C) typical / max program, 294.912 MHz
# Table 3 (-40..+105 C): typical 330, max 940 mA - the hot-cockpit figure

# --- +3V3 digital ---
DSP_IOVDD = {"typ": 20.0, "worst": 53.0}    # [fetched] 53 mA with ALL serial ports clock masters; 20 typ [assumed]
CODEC_IOVDD = {"typ": 2.4, "worst": 3.6}    # [fetched] ADAU1372 T4: master 48 kHz 2.40 mA / 192 kHz 3.62 mA at 3.3 V
A2B_IOVDD = 1.0                              # [assumed] main-node I2S/I2C pad current
OSC = {"typ": 4.0, "worst": 5.0}            # [assumed] SiT8008 12.288 MHz, 3.3 V, typical MEMS oscillator draw
FLASH = 0.05                                 # [assumed] W25Q32 standby after boot

# --- +3V3A analog (linear from VBAT) ---
DSP_AVDD = {"typ": 1.66, "worst": 2.0}      # [fetched] ADAU1467 Table 2
DSP_PVDD = {"typ": 10.1, "worst": 12.9}     # [fetched] ADAU1467 Table 2, 12.288 MHz MCLK
CODEC_AVDD = {"typ": 11.5, "worst": 12.65}  # [fetched] ADAU1372 T5 at 3.3 V, normal / enhanced, internal DVDD reg included
CABIN_MIC = {"typ": 0.105, "worst": 0.135}  # [fetched] IM68A130A IDD
LDO_IGND = 0.05                              # [fetched] ADP7118

def k1_ma(vbat, vf=1.14):  # two strings, two LEDs each, 390R from VBAT  [fetched] AQW61xS VF 1.14 typ
    return 2 * (vbat - 2 * vf) / 390 * 1000

def h1(mode, worst=False, spk_mw=1.0, hifi=False, vbat=VBAT):
    k = "worst" if worst else "typ"
    active = mode == "active"
    vin_cup = cupm.VIN["high" if worst else "nom"]
    cups = {c: cupm.cup(c, mode, vin_cup, spk_mw=spk_mw, hifi=hifi, worst=worst) for c in ("L", "R")}
    i_l, i_r = cups["L"]["i_vin"], cups["R"]["i_vin"]
    p_cups = sum(c["p_vin"] + c["p_d1"] for c in cups.values())
    r1 = bus.R_SUM + bus.R_PMOS + bus.R_CABLE_PER_M * bus.L_MAIN_TO_L
    r2 = bus.R_SUM + bus.R_PMOS + bus.R_CABLE_PER_M * bus.L_L_TO_R
    p_bus = ((i_l + i_r) / 1000) ** 2 * r1 * 1000 + (i_r / 1000) ** 2 * r2 * 1000      # mW, I^2R
    p_d3 = V_DIODE * (i_l + i_r)
    main_node = cupm.ad2428_ma("R", worst)          # main node uses only its B side, like cup R uses only A
    p_main = main_node * VBUS8                      # drawn from VBUS8 through D2
    p_vbus8 = p_cups + p_bus + p_d3 + p_main
    i_1v2 = DSP_CORE[k]
    i_3v3 = DSP_IOVDD[k] + CODEC_IOVDD[k] + A2B_IOVDD + OSC[k] + FLASH
    i_3v3a = DSP_AVDD[k] + DSP_PVDD[k] + CODEC_AVDD[k] + CABIN_MIC[k] + LDO_IGND
    parts = {
        "cups + bus (via boost)": (p_cups + p_bus + p_d3) / ETA_BOOST,
        "A2B main node (via boost)": p_main / ETA_BOOST,
        "ADAU1467 core 1V2": 1.2 * i_1v2 / ETA_1V2,
        "3V3 digital": 3.3 * i_3v3 / ETA_3V3,
        "3V3A analog (LDO)": i_3v3a * vbat,
        "K1 LEDs": k1_ma(vbat) * vbat if active else 0.0,
    }
    total = sum(parts.values())
    return {"parts": parts, "total": total, "i_bat": total / vbat, "p_vbus8": p_vbus8,
            "i_vbus8": p_vbus8 / VBUS8, "cups_at_vin": p_cups, "p_bus": p_bus + p_d3}

def show(label, **kw):
    r = h1(**kw)
    vb = kw.get("vbat", VBAT)
    print(f"\n{label}  (VBAT {vb} V)")
    for n, p in r["parts"].items():
        print(f"  {n:26s} {p:7.0f} mW  {p / r['total'] * 100:4.0f} %")
    print(f"  {'TOTAL from battery':26s} {r['total']:7.0f} mW  = {r['i_bat']:.0f} mA at {vb} V")
    print(f"  (boost output {r['p_vbus8']:.0f} mW = {r['i_vbus8']:.0f} mA at 8 V; cups {r['cups_at_vin']:.0f} mW at VIN_CUP;"
          f" bus I2R + D3 {r['p_bus']:.0f} mW)")
    return r

if __name__ == "__main__":
    show("NORMAL - K1 and K2 on, ANC, 1 mW per 32 ohm speaker, cup HiFi 3z off, hub typical program", mode="active")
    show("NORMAL at an empty battery", mode="active", vbat=5.0)
    show("BYPASS - K1 and K2 off, hub still running", mode="bypass")
    show("WORST - full volume, cup HiFi 3z +30 mA, hub max program (25 C), every max", mode="active",
         worst=True, spk_mw=30.0, hifi=True)
    show("WORST at an empty battery", mode="active", worst=True, spk_mw=30.0, hifi=True, vbat=5.0)
