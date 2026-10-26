"""Cup board with its A2B sub-node (2026-10-23) — intended connectivity. Built from the cup board netlist at
commit b641179 (before the A2B node) plus the edits listed in kicad/cup-board/README.md "A2B sub-node".
Run:  python3 -I design_nets.py check <netlist.xml>
"""
import sys

NETS = {'1V8': ['C1.1',
         'C11.1',
         'C2.1',
         'C3.1',
         'C4.1',
         'C5.1',
         'MK3.2',
         'R1.2',
         'R2.2',
         'R3.1',
         'U1.15',
         'U1.27',
         'U1.38',
         'U1.39',
         'U1.45',
         'U1.51',
         'U1.28',     # REG_EN tied to AVDD: internal DVDD regulator on (2026-10-26, DVDD abs max 1.21 V)
         'U1.56',
         'U2.12',
         'U2.5',
         'U2.8',
         'U3.3',
         'U7.6',
         'L9.2',
         'C42.1',
         'U6.9',
         'C40.1'],
 '3V3_MIC': ['MK1.2', 'MK2.2', 'U8.4', 'U8.5', 'C44.1'],
 # ADAU1861 internal regulator output; DS pin 54: "decouple DVDD to DGND with a 1 uF and 0.1 uF capacitor"
 'U1_DVDD': ['U1.54', 'C47.1', 'C48.1'],
 'ADC2_N': ['R5.2', 'R6.2', 'U1.23'],
 'ADC2_P': ['R4.2', 'R6.1', 'U1.24'],
 'DMIC_CLK': ['MK3.3', 'U1.7'],
 'DMIC_DATA': ['MK3.1', 'U1.1'],
 'GND': ['C1.2',
         'C11.2',
         'C2.2',
         'C3.2',
         'C4.2',
         'C5.2',
         'C6.2',
         'C7.2',
         'C8.2',
         'MK1.4',
         'MK1.5',
         'MK2.4',
         'MK2.5',
         'MK3.4',
         'MK3.5',
         'U1.11',
         'U1.16',
         'U1.26',
         'C47.2',
         'C48.2',
         'U1.37',
         'U1.46',
         'U1.5',
         'U1.55',
         'U1.65',
         'U1.9',
         'U2.1',
         'U2.6',
         'U2.7',
         'U2.9',
         'U3.10',
         'U3.11',
         'U3.9',
         'U6.7',
         'U6.8',
         'U6.25',
         'U6.31',
         'U6.33',
         'L4.2',
         'U7.1',
         'U7.4',
         'U7.5',
         'U7.9',
         'U8.2',
         'U9.2',
         'Q2.2',
         'R18.2',
         'C12.2',
         'C14.2',
         'C15.2',
         'C16.2',
         'C17.2',
         'C20.2',
         'C21.2',
         'C23.2',
         'C24.2',
         'C28.2',
         'C29.2',
         'C32.2',
         'C33.2',
         'C35.2',
         'C36.2',
         'C37.2',
         'C38.2',
         'C39.2',
         'C40.2',
         'C41.2',
         'C42.2',
         'C43.2',
         'C44.2',
         'C45.2',
         'C46.2'],
 'HPOUTN': ['U1.35', 'U4.5'],
 'HPOUTP': ['U1.36', 'U5.5'],
 'I2S0_BCLK': ['U1.50', 'U6.10'],
 'I2S0_FSYNC': ['U1.49', 'U6.11'],
 'I2S0_SDATAI': ['U1.41', 'U6.12'],
 'I2S0_SDATAO': ['U1.44', 'U6.14'],
 'PPG_INT': ['R3.2', 'U3.14'],
 'PPG_VLDO': ['C7.1', 'U3.4'],
 'PPG_VREF': ['C8.1', 'U3.12'],
 'SCL': ['R1.1', 'U1.4', 'U2.13', 'U3.2', 'U6.4'],
 'SDA': ['R2.1', 'U1.2', 'U2.14', 'U3.1', 'U6.5'],
 'SPKR_1': ['J2.1', 'U4.6', 'U4.8'],
 'SPKR_2': ['J2.2', 'U5.6', 'U5.8'],
 'TDM_BCLK': ['U1.59', 'U2.3'],
 'TDM_DATA': ['U1.58', 'U2.2'],
 'TDM_WCLK': ['U1.52', 'U2.11'],
 'VLED': ['C6.1', 'U3.5', 'U9.4', 'U9.5', 'C46.1'],
 'XF_SEC_A': ['C9.1', 'J5.1', 'U4.7'],
 'XF_SEC_B': ['C10.1', 'J5.2', 'U5.7'],
 'Net-(C9-Pad2)': ['C9.2', 'R4.1'],
 'Net-(C10-Pad2)': ['C10.2', 'R5.1'],
 'Net-(MK1-OUT+)': ['MK1.1', 'U1.20'],
 'Net-(MK1-OUT-)': ['MK1.3', 'U1.19'],
 'Net-(MK2-OUT+)': ['MK2.1', 'U1.22'],
 'Net-(MK2-OUT-)': ['MK2.3', 'U1.21'],
 'Net-(U4-NC_LED_A)': ['R7.2', 'U4.1'],
 'Net-(U4-NC_LED_K)': ['U4.2', 'U4.3'],
 'Net-(U5-NC_LED_A)': ['R8.2', 'U5.1'],
 'Net-(U5-NC_LED_K)': ['U5.2', 'U5.3'],
 'A_AP': ['U6.19', 'FB1.1', 'C13.1', 'L1.1'],
 'A_AN': ['U6.18', 'FB2.2', 'C13.2', 'L2.1'],
 'A_ACM': ['U6.17', 'FB1.2', 'FB2.1', 'C12.1'],
 'A_APF': ['L1.2', 'C14.1', 'FL1.1'],
 'A_ANF': ['L2.2', 'C15.1', 'FL1.3'],
 'A_APT': ['FL1.2', 'R9.1', 'C18.1'],
 'A_ANT': ['FL1.4', 'R10.2', 'C19.1'],
 'A_TCT': ['R9.2', 'R10.1', 'C16.1', 'C17.1'],
 'A_LINE_P': ['C18.2', 'L3.1', 'C20.1', 'C22.1', 'J7.1'],
 'A_LINE_N': ['C19.2', 'L4.1', 'C21.1', 'C22.2', 'J7.2'],
 'V_NODE': ['L3.2', 'D1.2', 'R11.1', 'C25.1', 'R12.1', 'C24.1'],
 'VIN_CUP': ['D1.1',
             'C23.1',
             'U6.30',
             'C35.1',
             'U7.2',
             'U7.3',
             'C41.1',
             'U8.1',
             'U8.3',
             'C43.1',
             'U9.1',
             'U9.3',
             'C45.1',
             'R7.1',
             'R8.1'],
 'B_GATE': ['R11.2', 'C25.2', 'Q1.1', 'R13.2', 'C26.1'],
 'B_QS': ['R12.2', 'Q1.2'],
 'B_BIASP': ['Q1.3', 'C26.2', 'R14.1', 'L5.1'],
 'B_SWP': ['U6.27', 'R13.1'],
 'B_SENSE': ['U6.28', 'R14.2'],
 'B_VSSN': ['U6.26', 'L6.2'],
 'B_BP': ['U6.22', 'FB3.1', 'C27.1', 'L7.1'],
 'B_BN': ['U6.23', 'FB4.2', 'C27.2', 'L8.1'],
 'B_BCM': ['U6.24', 'FB3.2', 'FB4.1'],
 'B_BPF': ['L7.2', 'C28.1', 'FL2.1'],
 'B_BNF': ['L8.2', 'FL2.3'],
 'B_BPT': ['FL2.2', 'R15.1', 'C30.1'],
 'B_BNT': ['FL2.4', 'R16.2', 'C31.1'],
 'B_TCT': ['R15.2', 'R16.1', 'C29.1'],
 'B_LINE_P': ['C30.2', 'L5.2', 'C32.1', 'C34.1', 'J8.1'],
 'B_LINE_N': ['C31.2', 'L6.1', 'C33.1', 'C34.2', 'J8.2'],
 'A2B_VOUT1': ['U6.32', 'U6.1', 'U6.2', 'U6.3', 'C36.1', 'C37.1'],
 'A2B_VOUT2': ['U6.29', 'U6.20', 'U6.21', 'C38.1', 'C39.1'],
 'K2_CTL': ['U6.16', 'R17.1'],
 'K2_B': ['R17.2', 'R18.1', 'Q2.1'],
 'K2_SW': ['U4.4', 'U5.4', 'Q2.3'],
 'SW1V8': ['U7.7', 'L9.1']}

NC = ['U1.25',
 'U1.8',
 'U1.43',
 'U1.17',
 'U1.18',
 'U1.29',
 'U1.30',
 'U1.31',
 'U1.32',
 'U1.33',
 'U1.34',
 'U1.47',
 'U1.48',
 'U1.3',
 'U1.14',
 'U1.6',
 'U1.10',
 'U1.13',
 'U1.12',
 'U1.53',
 'U1.57',
 'U1.64',
 'U1.61',
 'U1.60',
 'U1.40',
 'U1.42',
 'U1.63',
 'U1.62',
 'U2.4',
 'U2.10',
 'U3.13',
 'U3.8',
 'U3.7',
 'U3.6',
 'U6.6',
 'U6.13',
 'U6.15',
 'U7.8']


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
