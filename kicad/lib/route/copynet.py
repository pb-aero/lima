"""Copy every track/via of the named nets from a source board into a target board (e.g. restore a route that a
rip-up displaced). Usage: copynet.py <source.kicad_pcb> <target.kicad_pcb> NET ...   Run with KiCad closed."""
import sys, os, pcbnew
src, dst = pcbnew.LoadBoard(sys.argv[1]), pcbnew.LoadBoard(sys.argv[2]); n = 0
for t in src.GetTracks():
    if t.GetNetname() not in sys.argv[3:]: continue
    if t.GetClass() == "PCB_VIA":
        v = pcbnew.PCB_VIA(dst); v.SetPosition(t.GetPosition()); v.SetWidth(t.GetWidth()); v.SetDrill(t.GetDrill())
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(dst.FindNet(t.GetNetname())); v.SetLocked(t.IsLocked()); dst.Add(v)
    else:
        c = pcbnew.PCB_TRACK(dst); c.SetStart(t.GetStart()); c.SetEnd(t.GetEnd()); c.SetWidth(t.GetWidth())
        c.SetLayer(t.GetLayer()); c.SetNet(dst.FindNet(t.GetNetname())); c.SetLocked(t.IsLocked()); dst.Add(c)
    n += 1
pcbnew.SaveBoard(sys.argv[2], dst); print("copied", n, "items on", " ".join(sys.argv[3:]), flush=True); os._exit(0)
