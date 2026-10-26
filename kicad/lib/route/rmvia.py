import sys, os, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); MM = 1e6
want = [tuple(map(float, xy.split(","))) for xy in " ".join(sys.argv[2:]).split()]
vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and not t.IsLocked()]
victims = []
for x, y in want:
    for v in vias:
        p = v.GetPosition()
        if abs(p.x / MM - x) < 0.01 and abs(p.y / MM - y) < 0.01 and v not in victims: victims.append(v); break
for v in victims: b.Remove(v)
pcbnew.SaveBoard(sys.argv[1], b); print("removed vias", len(victims), flush=True); os._exit(0)
