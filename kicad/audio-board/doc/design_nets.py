"""Audio board (clean-slate, 2026-10-22) — intended connectivity, the source of truth the schematic is
checked against. Every pin of every part appears either in NETS or in NC. Rulings and sources:
kicad/audio-board/README.md. Run:  python3 -I design_nets.py check <netlist.xml>
"""
import sys

NETS = {
    # ---- power ----
    # J1 = Cvilux CF31241D0R0-05-NH FFC to AeroNode J9 (same part), 2026-10-26. Flat cable, connectors
    # facing, Type A FFC: our pin n = J9 pin 25-n. J9 pinout: AeroNode HW 0.0.2 rev 1, sheet 6.
    "VBAT": ["J1.2", "U1.2", "U1.3", "C1.1", "U2.2", "C3.1", "U3.1", "U3.3", "C5.1",
             "R23.1", "R24.1", "U12.5", "U12.4", "C57.1", "L7.1"],
    "GND": ["J1.1", "J1.3", "J1.6", "J1.13", "J1.15", "J1.19", "J1.24", "J1.MP", "U1.1", "U1.4", "U1.9", "U1.5", "C1.2", "C2.2", "U2.1", "U2.4", "U2.9", "C3.2", "C4.2",
            "R2.2", "U3.2", "C5.2", "C6.2",
            # hub
            "U4.1", "U4.21", "U4.23", "U4.29", "U4.36", "U4.44", "U4.45", "U4.66", "U4.67", "U4.88", "U4.8",
            "U4.18", "U4.89", "R26.2", "U4.41", "U4.40", "Y1.2", "U5.4", "C7.2", "C8.2",
            "C11.2", "C12.2", "C13.2", "C14.2", "C15.2", "C16.2", "C17.2", "C18.2", "C19.2", "C20.2", "C21.2",
            "C22.2", "C23.2",
            # codec
            "U6.3", "U6.4", "U6.11", "U6.20", "U6.23", "U6.5", "U6.30", "U6.41", "C24.2", "C26.2", "C28.2",
            "C29.2", "C30.2", "C31.2", "C32.2", "C33.2", "C34.2", "U7.2", "U7.4", "C35.2", "R8.2", "R9.2",
            "D1.1",
            # a2b
            "U9.7", "U9.8", "U9.25", "U9.31", "U9.33", "C39.2", "C40.2", "C41.2", "C42.2", "C43.2", "C44.2",
            "C45.2", "C46.2", "C50.2", "C51.2", "C54.2", "C55.2",
            # bypass
            "Q2.2", "R25.2",
            # 8 V bus boost (ruling 12)
            "U12.2", "C57.2", "C58.2", "C59.2", "R28.2"],
    "+3V3": ["U1.6", "L1.2", "C2.1", "U2.3", "R3.1",
             "U4.2", "U4.22", "U4.37", "U4.46", "U4.68", "Y1.1", "Y1.4", "C7.1", "U5.3", "U5.7", "U5.8",
             "C8.1", "R4.1", "C11.1", "C12.1", "C13.1", "C14.1", "C15.1", "C23.1",
             "U6.40", "C34.1", "U9.9", "C45.1"],
    "SW3V3": ["U1.7", "L1.1"],
    "+1V2": ["U2.6", "L2.2", "C4.1", "R1.1", "U4.24", "U4.43", "U4.65", "U4.87", "C18.1", "C19.1", "C20.1",
             "C21.1", "C22.1"],
    "SW1V2": ["U2.7", "L2.1"],
    "FB1V2": ["U2.5", "R1.2", "R2.1"],
    "RESET_N": ["U2.8", "R3.2", "U4.28", "U6.27"],
    "+3V3A": ["U3.4", "U3.5", "C6.1", "U4.9", "U4.19", "C16.1", "C17.1", "C9.1", "C10.1",
              "U6.10", "U6.19", "U6.24", "C31.1", "C32.1", "C33.1", "R6.1", "D1.2"],
    # ---- host header (mirrors AeroNode J3/J4) ----
    "I2S_WS": ["J1.12", "U4.47", "U4.74"],
    "I2S_BCLK": ["J1.14", "U4.48", "U4.73"],
    "HOST_SDI0": ["J1.11", "U4.49"],
    "HOST_SDO0": ["J1.10", "U4.75"],
    "HOST_SDI1": ["J1.17", "U4.52"],
    "HOST_SDO1": ["J1.16", "U4.78"],         # coefficient lane (ruling 8)
    "I2C_SCL": ["J1.5", "U4.39", "U6.2", "U9.4"],
    "I2C_SDA": ["J1.4", "U4.38", "U6.1", "U9.5"],
    "CTL_MIC": ["J1.7", "Q2.1", "R25.1"],
    "CTL_SPKR": ["J1.8", "U9.16"],          # ruling 11: cup K2 control via AD2428 IO7, GPIO-over-distance to the cups
    "HOST_SDI2": ["J1.18", "U4.72"],
    "HOST_SDO2": ["J1.20", "U4.71"],
    "HOST_SDI3": ["J1.22", "U4.70"],
    "HOST_SDO3": ["J1.21", "U4.69"],
    # ---- hub ----
    "MCLK_IN": ["Y1.3", "U4.25"],
    "BOOT_CS": ["U4.32", "U5.1"],
    "BOOT_MOSI": ["U4.33", "U5.5"],
    "BOOT_SCLK": ["U4.34", "U5.6"],
    "BOOT_MISO": ["U4.35", "U5.2"],
    "SELFBOOT": ["U4.42", "R4.2"],
    "PLLFILT": ["U4.20", "C9.2", "R5.2"],
    "PLL_RC": ["C10.2", "R5.1"],
    "VDRIVE": ["U4.3", "R26.1"],             # DS: VDRIVE to GND when DVDD is external; 0R keeps ERC clean
    "CODEC_MCLK":["U4.27", "U6.39"],
    "CODEC_BCLK": ["U4.56", "U4.81", "U6.32"],
    "CODEC_LRCLK": ["U4.55", "U4.82", "U6.31"],
    "CODEC_DAC": ["U4.57", "U6.33"],
    "CODEC_ADC": ["U4.83", "U6.34"],
    "A2B_BCLK": ["U4.59", "U4.84", "U9.10"],
    "A2B_SYNC": ["U4.58", "U4.85", "U9.11"],
    "A2B_DRX0": ["U4.60", "U9.14"],
    "A2B_DRX1": ["U4.64", "U9.15"],
    "A2B_DTX0": ["U4.86", "U9.12"],
    "A2B_DTX1": ["U4.63", "U9.13"],
    # ---- codec ----
    "AIN0REF": ["U6.8", "C24.1"],
    "AIN0": ["U6.9", "C25.2"],
    "CABIN_MIC": ["U7.1", "C25.1"],
    "MIC_VDD": ["U7.3", "R6.2", "C35.1"],
    "AIN1REF": ["U6.13", "C26.1"],
    "AIN1": ["U6.14", "C27.2", "D1.3"],
    "COMMS_TAP": ["R7.2", "R8.1", "C27.1"],
    "CODEC_CM": ["U6.12", "C28.1"],
    "CODEC_DVDD": ["U6.28", "U6.29", "C29.1", "C30.1"],
    # PureVoice out (ruling 10): both DAC legs drive T4 SM-LP-5001 directly; attenuator + DC block on the
    # aircraft-side secondary; secondary return goes to K1 mic-lo, never to our GND.
    "DAC_N": ["U6.21", "T4.2"],
    "DAC_P": ["U6.22", "T4.1"],
    "PV_SEC": ["T4.3", "R10.1"],
    "PV_ATT": ["R10.2", "C37.1"],
    "PV_OUT": ["C37.2", "U10.5"],
    "PV_RTN": ["T4.4", "U11.5"],
    # ---- 8 V A2B bus supply (ruling 12): LM2731X boost from VBAT; feeds bus bias (D3) and main-node VIN (D2) ----
    "BOOST_SW": ["L7.2", "U12.1", "D4.2"],
    "VBUS8": ["D4.1", "C58.1", "C59.1", "R27.1", "C60.1", "D2.2", "D3.2"],
    "BOOST_FB": ["U12.3", "R27.2", "R28.1", "C60.2"],
    # ---- A2B main node ----
    "A2B_VIN": ["U9.30", "D2.1", "C43.1", "C44.1"],
    "A2B_VOUT1": ["U9.32", "U9.1", "U9.2", "U9.3", "C39.1", "C40.1"],
    "A2B_VOUT2": ["U9.29", "U9.20", "U9.21", "C41.1", "C42.1"],
    "A2B_VPWR": ["D3.1", "C46.1", "R17.1", "C47.1", "R18.1"],
    "A2B_GATE": ["R17.2", "C47.2", "Q1.1", "R19.2", "C48.1"],
    "A2B_QS": ["R18.2", "Q1.2"],
    "A2B_BIASP": ["Q1.3", "C48.2", "R20.1", "L3.1"],
    "A2B_SWP": ["U9.27", "R19.1"],
    "A2B_SENSE": ["U9.28", "R20.2"],
    "A2B_VSSN": ["U9.26", "L4.2"],
    "A2B_BP": ["U9.22", "FB1.1", "C49.1", "L5.1"],
    "A2B_BN": ["U9.23", "FB2.2", "C49.2", "L6.1"],
    "A2B_BCM": ["U9.24", "FB1.2", "FB2.1"],
    "A2B_BPF": ["L5.2", "C50.1", "FL1.1"],
    "A2B_BNF": ["L6.2", "FL1.3"],
    "A2B_BPT": ["FL1.2", "R21.1", "C52.1"],
    "A2B_BNT": ["FL1.4", "R22.2", "C53.1"],
    "A2B_TCT": ["R21.2", "R22.1", "C51.1"],
    "A2B_LINE_P": ["C52.2", "L3.2", "C54.1", "C56.1", "J3.1"],
    "A2B_LINE_N": ["C53.2", "L4.1", "C55.1", "C56.2", "J3.2"],
    # ---- aircraft / bypass ----
    "EAR_HI": ["J5.1", "T2.1", "T3.1"],
    "EAR_RTN": ["J5.2", "T2.2", "T3.2"],
    "SPK_L_A": ["T2.3", "T2.5", "J3.3", "R7.1"],
    "SPK_L_B": ["T2.4", "T2.6", "J3.4", "R9.1"],
    "SPK_R_A": ["T3.3", "T3.5", "J4.1"],
    "SPK_R_B": ["T3.4", "T3.6", "J4.2"],
    "MIC_HI": ["J5.3", "U10.6", "U10.8"],
    "MIC_LO": ["J5.4", "U11.6", "U11.8"],
    "ELEC_HI": ["J6.1", "U10.7"],
    "ELEC_LO": ["J6.2", "U11.7"],
    "K1A_LED": ["R23.2", "U10.1"],
    "K1A_MID": ["U10.2", "U10.3"],
    "K1B_LED": ["R24.2", "U11.1"],
    "K1B_MID": ["U11.2", "U11.3"],
    "K1_DRV": ["U10.4", "U11.4", "Q2.3"],
}

