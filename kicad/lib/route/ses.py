"""Import a Freerouting SES, then de-dupe in a fresh process (de-duping in the importing process segfaults pcbnew 10.0.3)."""
import sys, os, subprocess, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); ok = pcbnew.ImportSpecctraSES(b, sys.argv[2])
pcbnew.SaveBoard(sys.argv[1], b); print("import", ok, "tracks", len(b.GetTracks()), flush=True)
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "dedupe.py"), sys.argv[1]])
os._exit(0)
