"""Subtract aircraft-corridor rectangles from the In1/In2 plane outlines (KiCad closed)."""
import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); F = pcbnew.FromMM
RECTS = [(129.0, 126.9, 156.5, 130.5),   # EAR bottom-edge corridor
         (142.2, 118.3, 156.4, 130.5),   # under T2 + EAR_HI F.Cu link at y119.2
         (152.6, 115.0, 161.6, 126.0)]   # under T3 + EAR_RTN riser at x153.2
cut = pcbnew.SHAPE_POLY_SET()
for x0, y0, x1, y1 in RECTS:
    r = pcbnew.SHAPE_POLY_SET(); r.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)): r.Append(F(x), F(y))
    cut.BooleanAdd(r)
for z in b.Zones():
    if z.GetNetname() in ("/GND", "/+3V3"):
        o = z.Outline(); before = o.Area(); o.BooleanSubtract(cut)
        print(z.GetNetname(), "area mm2", round(before/1e12, 1), "->", round(o.Area()/1e12, 1), "outlines", o.OutlineCount())
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[1], b)
