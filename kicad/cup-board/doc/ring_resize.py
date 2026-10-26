import sys, pcbnew
path, old_r, new_r = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
b = pcbnew.LoadBoard(path)
edges = [d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
print("before:", [(d.GetShapeStr(), round(pcbnew.ToMM(d.GetRadius()), 3)) for d in edges])
hit = [d for d in edges if d.GetShape() == pcbnew.SHAPE_T_CIRCLE and abs(pcbnew.ToMM(d.GetRadius()) - old_r) < 0.01]
assert len(hit) == 1, "expected exactly one circle of the old radius"
c = hit[0].GetCenter(); b.Remove(hit[0])
s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_CIRCLE)
s.SetCenter(c); s.SetEnd(pcbnew.VECTOR2I(c.x + pcbnew.FromMM(new_r), c.y))
s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.05)); b.Add(s)
pcbnew.SaveBoard(path, b)
print("after:", [(d.GetShapeStr(), round(pcbnew.ToMM(d.GetRadius()), 3)) for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts])
