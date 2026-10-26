"""Rip: remove every unlocked track/via of the given nets that touches the given footprint pads (or whole nets),
then strip dangling stubs. Usage: rip.py board 'NET' | 'REF' ...  (REF: pads of that footprint)"""
import sys, os, math, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); MM = 1e6
nets = [a for a in sys.argv[2:] if a.startswith("/")]; refs = [a for a in sys.argv[2:] if not a.startswith("/")]
rm = set()
for t in b.GetTracks():
    if t.IsLocked(): continue
    if t.GetNetname() in nets: rm.add(t.m_Uuid.AsString()); continue
for r in refs:
    f = b.FindFootprintByReference(r)
    for p in f.Pads():
        poly = p.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_OUTSIDE)
        for t in b.GetTracks():
            if t.IsLocked() or t.GetNetname() != p.GetNetname() or t.GetClass() == "PCB_VIA": continue
            if poly.Collide(t.GetStart(), 1000) or poly.Collide(t.GetEnd(), 1000): rm.add(t.m_Uuid.AsString())
victims = [t for t in b.GetTracks() if t.m_Uuid.AsString() in rm]
for t in victims: b.Remove(t)
# strip dangling stubs: a segment end must touch a pad, a via or another segment of its net
def ends_ok(t, segs, vias, pads):
    for e in (t.GetStart(), t.GetEnd()):
        hit = any(p.GetEffectivePolygon(t.GetLayer(), pcbnew.ERROR_OUTSIDE).Collide(e, 1000) for p in pads.get(t.GetNetname(), []) if p.IsOnLayer(t.GetLayer()))
        hit = hit or any(math.hypot(e.x - v.GetPosition().x, e.y - v.GetPosition().y) <= v.GetWidth(pcbnew.F_Cu) / 2 for v in vias.get(t.GetNetname(), []))
        hit = hit or any(s is not t and s.GetLayer() == t.GetLayer() and (s.GetStart() == e or s.GetEnd() == e) for s in segs.get(t.GetNetname(), []))
        if not hit: return False
    return True
pads = {}
for f in b.GetFootprints():
    for p in f.Pads(): pads.setdefault(p.GetNetname(), []).append(p)
stripped = 0
while True:
    segs, vias = {}, {}
    for t in b.GetTracks():
        (vias if t.GetClass() == "PCB_VIA" else segs).setdefault(t.GetNetname(), []).append(t)
    touched = set(nets) | {p.GetNetname() for r in refs for p in b.FindFootprintByReference(r).Pads()}
    dead = [t for n in touched for t in segs.get(n, []) if not t.IsLocked() and not ends_ok(t, segs, vias, pads)]
    if not dead: break
    for t in dead: b.Remove(t)
    stripped += len(dead)
pcbnew.SaveBoard(sys.argv[1], b); print("ripped", len(victims), "stripped", stripped, flush=True); os._exit(0)
