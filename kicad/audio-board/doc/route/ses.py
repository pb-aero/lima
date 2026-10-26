import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); print("import", pcbnew.ImportSpecctraSES(b, sys.argv[2]))
f = pcbnew.ZONE_FILLER(b); f.Fill(b.Zones())
pcbnew.SaveBoard(sys.argv[1], b); print("tracks", len(b.GetTracks()))
