"""Plane fanout: a via + stub for every F.Cu SMD pad on a plane net (FANOUT_NETS, default /GND,/+3V3).
AIRCRAFT_NETS (space-separated) get 0.5 mm clearance. Board edge = real outline (works for rings).
Large pads (EPs) get a grid of vias inside the pad. FANOUT_PADS=REF.PAD,... limits it to those pads. Run with KiCad closed."""
import sys, math, pcbnew
MM = 1e6
import os
PLANES = set(os.environ.get("FANOUT_NETS", "/GND,/+3V3").split(","))
AIRCRAFT = set(os.environ.get("AIRCRAFT_NETS", "").split())
ONLY = set(os.environ.get("FANOUT_PADS", "").split(",")) - {""}   # REF.PAD,... = fan out just these (repairs)
VIA_D, VIA_DRILL = int(0.5*MM), int(0.25*MM)
CL, HOLE_CL, EDGE_CL = int(0.15*MM), int(0.28*MM), int(0.55*MM)   # a hair over the rules
def clr(net): return int(0.5*MM) if net in AIRCRAFT else CL

b = pcbnew.LoadBoard(sys.argv[1])
_ol = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(_ol, False)
SAFE = pcbnew.SHAPE_POLY_SET(_ol); SAFE.Deflate(EDGE_CL + VIA_D//2, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, 5000)
obst = []   # (net, kind, geom) kind: 'poly' (SHAPE_POLY_SET) | 'circle' (center, r) | 'seg' (SEG, halfwidth)
holes = []  # (center, r) every drilled hole
pads = []
for f in b.GetFootprints():
    for p in f.Pads():
        if p.HasHole():
            holes.append((p.GetPosition(), max(p.GetDrillSize().x, p.GetDrillSize().y)//2))
        if not p.IsOnLayer(pcbnew.F_Cu): continue
        poly = p.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_OUTSIDE)
        obst.append((p.GetNetname(), 'poly', poly, p))
        pads.append((f, p, poly))

PLANE_OUTLINE = {z.GetNetname(): z.Outline() for z in b.Zones() if z.GetNetname() in PLANES}
for tr in b.GetTracks():
    if tr.GetClass() == "PCB_VIA":
        obst.append((tr.GetNetname(), 'circle', (tr.GetPosition(), tr.GetWidth(pcbnew.F_Cu)//2), tr)); holes.append((tr.GetPosition(), tr.GetDrillValue()//2))
    else:
        obst.append((tr.GetNetname(), 'bseg' if tr.GetLayer() != pcbnew.F_Cu else 'seg', (pcbnew.SEG(tr.GetStart(), tr.GetEnd()), tr.GetWidth()//2), tr))

def dist_pt_seg(c, s):
    ax, ay, bx, by = s.A.x, s.A.y, s.B.x, s.B.y
    dx, dy = bx-ax, by-ay; L = dx*dx+dy*dy
    t = 0 if L == 0 else max(0, min(1, ((c.x-ax)*dx+(c.y-ay)*dy)/L))
    return math.hypot(c.x-(ax+t*dx), c.y-(ay+t*dy))

def via_ok(c, net, skip):
    r = VIA_D//2
    if not SAFE.Contains(c): return False
    for hc, hr in holes:
        if math.hypot(c.x-hc.x, c.y-hc.y) < hr + r + HOLE_CL: return False
    for onet, kind, g, owner in obst:
        if owner is skip: continue
        if onet == net and kind != 'circle': continue          # same-net copper may touch
        cl = max(clr(net), clr(onet)) if onet != net else int(0.2*MM)
        if kind == 'poly' and g.Collide(c, r+cl): return False
        if kind == 'circle' and math.hypot(c.x-g[0].x, c.y-g[0].y) < g[1]+r+cl: return False
        if kind in ('seg', 'bseg') and dist_pt_seg(c, g[0]) < g[1]+r+cl: return False
    o = PLANE_OUTLINE[net]
    return _inside(o, c)

def _inside(o, c):
    return all(o.Contains(pcbnew.VECTOR2I(c.x+dx, c.y+dy)) for dx, dy in ((500000,0),(-500000,0),(0,500000),(0,-500000)))

def seg_ok(s, hw, net, skip):
    for onet, kind, g, owner in obst:
        if owner is skip or onet == net: continue
        cl = max(clr(net), clr(onet))
        if kind == 'poly' and g.Collide(s, hw+cl): return False
        if kind == 'circle' and dist_pt_seg(g[0], s) < g[1]+hw+cl: return False
        if kind == 'seg':
            # sample both ways (segments are short)
            for k in range(11):
                t = k/10; q = pcbnew.VECTOR2I(int(s.A.x+t*(s.B.x-s.A.x)), int(s.A.y+t*(s.B.y-s.A.y)))
                if dist_pt_seg(q, g[0]) < g[1]+hw+cl: return False
    return True

def add_via(c, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(c); v.SetWidth(VIA_D); v.SetDrill(VIA_DRILL)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(b.FindNet(net)); b.Add(v)
    obst.append((net, 'circle', (c, VIA_D//2), v)); holes.append((c, VIA_DRILL//2))

def add_track(a, c, w, net):
    t = pcbnew.PCB_TRACK(b); t.SetStart(a); t.SetEnd(c); t.SetWidth(w); t.SetLayer(pcbnew.F_Cu)
    t.SetNet(b.FindNet(net)); b.Add(t); obst.append((net, 'seg', (pcbnew.SEG(a, c), w//2), t))

done = fail = ep = 0; failed = []
for f, p, poly in pads:
    net = p.GetNetname()
    if net not in PLANES or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD: continue
    if ONLY and f"{f.GetReference()}.{p.GetNumber()}" not in ONLY: continue
    sz = p.GetSize(pcbnew.F_Cu); bb = poly.BBox()
    if min(sz.x, sz.y) >= 1.5*MM:   # exposed pad: via grid inside
        pitch = int(1.0*MM); m = int(0.45*MM)
        nx = max(1, int((bb.GetWidth()-2*m)//pitch)+1); ny = max(1, int((bb.GetHeight()-2*m)//pitch)+1)
        x0 = bb.Centre().x-(nx-1)*pitch//2; y0 = bb.Centre().y-(ny-1)*pitch//2
        for i in range(nx):
            for j in range(ny):
                c = pcbnew.VECTOR2I(x0+i*pitch, y0+j*pitch)
                if poly.Contains(c) and via_ok(c, net, p): add_via(c, net); ep += 1
        continue
    pc = p.GetPosition(); fc = f.GetPosition()
    out = math.atan2(pc.y-fc.y, pc.x-fc.x) if (pc.x, pc.y) != (fc.x, fc.y) else 0
    w = int(min(0.3*MM, min(sz.x, sz.y)*0.8))
    angs = sorted((out + math.radians(a) for a in range(0, 360, 15)), key=lambda a: abs(math.remainder(a-out, 2*math.pi)))
    best = None
    for d10 in range(4, 22):               # 0.4 .. 2.1 mm from the pad centre
        d = d10*0.1*MM
        for a in angs:
            c = pcbnew.VECTOR2I(int(pc.x+d*math.cos(a)), int(pc.y+d*math.sin(a)))
            if via_ok(c, net, p) and seg_ok(pcbnew.SEG(pc, c), w//2, net, p):
                best = c; break
        if best: break
    if best:
        add_via(best, net); add_track(pc, best, w, net); done += 1
    else:
        fail += 1; failed.append(f"{f.GetReference()}.{p.GetNumber()}({net})")
pcbnew.SaveBoard(sys.argv[1], b)
print(f"fanned {done} pads, {ep} EP vias, failed {fail}: {' '.join(failed)}", flush=True); os._exit(0)
