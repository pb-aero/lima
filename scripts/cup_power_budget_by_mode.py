"""Cup-board power budget BY MODE and BY CUP (L vs R), at the board as built on 2026-10-30.
Complements scripts/cup_power_budget.py (2026-10-23, docs/cup-power-budget.md), which compares 32 vs 150 ohm
drivers with the bus model; this one builds the AD2428 current from its datasheet components, splits cup L
(A+B transceivers) from cup R (A only), adds a bypass mode and the D1 loss. The two agree to ~5 %.
Power tree (kicad/cup-board netlist): A2B bus bias -> L3 -> V_NODE -> D1 -> VIN_CUP, which feeds
U6 AD2428 VIN (internal linear regs), U7 TPS62161 buck -> 1V8, U8 ADP7118 -> 3V3_MIC, U9 ADP7118 -> VLED,
and the K2 PhotoMOS LED strings (R7/R8 680R). Run: python3 -I scripts/cup_power_budget_by_mode.py
Every input is tagged; change them here, not in prose.
"""

VIN = {"low": 6.44, "nom": 6.8, "high": 7.2}  # [repo] docs/a2b-bus-power-budget.md: 8 V bus, cup R 6.44 V worst, ~7.2 V no-load
V_D1 = 0.38           # [assumed] ZLLS400 drop at ~50-100 mA, as in a2b_bus_budget.py
V_1V8 = 1.8

# TPS62161 efficiency, VOUT 1.8 V, VIN 6-7 V  [fetched] TPS62160 DS Fig. 15 (read off the graph)
def buck_eff(i_ma):
    return 0.74 if i_ma < 10 else (0.755 if i_ma < 30 else 0.77)

# --- 1V8 loads (mA) ---
U1_AMP_ON = 7.87 + 3.06 + 0.32   # [fetched] ADAU1861 T7, high perf, normal voltage, HP on: AVDD + DVDD + IOVDD (HiFi 3z bypassed)
U1_AMP_OFF = 3.04 + 3.06 + 0.32  # [fetched] same table, HP amp off
# DVDD comes from U1's internal regulator (REG_EN high); its input is HPVDD_L [fetched pin table], which is on 1V8
HIFI3Z = {"typ": 5.0, "worst": 30.0}  # [assumed] extra DVDD with the HiFi 3z running - T7 was measured with it bypassed
LSM6 = {"typ": 0.60, "worst": 0.95}   # [fetched] LSM6DSV16BX T4: LA_IddHPT / IddHPT
PDM_MIC = {"typ": 0.43, "worst": 0.525}  # [fetched] IM72D128V T6 at 3.072 MHz, VDD 1.8 V
U6_IOVDD = 0.5        # [assumed] I2S master + I2C switching at 12.288 MHz BCLK into ~15 pF: C*V*f ~ 0.3 mA + data lines
Q2_BASE = (1.8 - 0.7) / 2.2   # [derived] K2 transistor base current from U6 IO7 via R17 2.2k, only when K2 is on

# speaker, 32 ohm, sine: supply current = (2/pi) * sqrt(2P/R)   [derived]; amp max 30 mW into 32 ohm [fetched] T1
def spk_ma(p_mw, r=32.0):
    return 2 / 3.14159265 * (2 * p_mw / 1000 / r) ** 0.5 * 1000

# --- VIN loads (mA) ---
def ad2428_ma(cup, worst):
    vout1 = (12.0 + 1.5) if worst else (10.5 + 1.1)       # [fetched] AD242x T: IDVDD + IPLLVDD
    trx_active = 13.0 if worst else 6.0                     # per transceiver: [fetched] TX 12 / RX 2.8 mA at 100 %; mix [assumed]
    trx_idle = 2.5 if worst else 1.7                        # [fetched] TX and RX disabled
    vout2 = 2 * trx_active if cup == "L" else trx_active + trx_idle   # cup L uses A and B sides; cup R (end) only A
    ivinq = 0.75 if worst else 0.60                         # [fetched]
    return vout1 + vout2 + ivinq                            # IVIN = IVOUT1 + IVOUT2 + IVINQ [fetched]

