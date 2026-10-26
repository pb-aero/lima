"""Apply {ref: (x, y, deg)} moves from a JSON file to a board (KiCad closed)."""
import sys, json, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); mv = json.load(open(sys.argv[2]))
for ref, (x, y, r) in mv.items():
    f = b.FindFootprintByReference(ref)
    f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))); f.SetOrientationDegrees(r)
pcbnew.SaveBoard(sys.argv[1], b); print("moved", len(mv))
for ref in sys.argv[3].split(",") if len(sys.argv) > 3 else []:
    f = b.FindFootprintByReference(ref)
    print(ref, [(p.GetNumber(), p.GetNetname().lstrip('/')[:10], round(p.GetPosition().x/1e6,2), round(p.GetPosition().y/1e6,2)) for p in f.Pads() if p.IsOnLayer(pcbnew.F_Cu) and p.GetNumber()!='33'])
