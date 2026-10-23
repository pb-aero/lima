"""A2B bus-power margin: AeroNode main node -> cup L -> cup R, per AD242x DS Rev C Fig. 36 / Table 16.
V_NODE = V_NODE_prev - I_A * R_between ;  V_IN = V_NODE - V_diode.  Run: python3 -I scripts/a2b_bus_budget.py
Every input is tagged; change them here, not in prose.
"""
R_SUM = 2.39            # [fetched] DS Table 16: 4 x 0.26 inductor DCR + 1.05 protection R + 1.2 RVSSN + 0.04 connections
R_CABLE_PER_M = 0.242   # [fetched] DS Table 16: 0.121 ohm/m per wire, x2 for bias + return
R_PMOS = 0.085          # [fetched] AO3401A Rds(on) max at Vgs -2.5 V (60 mohm at -4.5 V); not in ADI's table
V_DIODE = 0.38          # [assumed] ZLLS400 at ~0.1-0.2 A; only 0.8 V @ 1.5 A found
L_MAIN_TO_L = 2.0       # [assumed] m, AeroNode to left cup
L_L_TO_R = 0.6          # [assumed] m, headband cable
VIN_MIN_AD2428 = 3.7    # [fetched] DS: VVIN 3.7-9.0 V at the VIN pin
VIN_MIN_LDO = 3.5       # [derived] ADP7118 3.3 V out + ~0.2 V dropout at a few mA

# cup current drawn from VIN_CUP, at VIN ~4 V
def cup_ma(worst):
    ad2428 = 29 if worst else 20            # [fetched] DS IVIN max 29 mA (VOUT1 8 mA, VOUT2 20 mA); typ [assumed]
    # 1V8 rail: ADAU1861 AVDD ANC 7.9 mA [fetched T7] + HP into 32 ohm (loud 40 / typ 5) [assumed]
    #           + DVDD incl. HiFi 3z (30 / 5) [assumed: DS T7 measured with HiFi bypassed] + LSM6/mic/PPG/U6 IO ~4 mA [assumed]
    i_1v8 = 7.9 + (40 if worst else 5) + (30 if worst else 5) + 4
    buck = 1.8 * i_1v8 / (0.85 if worst else 0.80) / 4.0     # TPS62161 at ~4 V in
    mics = 1.0                                               # 3V3_MIC, two IM73A135 [assumed]
    vled = 5 if worst else 2                                 # MAXM86161 average LED current [assumed]
    k2 = 2 * (4.0 - 2 * 1.14) / 220 * 1000                   # two LED strings, VF 1.14 V [fetched AQW61xS]
    return ad2428 + buck + mics + vled + k2

def chain(vbat, i_cup_ma):
    i = i_cup_ma / 1000
    r1 = R_SUM + R_PMOS + R_CABLE_PER_M * L_MAIN_TO_L
    r2 = R_SUM + R_PMOS + R_CABLE_PER_M * L_L_TO_R
    v_node_m = vbat - V_DIODE                    # main node D3
    v_node_l = v_node_m - 2 * i * r1             # cup L carries both cups
    v_node_r = v_node_l - i * r2
    return v_node_l - V_DIODE, v_node_r - V_DIODE, 2 * i

if __name__ == "__main__":
    for label, worst in (("worst", True), ("typical", False)):
        ic = cup_ma(worst)
        print(f"\n{label}: {ic:.0f} mA per cup from VIN_CUP")
        for vbat in (5.0, 5.5, 6.0, 6.4, 7.3, 8.0):
            vl, vr, itot = chain(vbat, ic)
            flag = "OK" if vr >= VIN_MIN_AD2428 else "FAIL"
            print(f"  bus source {vbat:4.1f} V: VIN cup L {vl:4.2f} V, cup R {vr:4.2f} V  ({flag} vs {VIN_MIN_AD2428} V)  main VSSN {itot*1000:.0f} mA of 300")
        # battery needed for cup R to reach 3.7 V
        lo, hi = 3.0, 9.0
        for _ in range(40):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if chain(mid, ic)[1] < VIN_MIN_AD2428 else (lo, mid)
        print(f"  cup R reaches {VIN_MIN_AD2428} V at bus source >= {hi:.2f} V")
    print("\nsensitivity at 5.0 V, worst load (cup R VIN):")
    base = chain(5.0, cup_ma(True))[1]
    for name, delta in (("V_DIODE +0.1 V", ("V_DIODE", 0.1)), ("cable +1 m", ("L_MAIN_TO_L", 1.0)), ("cup current +20 mA", None)):
        g = globals()
        if delta:
            k, d = delta; g[k] += d; v = chain(5.0, cup_ma(True))[1]; g[k] -= d
        else:
            v = chain(5.0, cup_ma(True) + 20)[1]
        print(f"  {name:20s} {v - base:+.2f} V")
