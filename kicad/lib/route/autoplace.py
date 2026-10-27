"""Put a footprint at the nearest courtyard-legal spot to a target point (inside the board, overlapping nothing).
Usage: autoplace.py <board> REF X Y [--r 4] [--angles a,b,...] [--pad N --toward X,Y]
  --pad N --toward X,Y : among legal spots prefer orientations that put pad N closest to (X,Y)
Moves one footprint per call and saves.  Run with KiCad closed."""
import sys, os, math, pcbnew
args = sys.argv[1:]; path, ref, tx, ty = args[0], args[1], float(args[2]), float(args[3]); rest = args[4:]
R, angles, padn, toward = 4.0, None, None, None
while rest:
    k = rest.pop(0)
    if k == "--r": R = float(rest.pop(0))
    elif k == "--angles": angles = [float(a) for a in rest.pop(0).split(",")]
    elif k == "--pad": padn = rest.pop(0)
    elif k == "--toward": toward = tuple(float(v) for v in rest.pop(0).split(","))
b = pcbnew.LoadBoard(path); F = pcbnew.FromMM
f = b.FindFootprintByReference(ref)
ol = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(ol, False)
others = []
for g in b.GetFootprints():
    if g.GetReference() == ref: continue
    c = g.GetCourtyard(pcbnew.F_CrtYd)
    if c.OutlineCount(): others.append(pcbnew.SHAPE_POLY_SET(c))
if angles is None: angles = [f.GetOrientationDegrees() + a for a in range(0, 360, 45)]
def legal():
    f.BuildCourtyardCaches()
    c = pcbnew.SHAPE_POLY_SET(f.GetCourtyard(pcbnew.F_CrtYd))
    out = pcbnew.SHAPE_POLY_SET(c); out.BooleanSubtract(ol)
    if out.Area() > 0: return False
    for o in others:
        x = pcbnew.SHAPE_POLY_SET(c); x.BooleanIntersection(o)
        if x.Area() > 0: return False
    return True
best = None
step = 0.1
for ir in range(0, int(R / step) + 1):
    r = ir * step; nth = max(1, int(2 * math.pi * r / step))
    for k in range(nth):
        x, y = tx + r * math.cos(2 * math.pi * k / nth), ty + r * math.sin(2 * math.pi * k / nth)
        for a in angles:
            f.SetPosition(pcbnew.VECTOR2I(F(x), F(y))); f.SetOrientationDegrees(a)
            if not legal(): continue
            score = r
            if padn and toward:
                pp = [p.GetPosition() for p in f.Pads() if p.GetNumber() == padn][0]
                score = r + math.hypot(pp.x / 1e6 - toward[0], pp.y / 1e6 - toward[1])
            if best is None or score < best[0]: best = (score, x, y, a)
    if best and r > best[0] + 0.5: break     # rings beyond the best score can't beat it
if not best: print(ref, "no legal spot within", R, "mm", flush=True); os._exit(1)
_, x, y, a = best
f.SetPosition(pcbnew.VECTOR2I(F(x), F(y))); f.SetOrientationDegrees(a)
pcbnew.SaveBoard(path, b)
print(f"{ref} -> ({x:.2f}, {y:.2f}) r{a:.0f}", " ".join(f"{p.GetNumber()}:{p.GetNetname()}@({p.GetPosition().x/1e6:.2f},{p.GetPosition().y/1e6:.2f})" for p in f.Pads()), flush=True)
os._exit(0)
