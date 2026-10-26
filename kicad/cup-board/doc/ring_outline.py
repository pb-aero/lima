import sys, pcbnew
path, cx, cy, ro, ri = sys.argv[1], *map(float, sys.argv[2:6])
b = pcbnew.LoadBoard(path)
for r in (ro, ri):
    s = pcbnew.PCB_SHAPE(b, pcbnew.SHAPE_T_CIRCLE)
    s.SetCenter(pcbnew.VECTOR2I(pcbnew.FromMM(cx), pcbnew.FromMM(cy)))
    s.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(cx + r), pcbnew.FromMM(cy)))
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(pcbnew.FromMM(0.05))
    b.Add(s)
pcbnew.SaveBoard(path, b)
print("edge shapes:", sum(1 for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts), "copper layers:", b.GetCopperLayerCount())