MIC_RAIL = {"typ": 2 * 0.17 + 0.05, "worst": 2 * 0.23 + 0.14}  # [fetched] IM73A135 T7 x2 (at 2.75 V) + ADP7118 IGND
VLED = {"typ": 0.97 + 0.05, "worst": 1.30 + 0.14}  # [fetched] MAXM86161 at 100 sps: SpO2 (2 LEDs FS) 0.97, 3 LEDs FS 1.3; + IGND

def k2_ma(vin, vf=1.14):          # two strings, two LEDs each, 680R  [fetched] AQW61xS VF 1.14 typ / 1.5 max
    return 2 * (vin - 2 * vf) / 680 * 1000

def cup(cup_id, mode, vin, spk_mw=1.0, hifi=False, worst=False):
    k = "worst" if worst else "typ"
    active = mode == "active"
    i18 = (U1_AMP_ON if active else U1_AMP_OFF) + LSM6[k] + PDM_MIC[k] + U6_IOVDD
    if active:
        i18 += spk_ma(spk_mw) + Q2_BASE
    if hifi:
        i18 += HIFI3Z[k]
    p18 = i18 * V_1V8
    i_buck_in = p18 / buck_eff(i18) / vin
    parts = {
        "AD2428 (U6)": ad2428_ma(cup_id, worst),
        "1V8 buck in": i_buck_in,
        "K2 LEDs": k2_ma(vin) if active else 0.0,
        "mic LDO": MIC_RAIL[k],
        "VLED LDO": VLED[k],
    }
    i_vin = sum(parts.values())
    return {"i_1v8": i18, "parts_mw": {n: i * vin for n, i in parts.items()}, "i_vin": i_vin,
            "p_vin": i_vin * vin, "p_d1": i_vin * V_D1}

def show(label, **kw):
    vin = kw.pop("vin")
    r = {c: cup(c, vin=vin, **kw) for c in ("L", "R")}
    print(f"\n{label}  (VIN_CUP {vin} V)")
    for name in r["R"]["parts_mw"]:
        print(f"  {name:12s}  cup R {r['R']['parts_mw'][name]:6.1f} mW   cup L {r['L']['parts_mw'][name]:6.1f} mW")
    for c in ("R", "L"):
        x = r[c]
        print(f"  cup {c}: 1V8 {x['i_1v8']:5.1f} mA | VIN {x['i_vin']:5.1f} mA = {x['p_vin']:6.1f} mW (+D1 {x['p_d1']:4.1f} mW)")
    tot = sum(r[c]["p_vin"] + r[c]["p_d1"] for c in r)
    print(f"  H1 (both cups, incl. D1): {tot:6.1f} mW, {r['R']['i_vin'] + r['L']['i_vin']:5.1f} mA at VIN_CUP")
    return r

if __name__ == "__main__":
    show("BYPASS - K2 off, aircraft audio straight through, HP amp off", mode="bypass", vin=VIN["nom"])
    show("ACTIVE - K2 on, ANC, speech at 1 mW into 32 ohm, HiFi 3z off", mode="active", vin=VIN["nom"])
    show("ACTIVE + HiFi 3z running (5 mA DVDD, assumed)", mode="active", vin=VIN["nom"], hifi=True)
    show("WORST - 30 mW speaker, HiFi 3z 30 mA, max currents, high VIN", mode="active", vin=VIN["high"],
         spk_mw=30.0, hifi=True, worst=True)
    print(f"\nK2 LED string current: {k2_ma(6.44, 1.5) / 2:.1f} mA (6.44 V, VF max) to {k2_ma(7.2) / 2:.1f} mA (7.2 V, VF typ) per string")
