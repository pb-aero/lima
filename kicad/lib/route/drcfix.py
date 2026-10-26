"""Rip the unlocked tracks/vias a DRC report blames, then strip the dangling stubs they leave.
Usage: drcfix.py <board> <drc.rpt>    -> follow with maze.py on a fresh DRC report.
Run with KiCad closed."""
import sys, os, re, math, pcbnew

RIP = ("copper_edge_clearance", "hole_clearance", "track_width", "clearance", "via_dangling",
       "track_dangling", "holes_co_located", "hole_to_hole", "shorting_items", "tracks_crossing")
MM = 1e6
# strip dangling: a segment end must land on a pad, a via or another segment end of its net (same layer)
def end_ok(t, e, segs, vias, pads):
    L = t.GetLayer()
    if any(p.IsOnLayer(L) and p.GetEffectivePolygon(L, pcbnew.ERROR_OUTSIDE).Collide(e, 1000) for p in pads.get(t.GetNetname(), [])): return True
    if any(math.hypot(e.x - v.GetPosition().x, e.y - v.GetPosition().y) <= v.GetWidth(pcbnew.F_Cu) / 2 for v in vias.get(t.GetNetname(), [])): return True
    return any(s is not t and s.GetLayer() == L and (math.hypot(s.GetStart().x - e.x, s.GetStart().y - e.y) < 2000 or
               math.hypot(s.GetEnd().x - e.x, s.GetEnd().y - e.y) < 2000) for s in segs.get(t.GetNetname(), []))
def strip_once(path, touched):
    b = pcbnew.LoadBoard(path)
    pads = {}
    for f in b.GetFootprints():
        for p in f.Pads(): pads.setdefault(p.GetNetname(), []).append(p)
    segs, vias = {}, {}
    for t in b.GetTracks():
        (vias if t.GetClass() == "PCB_VIA" else segs).setdefault(t.GetNetname(), []).append(t)
    dead = [t for n in touched for t in segs.get(n, []) if not t.IsLocked()
            and not (end_ok(t, t.GetStart(), segs, vias, pads) and end_ok(t, t.GetEnd(), segs, vias, pads))]
    # vias that now connect to nothing on either outer layer
    for n in touched:
        for v in vias.get(n, []):
            if v.IsLocked(): continue
            p = v.GetPosition(); r = v.GetWidth(pcbnew.F_Cu) / 2
            hit = any(math.hypot(s.GetStart().x - p.x, s.GetStart().y - p.y) <= r or math.hypot(s.GetEnd().x - p.x, s.GetEnd().y - p.y) <= r
                      for s in segs.get(n, []))
            hit = hit or any(q.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_OUTSIDE).Collide(p, int(r)) for q in pads.get(n, []) if q.IsOnLayer(pcbnew.F_Cu))
            if not hit and n not in os.environ.get("PLANE_NETS", "/GND").split(","): dead.append(v)
    for t in dead: b.Remove(t)
    if dead: pcbnew.SaveBoard(path, b)
    return len(dead)

if len(sys.argv) > 3 and sys.argv[3] == "--strip":
    n = strip_once(sys.argv[1], set(sys.argv[4].split("\t")))
    print(n, flush=True); os._exit(0)
b = pcbnew.LoadBoard(sys.argv[1])
rep = open(sys.argv[2]).read()
want = []   # (kind, net, x, y)
for code, blk in re.findall(r"^\[(\w+)\]:.*?\n((?:    .*\n)+)", rep, re.M):
    if code not in RIP: continue
    for x, y, kind, net in re.findall(r"@\(([\d.]+) mm, ([\d.]+) mm\): (Track|Via) \[(/[^\]]+)\]", blk):
        want.append((kind, net, float(x), float(y)))

tracks = list(b.GetTracks()); victims = []
def dist(t, x, y):
    if t.GetClass() == "PCB_VIA":
        p = t.GetPosition(); return math.hypot(p.x / MM - x, p.y / MM - y)
    pts = (t.GetStart(), t.GetEnd(), pcbnew.VECTOR2I((t.GetStart().x + t.GetEnd().x) // 2, (t.GetStart().y + t.GetEnd().y) // 2))
    return min(math.hypot(p.x / MM - x, p.y / MM - y) for p in pts)
for kind, net, x, y in want:
    cls = "PCB_VIA" if kind == "Via" else "PCB_TRACK"
    cand = [t for t in tracks if t.GetClass() == cls and t.GetNetname() == net and not t.IsLocked() and t not in victims]
    if not cand: continue
    best = min(cand, key=lambda t: dist(t, x, y))
    if dist(best, x, y) < 0.05: victims.append(best)
touched = {t.GetNetname() for t in victims}
nv = len(victims)
for t in victims: b.Remove(t)
pcbnew.SaveBoard(sys.argv[1], b)
# pcbnew 10.0.3: walking/reloading boards after Remove() in one process corrupts SWIG objects -> one child per pass
import subprocess
stripped = 0
while touched:
    r = subprocess.run([sys.executable, __file__, sys.argv[1], sys.argv[2], "--strip", "\t".join(sorted(touched))], capture_output=True, text=True)
    n = int([l for l in r.stdout.split() if l.isdigit()][-1]); stripped += n
    if n == 0: break
print("blamed", len(want), "ripped", nv, "stripped", stripped, "nets", len(touched), flush=True)
os._exit(0)

