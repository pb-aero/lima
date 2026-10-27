"""Lock (or unlock with --unlock) every track/via of the named nets so rip-up and Freerouting leave them alone.
Usage: locknets.py <board> [--unlock] NET ...   Run with KiCad closed."""
import sys, os, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); args = sys.argv[2:]; lock = True
if args and args[0] == "--unlock": lock = False; args = args[1:]
n = 0
for t in b.GetTracks():
    if t.GetNetname() in args: t.SetLocked(lock); n += 1
pcbnew.SaveBoard(sys.argv[1], b); print(("locked" if lock else "unlocked"), n, "items on", " ".join(args), flush=True); os._exit(0)
