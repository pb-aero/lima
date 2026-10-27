import sys, math, json, pcbnew
board, table, cx, cy, margin = sys.argv[1], sys.argv[2], 150.0, 100.0, 0.55
ro = float(sys.argv[3]) if len(sys.argv) > 3 else 34.0   # outer radius (36 since the 72/38 ring)
b = pcbnew.LoadBoard(board); P = json.load(open(table))
for f in b.GetFootprints():
    r = f.GetReference()
    if r not in ('J2', 'J7', 'J8'): continue
    worst = 0.0
    for p in f.Pads():
        poly = p.GetEffectivePolygon(pcbnew.F_Cu)
        for i in range(poly.OutlineCount()):
            o = poly.Outline(i)
            for k in range(o.PointCount()):
                q = o.CPoint(k); worst = max(worst, math.hypot(pcbnew.ToMM(q.x) - cx, pcbnew.ToMM(q.y) - cy))
    shift = max(0.0, worst - (ro - margin))
    pos = f.GetPosition(); x, y = pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y)
    d = math.hypot(x - cx, y - cy); ux, uy = (x - cx) / d, (y - cy) / d
    nx, ny = x - ux * shift, y - uy * shift
    f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(nx), pcbnew.FromMM(ny)))
    P[r] = [round(nx, 3), round(ny, 3), P[r][2]]
    print(r, "outermost copper r=%.3f -> shift in %.3f mm" % (worst, shift))
pcbnew.SaveBoard(board, b); json.dump(P, open(table, 'w'))
