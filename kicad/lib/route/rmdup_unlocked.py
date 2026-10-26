"""Remove unlocked segments lying entirely on locked same-net same-layer copper, and zero-length segments."""
import sys, os, math, pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
segs = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
locked = [t for t in segs if t.IsLocked()]
def on(p, s):
    a, c = s.GetStart(), s.GetEnd(); dx, dy = c.x - a.x, c.y - a.y; L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / L2))
    return math.hypot(p.x - a.x - t * dx, p.y - a.y - t * dy) < 2000
victims = []
for t in segs:
    if t.IsLocked(): continue
    if t.GetStart() == t.GetEnd(): victims.append(t); continue
    same = [s for s in locked if s.GetNetCode() == t.GetNetCode() and s.GetLayer() == t.GetLayer()]
    pts = [pcbnew.VECTOR2I(int(t.GetStart().x + (t.GetEnd().x - t.GetStart().x) * k / 20), int(t.GetStart().y + (t.GetEnd().y - t.GetStart().y) * k / 20)) for k in range(21)]
    if same and all(any(on(p, s) for s in same) for p in pts): victims.append(t)
names = [(t.GetNetname(), round(t.GetLength() / 1e6, 2)) for t in victims]
for t in victims: b.Remove(t)
pcbnew.SaveBoard(sys.argv[1], b); print("removed", names, flush=True); os._exit(0)
