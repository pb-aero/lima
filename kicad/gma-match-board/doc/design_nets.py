"""GMA match board — intended connectivity, the source of truth the schematic is checked against.

A bench breakout of the audio board's ADAU1372 <-> GMA 245R matching networks, both directions, with
K1 (U10/U11 AQW612S) and the failsafe electret left out (Peter, 2026-11-13). Reference designators,
values and footprints are carried over from kicad/audio-board (doc/design_nets.py there) so a result
measured here maps one-to-one onto that board.

  TX  ADAU1372 HPOUTL+/- (DAC_P/N) -> T4 SM-LP-5001 -> R10 10k -> C37 220n film -> MIC_HI / MIC_LO
      (audio board: PV_OUT -> U10 K1 -> MIC_HI, PV_RTN -> U11 K1 -> MIC_LO; here K1 is a straight wire)
  RX  EAR_HI / EAR_RTN -> T2 + T3 SP-74 primaries in parallel -> T2 secondary SPK_L_A -> R7/R8 10k/10k
      -> COMMS_TAP -> C27 1u -> AIN1, clamped by D1 BAT54S to GND / +3V3A; C26 10u on AIN1REF

Every pin of every part appears either in NETS or in NC. Run:  python3 -I design_nets.py check <netlist.xml>
"""
import sys

NETS = {
    # ---- codec side: J1, 2.54 mm 1x8, jumper wires to the ADAU1372 (EVB J13/J16, AVDD, AIN1) ----
    "GND": ["J1.3", "J1.7", "R8.2", "R9.2", "D1.1", "C26.2"],
    "+3V3A": ["J1.6", "D1.2"],                 # clamp rail only — take it from the codec's AVDD
    "DAC_P": ["J1.1", "T4.1"],
    "DAC_N": ["J1.2", "T4.2"],
    "AIN1": ["J1.4", "C27.2", "D1.3"],
    "AIN1REF": ["J1.5", "C26.1"],
    "COMMS_TAP": ["J1.8", "R7.2", "R8.1", "C27.1"],
    # ---- TX: PureVoice out (audio board ruling 10) ----
    "PV_SEC": ["T4.3", "R10.1"],
    "PV_ATT": ["R10.2", "C37.1"],
    # ---- aircraft side: J5 = same JST GH 4-pin and pinout as the audio board's J5; J2 = 2.54 mm twin ----
    "EAR_HI": ["J5.1", "J2.1", "T2.1", "T3.1"],
    "EAR_RTN": ["J5.2", "J2.2", "T2.2", "T3.2"],
    "MIC_HI": ["J5.3", "J2.3", "C37.2"],
    "MIC_LO": ["J5.4", "J2.4", "T4.4"],
    # ---- SP-74 secondaries (paralleled 3/5 and 4/6, as on the audio board) -> cup drivers ----
    "SPK_L_A": ["T2.3", "T2.5", "J3.1", "R7.1"],
    "SPK_L_B": ["T2.4", "T2.6", "J3.2", "R9.1"],
    "SPK_R_A": ["T3.3", "T3.5", "J4.1"],
    "SPK_R_B": ["T3.4", "T3.6", "J4.2"],
}

NC = []

AIRCRAFT = ["EAR_HI", "EAR_RTN", "MIC_HI", "MIC_LO", "PV_SEC", "PV_ATT",
            "SPK_L_A", "SPK_L_B", "SPK_R_A", "SPK_R_B"]   # 0.5 mm netclass, as on the audio board


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
        wrong = {p: pin2net.get(p) for p in pins if pin2net.get(p) != net}
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
