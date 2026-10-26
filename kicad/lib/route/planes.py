"""Add full-board plane zones that follow the real outline (rings included), pulled in 0.5 mm from the edge.
Usage: planes.py <board> /GND=In1.Cu /1V8=In2.Cu ...   (replaces any existing zone of that net on that layer)
Run with KiCad closed."""
import sys, os, pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
ol = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(ol, False)
area = pcbnew.SHAPE_POLY_SET(ol); area.Deflate(pcbnew.FromMM(0.5), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.005))
for spec in sys.argv[2:]:
    net, layer = spec.split("=")
    L = b.GetLayerID(layer)
    old = [z for z in b.Zones() if z.GetNetname() == net and z.GetLayer() == L]
    for z in old: b.Remove(z)
    z = pcbnew.ZONE(b); z.SetLayer(L); z.SetNet(b.FindNet(net))
    z.Outline().RemoveAllContours(); z.Outline().Append(area)
    z.SetLocalClearance(pcbnew.FromMM(0.2)); z.SetMinThickness(pcbnew.FromMM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(pcbnew.FromMM(0.25)); z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.3))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    b.Add(z)
    print(net, layer, "zone area mm2", round(area.Area() / 1e12, 1), "replaced", len(old), flush=True)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[1], b); os._exit(0)
