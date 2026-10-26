"""Scratch-DSN edits for Freerouting (never touches the board). Usage: dsn_tweak.py in.dsn out.dsn

What it does, all relative to what KiCad exported:
- every class clearance 127 -> 130 um and >= 500 um ones +20 um (Freerouting doesn't model hole clearance;
  the margin keeps 0.5/0.25 vias off the 0.25 mm hole rule)
- every class uses 0.5/0.25 vias
- class widths above 300 um capped at 300 um (fine-pitch power pins)
- FINE_NETS (space-separated) moved to their own 200 um class
- PROTECT=1: existing wiring becomes (type protect) so Freerouting leaves hand routes and fanout alone
- ROUTE_LAYERS: power layers listed here (e.g. "In2.Cu") become routable, and their plane is dropped
- PLANE_LAYERS: signal layers listed here become power (plane-only) layers
- EDGE_INSET (mm): boundary pulled toward its centroid, and polygon keepouts (board holes) pushed out from theirs,
  so Freerouting's class clearance to the outline ends up >= the 0.5 mm edge rule (exact for circles/rings)
"""
import sys, os, re
t = open(sys.argv[1]).read()

t = re.sub(r"\(clearance (\d+)\)", lambda m: f"(clearance {130 if int(m.group(1)) <= 130 else int(m.group(1)) + 20})", t)
t = re.sub(r'\(use_via "Via\[0-3\]_\d+:\d+_um"\)', '(use_via "Via[0-3]_500:250_um")', t)
t = re.sub(r"\(width (\d+)\)", lambda m: f"(width {min(int(m.group(1)), 300)})", t)

fine = os.environ.get("FINE_NETS", "").split()
if fine:
    for n in fine:
        t = re.sub(r"(\(class [^()]*?)\s" + re.escape(n) + r"(?=[\s)])", r"\1", t)
    cls = ("    (class Fine " + " ".join(fine) + "\n      (circuit\n        (use_via \"Via[0-3]_500:250_um\")\n"
           "      )\n      (rule\n        (width 200)\n        (clearance 130)\n      )\n    )\n")
    i = t.index("  (wiring"); j = t.rindex("  )\n", 0, i); t = t[:j] + cls + t[j:]

for lay in os.environ.get("ROUTE_LAYERS", "").split():
    i = t.index(f"(layer {lay}"); j = t.index("(type power)", i); t = t[:j] + "(type signal)" + t[j + 12:]
    for m in list(re.finditer(r"\(plane \S+ \(polygon " + re.escape(lay), t))[::-1]:
        k, depth = m.start(), 0
        for e in range(k, len(t)):
            depth += t[e] == "("; depth -= t[e] == ")"
            if depth == 0: break
        t = t[:k] + t[e + 1:]

for lay in os.environ.get("PLANE_LAYERS", "").split():
    i = t.index(f"(layer {lay}"); j = t.index("(type signal)", i); t = t[:j] + "(type power)" + t[j + 13:]

inset = float(os.environ.get("EDGE_INSET", "0")) * 1000   # DSN units are um
def move_poly(m, sign):
    head, nums, tail = m.group(1), m.group(2), m.group(3)
    v = [float(x) for x in nums.split()]
    pts = list(zip(v[0::2], v[1::2])); cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
    out = []
    for x, y in pts:
        d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 or 1
        out += [round(x + sign * inset * (x - cx) / d, 1), round(y + sign * inset * (y - cy) / d, 1)]
    return head + "  ".join(f"{out[k]:g} {out[k+1]:g}" for k in range(0, len(out), 2)) + tail
if inset:
    t = re.sub(r"(\(boundary\s*\(path pcb 0\s+)([-\d.\s]+?)(\))", lambda m: move_poly(m, -1), t, count=1)
    t = re.sub(r'(\(keepout "" \(polygon signal 0\s+)([-\d.\s]+?)(\))', lambda m: move_poly(m, +1), t)

if os.environ.get("PROTECT") == "1":
    t = t.replace("(type route)", "(type protect)").replace("(type fix)", "(type protect)")
open(sys.argv[2], "w").write(t)
