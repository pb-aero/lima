"""GMA match board on 0.1-inch stripboard — layout, and a checker that proves it against design_nets.py.

Strips run left-right and are lettered A.. from the top; holes are numbered 1.. from the left (standard
Veroboard notation). A cut is made AT a hole and removes that hole from the strip. Layout by LIMA,
2026-11-13, for Peter: "can you please show me wiring on vera board".

Through-hole stand-ins for the PCB's SMD parts (same values):
  R7, R8, R10 10k, R9 0R  -> 1/4 W axial, stood upright
  C26 10u, C27 1u         -> radial MLCC (C27's legs bent out to 10.16 mm)
  C37 220n film           -> radial film, 5.08 mm pitch, rated >= 63 V
  D1 BAT54S               -> two discrete small-signal Schottkys, D1A (GND->AIN1) and D1B (AIN1->+3V3A)
  T4 SM-LP-5001 (SMD)     -> on four 0.6 mm tinned-wire legs: its feet are 12.0 mm apart, the grid gives 12.7
  T2, T3 SP-74            -> straight in: pads +/-3.81 x 2.54 mm sit on the grid (from kicad/lib/Triad.pretty)
  J5 JST GH               -> a GH pigtail's four wires soldered into hole 37 of strips B-E

Run:  python3 -I veroboard.py check      (exit 0 = the strips, cuts, links and leads give exactly design_nets.NETS)
      python3 -I veroboard.py json       (layout for docs/gma-match-veroboard.html)
"""
import importlib.util
import json
import os
import sys

COLS, ROWS, OFF = 38, 24, 1          # logical row r is strip letter chr(ord('A') + r + OFF)

# (ref, kind, value, {pin: (col, logical_row)})
PARTS = [
    ("J1", "header", "1x8 pin header · codec", {str(i + 1): (2, 2 + i) for i in range(8)}),
    ("J2", "header", "1x4 pin header · panel bench (pin 1 at the bottom)", {"1": (33, 4), "2": (33, 3), "3": (33, 2), "4": (33, 1)}),
    ("J5", "pigtail", "JST GH 4-way pigtail · panel harness", {"1": (36, 4), "2": (36, 3), "3": (36, 2), "4": (36, 1)}),
    ("J3", "header", "1x2 pin header · cup L driver", {"1": (31, 14), "2": (31, 15)}),
    ("J4", "header", "1x2 pin header · cup R driver", {"1": (31, 20), "2": (31, 21)}),
    ("T4", "lp5001", "Bourns SM-LP-5001 · 600:600 on wire legs", {"1": (14, 1), "2": (14, 3), "4": (19, 1), "3": (19, 3)}),
    ("T2", "sp74", "Triad SP-74 · cup L", {"1": (22, 11), "2": (25, 11), "3": (22, 12), "4": (25, 12), "5": (22, 13), "6": (25, 13)}),
    ("T3", "sp74", "Triad SP-74 · cup R", {"1": (22, 17), "2": (25, 17), "3": (22, 18), "4": (25, 18), "5": (22, 19), "6": (25, 19)}),
    ("R10", "res", "10 kΩ ¼ W", {"1": (21, 3), "2": (21, 0)}),
    ("C37", "film", "220 nF film ≥63 V, 5.08 mm", {"1": (26, 0), "2": (26, 2)}),
    ("R7", "res", "10 kΩ ¼ W", {"1": (17, 12), "2": (17, 9)}),
    ("R8", "res", "10 kΩ ¼ W", {"1": (15, 9), "2": (15, 8)}),
    ("R9", "res", "0 Ω (or a wire link)", {"1": (18, 15), "2": (18, 16)}),
    ("C27", "mlcc", "1 µF MLCC, legs to 10.16 mm", {"1": (13, 9), "2": (13, 5)}),
    ("C26", "mlcc", "10 µF MLCC", {"1": (7, 6), "2": (7, 8)}),
    ("D1A", "diode", "Schottky, half of D1 (GND → AIN1)", {"A": (9, 8), "K": (9, 5)}),
    ("D1B", "diode", "Schottky, half of D1 (AIN1 → +3V3A)", {"A": (11, 5), "K": (11, 7)}),
]
PIN_MAP = {"D1A.A": "D1.1", "D1A.K": "D1.3", "D1B.A": "D1.3", "D1B.K": "D1.2"}

LINKS = [((4, 2), (4, 1)), ((5, 4), (5, 8)), ((14, 8), (14, 16)),
         ((20, 4), (20, 11)), ((21, 11), (21, 17)), ((35, 3), (35, 11)), ((28, 11), (28, 17)),
         ((20, 12), (20, 13)), ((27, 12), (27, 13)), ((18, 13), (18, 14)), ((26, 13), (26, 15)),
         ((20, 18), (20, 19)), ((27, 18), (27, 19)), ((18, 19), (18, 20)), ((26, 19), (26, 21))]

CUTS = {1: [16], 2: [5, 24], 3: [16, 24], 4: [12], 5: [14], 6: [8], 7: [12], 8: [19], 9: [19],
        11: [19, 23], 12: [16, 23], 13: [16, 23], 14: [16], 15: [16], 16: [20], 17: [19, 23],
        18: [16, 23], 19: [16, 23], 20: [16], 21: [16]}

MOUNT = [(0, -1), (37, -1), (0, 22), (37, 22)]   # M3 holes in the empty top and bottom strips


def hole(c, r):
    return f"{chr(ord('A') + r + OFF)}{c + 1}"


