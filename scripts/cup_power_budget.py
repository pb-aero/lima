"""Per-cup power budget on the 8 V A2B bus, for a 32 ohm and a 150 ohm earcup driver.
Run: python3 -I scripts/cup_power_budget.py     Inputs tagged; bus model imported from a2b_bus_budget.py.
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a2b_bus_budget as bus

VFS = 1.0               # [fetched] ADAU1861 DS T1: DAC differential full scale 1.0 Vrms (30 mW into 32 ohm, AVDD 1.8 V)
ETA_BUCK = 0.85         # [assumed] TPS62161, 1.8 V out at ~6.6 V in, tens of mA
VF_LED, R_LED = 1.14, 680   # [fetched] AQW61xS VF at 5 mA; R7/R8 (ruling 12)

def hp_ma(r_ohm, dbfs):
    """Bridged class-AB supply current for a sine: I = 2*Vpk/(pi*R). Cross-check: DS T7 shows +4.8 mA at -15 dBFS/32 ohm."""
    vpk = VFS * 10 ** (dbfs / 20) * math.sqrt(2)
    return 2 * vpk / (math.pi * r_ohm) * 1000

def budget(r_ohm, case, vin):
    worst = case == "worst"
    dbfs = 0 if worst else -15                         # full-scale sine vs ~1 mW-into-32-ohm listening level
    rail_1v8 = {
        "ADAU1861 AVDD quiescent (ANC)": 3.04,         # [fetched] DS T7, high perf, no load
        "ADAU1861 headphone": hp_ma(r_ohm, dbfs),
        "ADAU1861 DVDD (ANC) + HiFi 3z": 3.06 + (30 if worst else 5),   # 3.06 [fetched] T7, HiFi bypassed; HiFi share [assumed]
        "ADAU1861 IOVDD": 0.32,                        # [fetched] T7
        "LSM6DSV16BX + IM72D128V + MAXM86161 VDD + AD2428 IOVDD": 4.0,  # [assumed]
    }
    i_1v8 = sum(rail_1v8.values())
    rows = {  # mA drawn from VIN_CUP
        "AD2428 VIN (incl. VOUT1/VOUT2)": 29 if worst else 20,   # [fetched] max 29 mA; typ [assumed]
        "1V8 buck input": 1.8 * i_1v8 / ETA_BUCK / vin,
        "3V3_MIC LDO (two IM73A135)": 1.0,                       # [assumed]
        "VLED LDO (MAXM86161 average)": 5.0 if worst else 2.0,   # [assumed]; 124 mA peaks on C6
        "K2 LEDs (two strings, normal mode)": 2 * (vin - 2 * VF_LED) / R_LED * 1000,
    }
    return rail_1v8, i_1v8, rows

if __name__ == "__main__":
    out = []
    for r in (32, 150):
        for case in ("worst", "typical"):
            vin = 6.6                     # first pass; refined below from the bus model
            for _ in range(3):
                rail, i18, rows = budget(r, case, vin)
                i_cup = sum(rows.values())
                vl, vr, itot = bus.chain(8.0, i_cup)
                vin = vr                  # size the last cup at its own (lowest) VIN
            p_cup = i_cup * vin
            pmax = (VFS ** 2) / r * 1000
            out.append((r, case, i18, rail, rows, i_cup, p_cup, vl, vr, itot, pmax))
    for r, case, i18, rail, rows, i_cup, p_cup, vl, vr, itot, pmax in out:
        print(f"\n=== {r} ohm driver, {case} ({'0 dBFS sine' if case=='worst' else '-15 dBFS'}): driver max {pmax:.1f} mW at 1.0 Vrms")
        for k, v in rail.items(): print(f"   1V8  {k:52s} {v:6.2f} mA")
        print(f"   1V8  total                                                {i18:6.2f} mA")
        for k, v in rows.items(): print(f"   VIN  {k:52s} {v:6.2f} mA")
        print(f"   per cup: {i_cup:.1f} mA from VIN_CUP = {p_cup:.0f} mW;  bus: VIN cup L {vl:.2f} V, cup R {vr:.2f} V, main VSSN {itot*1000:.0f}/300 mA")
