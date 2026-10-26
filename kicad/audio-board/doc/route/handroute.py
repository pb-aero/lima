"""Hand routes from a JSON spec: {"tracks": [[net, layer, width, [[x,y],...]], ...], "vias": [[net, x, y, dia, drill], ...]}."""
import sys, json, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); spec = json.load(open(sys.argv[2])); F = pcbnew.FromMM
L = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
nets = {tr[0] for tr in spec["tracks"]} | {v[0] for v in spec.get("vias", [])}
old = [t for t in b.GetTracks() if t.GetNetname() in nets and t.IsLocked()]
for t in old: b.Remove(t)
print("removed", len(old), "old locked items")
for z in b.Zones(): z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
n = 0
for net, layer, w, pts in spec["tracks"]:
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(F(x0), F(y0))); t.SetEnd(pcbnew.VECTOR2I(F(x1), F(y1)))
        t.SetWidth(F(w)); t.SetLayer(L[layer]); t.SetNet(b.FindNet(net)); t.SetLocked(True); b.Add(t); n += 1
for net, x, y, d, dr in spec.get("vias", []):
    v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(F(x), F(y))); v.SetWidth(F(d)); v.SetDrill(F(dr))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(b.FindNet(net)); v.SetLocked(True); b.Add(v)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[1], b); print("segments", n, "vias", len(spec.get("vias", [])))