def segments():
    """Every strip segment: (row, first_col, last_col)."""
    segs = []
    for r in range(-OFF, ROWS - OFF):
        cuts = sorted(CUTS.get(r, []))
        start = 0
        for c in cuts + [COLS]:
            if c > start:
                segs.append((r, start, c - 1))
            start = c + 1
    return segs


def seg_of(c, r, segs):
    for s in segs:
        if s[0] == r and s[1] <= c <= s[2]:
            return s
    return None


def load_design():
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location("design_nets", os.path.join(here, "design_nets.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.NETS


def check():
    segs, bad = segments(), 0
    # 1. every hole used once, nothing on a cut, everything on the board
    used = {}
    holes = [((c, r), f"{ref}.{p}") for ref, _, _, pins in PARTS for p, (c, r) in pins.items()]
    holes += [(a, f"link{i}") for i, (a, b) in enumerate(LINKS)] + [(b, f"link{i}") for i, (a, b) in enumerate(LINKS)]
    for (c, r), who in holes:
        if not (0 <= c < COLS and -OFF <= r < ROWS - OFF):
            bad += 1; print("off board:", who, hole(c, r))
        if c in CUTS.get(r, []):
            bad += 1; print("on a cut:", who, hole(c, r))
        if (c, r) in used:
            bad += 1; print("hole used twice:", hole(c, r), used[(c, r)], who)
        used[(c, r)] = who
    # 2. links are straight vertical runs; vertical items in one column must not overlap
    spans = []
    for i, (a, b) in enumerate(LINKS):
        if a[0] != b[0]:
            bad += 1; print("link not vertical:", i)
        spans.append((a[0], min(a[1], b[1]), max(a[1], b[1]), f"link {hole(*a)}-{hole(*b)}"))
    for ref, kind, _, pins in PARTS:
        cols = {}
        for c, r in pins.values():
            cols.setdefault(c, []).append(r)
        for c, rs in cols.items():
            spans.append((c, min(rs), max(rs), ref))
    for i, s in enumerate(spans):
        for t in spans[i + 1:]:
            if s[0] == t[0] and s[1] <= t[2] and t[1] <= s[2]:
                bad += 1; print("overlap in column", s[0] + 1, ":", s[3], "and", t[3])
    # 3. connectivity: union-find over strip segments joined by links
    parent = {s: s for s in segs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in LINKS:
        sa, sb = seg_of(*a, segs), seg_of(*b, segs)
        parent[find(sa)] = find(sb)
    pin_node = {}
    for ref, _, _, pins in PARTS:
        for p, (c, r) in pins.items():
            pin_node.setdefault(PIN_MAP.get(f"{ref}.{p}", f"{ref}.{p}"), set()).add(find(seg_of(c, r, segs)))
    for p, nodes in pin_node.items():
        if len(nodes) > 1:
            bad += 1; print("split pin (D1 halves not joined):", p)
    node_pins = {}
    for p, nodes in pin_node.items():
        node_pins.setdefault(next(iter(nodes)), set()).add(p)
    design = load_design()
    want = {frozenset(v) for v in design.values()}
    got = {frozenset(v) for v in node_pins.values()}
    for s in sorted(want - got, key=sorted):
        bad += 1; print("design net not built as one strip group:", sorted(s))
    for s in sorted(got - want, key=sorted):
        bad += 1; print("built group that is not a design net:", sorted(s))
    print(f"{len(segs)} segments, {sum(len(v) for v in CUTS.values())} cuts, {len(LINKS)} links, "
          f"{len(PARTS)} parts")
    print("OK — stripboard connectivity == design_nets.NETS" if not bad else f"{bad} problem(s)")
    return bad, find, segs, design


def to_json():
    bad, find, segs, design = check()
    if bad:
        sys.exit(1)
    pin2net = {p: n for n, ps in design.items() for p in ps}
    seg_net = {}
    for ref, _, _, pins in PARTS:
        for p, (c, r) in pins.items():
            seg_net[find(seg_of(c, r, segs))] = pin2net[PIN_MAP.get(f"{ref}.{p}", f"{ref}.{p}")]
    out = {
        "cols": COLS, "rows": ROWS,
        "segments": [{"row": r + OFF, "c0": a, "c1": b, "net": seg_net.get(find((r, a, b)))} for r, a, b in segs],
        "cuts": [{"row": r + OFF, "col": c, "hole": hole(c, r)} for r, cs in sorted(CUTS.items()) for c in cs],
        "links": [{"a": [a[0], a[1] + OFF], "b": [b[0], b[1] + OFF], "from": hole(*a), "to": hole(*b),
                   "net": seg_net.get(find(seg_of(*a, segs)))} for a, b in LINKS],
        "parts": [{"ref": ref, "kind": kind, "value": val,
                   "pins": {p: {"c": c, "r": r + OFF, "hole": hole(c, r),
                                "net": pin2net[PIN_MAP.get(f"{ref}.{p}", f"{ref}.{p}")]} for p, (c, r) in pins.items()}}
                  for ref, kind, val, pins in PARTS],
        "mount": [{"c": c, "r": r + OFF} for c, r in MOUNT],
    }
    print(json.dumps(out, separators=(",", ":"), ensure_ascii=False), file=sys.stderr)


if __name__ == "__main__":
    if sys.argv[1] == "check":
        sys.exit(1 if check()[0] else 0)
    if sys.argv[1] == "json":
        to_json()