NC = ["J1.9",                            # J9.16 "reserved"
      "J1.23",                           # J9.2 Vcm3.3: left open, never back-feed our +3V3 into the CM5
      "U1.8",
      "U4.26", "U4.51", "U4.50", "U4.76", "U4.77", "U4.62", "U4.61", "U4.10", "U4.11", "U4.12", "U4.13",
      "U4.14", "U4.15", "U4.16", "U4.17", "U4.80", "U4.79", "U4.30", "U4.31", "U4.53", "U4.54", "U4.6",
      "U4.7", "U4.4", "U4.5",
      "U6.38", "U6.15", "U6.16", "U6.17", "U6.18", "U6.6", "U6.7", "U6.35", "U6.36", "U6.37", "U6.25",
      "U6.26",
      "U9.6", "U9.17", "U9.18", "U9.19"]


def check(xml_path):
    import xml.etree.ElementTree as ET
    r = ET.parse(xml_path).getroot()
    pin2net = {}
    for n in r.iter("net"):
        name = n.get("name").lstrip("/")
        for x in n.iter("node"):
            pin2net[f"{x.get('ref')}.{x.get('pin')}"] = name
    bad = 0
    for net, pins in NETS.items():
        got = {p: pin2net.get(p) for p in pins}
        wrong = {p: g for p, g in got.items() if g != net}
        if wrong:
            bad += 1
            print(f"NET {net}: {wrong}")
    groups = {}
    for p, n in pin2net.items():
        groups.setdefault(n, set()).add(p)
    for net, pins in NETS.items():
        extra = groups.get(net, set()) - set(pins)
        if extra:
            bad += 1
            print(f"NET {net}: unexpected extra pins {sorted(extra)}")
    for p in NC:
        n = pin2net.get(p, "")
        if n and not n.startswith("unconnected"):
            bad += 1
            print(f"NC {p} is on {n}")
    declared = {p for ps in NETS.values() for p in ps} | set(NC)
    stray = sorted(p for p in pin2net if p not in declared and not p.startswith("#"))
    if stray:
        bad += 1
        print("pins in schematic but not in design:", stray)
    missing = sorted(p for p in declared if p not in pin2net)
    if missing:
        bad += 1
        print("pins in design but not in schematic:", missing)
    print("OK" if not bad else f"{bad} problem group(s)")
    return bad


if __name__ == "__main__":
    if sys.argv[1] == "check":
        sys.exit(1 if check(sys.argv[2]) else 0)
    if sys.argv[1] == "net":
        import json
        for n in sys.argv[2:]:
            print(n, json.dumps([{"reference": p.split(".")[0], "pin_number": p.split(".")[1]} for p in NETS[n]]))
