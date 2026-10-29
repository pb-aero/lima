"""Boom-electret pass-through placement (2026-10-29): seat the 6-pin J7 where the 4-pin was (tangent to the ring,
pads pulled in for edge clearance) and the J12 wire pads in the nearest legal spot of the outer band.
Usage: place_elec.py <board> [J12 angle range lo hi]   KiCad closed, after syncnet added J7/J12 at the centre."""
import sys, os, math, pcbnew
CX, CY, RO, EDGE = 150.0, 100.0, 36.0, 0.55
b = pcbnew.LoadBoard(sys.argv[1]); MM = 1e6
lo, hi = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (240.0, 330.0)
ol = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(ol, False)
def crt(f):
    f.BuildCourtyardCaches(); return pcbnew.SHAPE_POLY_SET(f.GetCourtyard(pcbnew.F_CrtYd))
def copper_r(f):
    w = 0
    for p in f.Pads():
        poly = p.GetEffectivePolygon(pcbnew.F_Cu)
        for i in range(poly.OutlineCount()):
            o = poly.Outline(i)
            for k in range(o.PointCount()):
                q = o.CPoint(k); w = max(w, math.hypot(q.x / MM - CX, q.y / MM - CY))
    return w
def legal(f, others):
    c = crt(f); out = pcbnew.SHAPE_POLY_SET(c); out.BooleanSubtract(ol)
    if out.Area() > 0 or copper_r(f) > RO - EDGE: return False
    for o in others:
        x = pcbnew.SHAPE_POLY_SET(c); x.BooleanIntersection(o)
        if x.Area() > 0: return False
    return True
def seat(f, ang, r):
    a = math.radians(ang); f.SetPosition(pcbnew.VECTOR2I(int((CX + r * math.cos(a)) * MM), int((CY - r * math.sin(a)) * MM)))
    f.SetOrientationDegrees(ang - 270)
def place(ref, angles, radii):
    f = b.FindFootprintByReference(ref)
    others = [crt(g) for g in b.GetFootprints() if g.GetReference() not in (ref, "J7", "J12") or
              (g.GetReference() in ("J7", "J12") and g.GetReference() in done)]
    others = [o for o in others if o.OutlineCount()]
    for ang in angles:
        for r in radii:
            seat(f, ang, r)
            if legal(f, others):
                done.add(ref); print(f"{ref} at {ang:.1f} deg, r {r:.2f}, rot {ang - 270:.1f}, copper r {copper_r(f):.2f}", flush=True)
                return True
    print(ref, "no legal spot", flush=True); return False
done = set()
J7_HOME = 286.25
place("J7", sorted([J7_HOME + d / 10 for d in range(-40, 41)], key=lambda a: abs(a - J7_HOME)),
      [33.6 - k * 0.05 for k in range(0, 60)])
j7 = b.FindFootprintByReference("J7")
pin = {p.GetNumber(): math.degrees(math.atan2(-(p.GetPosition().y / MM - CY), p.GetPosition().x / MM - CX)) % 360 for p in j7.Pads()}
print("J7 pad angles:", {k: round(v, 1) for k, v in sorted(pin.items())}, flush=True)
tgt = (pin["5"] + pin["6"]) / 2
place("J12", sorted([lo + d / 4 for d in range(int((hi - lo) * 4) + 1)], key=lambda a: abs(a - tgt)),
      [34.6 - k * 0.1 for k in range(0, 30)])
pcbnew.SaveBoard(sys.argv[1], b); os._exit(0)
