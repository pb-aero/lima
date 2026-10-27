"""Seat decoupling caps at their IC pins: each cap end-on (radial) to its pin, net pad nearest, at the closest
courtyard-legal spot just outside the IC.  End-on caps block ~1 mm of the IC's face instead of a whole side.
Usage: decaps.py <board> IC CAP:PIN [CAP:PIN ...] [--gap 0.5] [--r 3]   Run with KiCad closed."""
import sys, os, math, pcbnew
args = sys.argv[1:]; path, icref = args[0], args[1]; GAP, R = 0.5, 3.0; jobs = []
rest = args[2:]
while rest:
    a = rest.pop(0)
    if a == "--gap": GAP = float(rest.pop(0))
    elif a == "--r": R = float(rest.pop(0))
    else: jobs.append(a.split(":"))
b = pcbnew.LoadBoard(path); F = pcbnew.FromMM; MM = 1e6
ic = b.FindFootprintByReference(icref); icc = ic.GetPosition()
ol = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(ol, False)
ic.BuildCourtyardCaches(); icbb = ic.GetCourtyard(pcbnew.F_CrtYd).BBox()
def courtyard(f):
    f.BuildCourtyardCaches(); return pcbnew.SHAPE_POLY_SET(f.GetCourtyard(pcbnew.F_CrtYd))
def legal(f, others):
    c = courtyard(f); out = pcbnew.SHAPE_POLY_SET(c); out.BooleanSubtract(ol)
    if out.Area() > 0: return False
    for o in others:
        x = pcbnew.SHAPE_POLY_SET(c); x.BooleanIntersection(o)
        if x.Area() > 0: return False
    return True
for capref, pin in jobs:
    cap = b.FindFootprintByReference(capref)
    home, home_a = cap.GetPosition(), cap.GetOrientationDegrees()
    pp = [p for p in ic.Pads() if p.GetNumber() == pin][0]; px, py = pp.GetPosition().x / MM, pp.GetPosition().y / MM
    net = pp.GetNetname(); cpad = [p for p in cap.Pads() if p.GetNetname() == net][0].GetNumber()
    # outward normal of the pin's face: from the IC centre, snapped to the IC's own axes
    ang = math.radians(-ic.GetOrientationDegrees()); ux, uy = math.cos(ang), math.sin(ang)
    vx, vy = px - icc.x / MM, py - icc.y / MM
    a1, a2 = vx * ux + vy * uy, -vx * uy + vy * ux
    nx, ny = (ux, uy) if abs(a1) >= abs(a2) else (-uy, ux)
    if (vx * nx + vy * ny) < 0: nx, ny = -nx, -ny
    near = lambda g: math.hypot(g.GetPosition().x / MM - px, g.GetPosition().y / MM - py) < R + 9
    others = [courtyard(g) for g in b.GetFootprints() if g.GetReference() != capref and near(g) and g.GetCourtyard(pcbnew.F_CrtYd).OutlineCount()]
    radial = math.degrees(math.atan2(-ny, nx))          # KiCad angles are CCW with y down
    best = None
    for dist in [x * 0.1 for x in range(int((GAP + 0.6) * 10), int((GAP + 0.6 + R) * 10))]:
        for side in [0] + [s * k * 0.1 for k in range(1, 31) for s in (1, -1)]:
            x = px + nx * dist - ny * side; y = py + ny * dist + nx * side
            for a in (radial, radial + 180, radial + 90, radial - 90):
                cap.SetPosition(pcbnew.VECTOR2I(F(x), F(y))); cap.SetOrientationDegrees(a)
                if not legal(cap, others): continue
                cp = [p for p in cap.Pads() if p.GetNumber() == cpad][0].GetPosition()
                d = math.hypot(cp.x / MM - px, cp.y / MM - py)
                score = d + (0 if a in (radial, radial + 180) else 1.0)    # prefer end-on
                if best is None or score < best[0]: best = (score, x, y, a, d)
        if best and dist > best[4] + 1.5: break
    if not best:
        cap.SetPosition(home); cap.SetOrientationDegrees(home_a)   # leave it where it was
        print(capref, "no legal spot (left in place)", flush=True); continue
    _, x, y, a, d = best
    cap.SetPosition(pcbnew.VECTOR2I(F(x), F(y))); cap.SetOrientationDegrees(a)
    print(f"{capref} -> ({x:.2f},{y:.2f}) r{a:.0f}, {net} pad {d:.2f} mm from {icref}.{pin}", flush=True)
pcbnew.SaveBoard(path, b); os._exit(0)
