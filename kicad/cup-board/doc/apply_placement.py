import sys, json, pcbnew
board, table = sys.argv[1], sys.argv[2]
P = json.load(open(table)); b = pcbnew.LoadBoard(board); n = 0; missing = []
fps = {f.GetReference(): f for f in b.GetFootprints()}
for ref, (x, y, rot) in P.items():
    f = fps.get(ref)
    if f is None: missing.append(ref); continue
    f.SetOrientationDegrees(rot)
    f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
    n += 1
pcbnew.SaveBoard(board, b)
# read back from a fresh load of the saved file
b2 = pcbnew.LoadBoard(board); worst = 0.0
for f in b2.GetFootprints():
    r = f.GetReference()
    if r not in P: continue
    x, y, rot = P[r]; p = f.GetPosition()
    dpos = max(abs(pcbnew.ToMM(p.x) - x), abs(pcbnew.ToMM(p.y) - y))
    drot = abs(((f.GetOrientationDegrees() - rot) + 180) % 360 - 180)
    worst = max(worst, dpos, drot)
print("placed", n, "missing", missing, "footprints on board", len(b2.GetFootprints()), "worst read-back error", round(worst, 4))
