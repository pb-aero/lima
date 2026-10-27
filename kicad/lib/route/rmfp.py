"""Remove footprints by reference (e.g. a mounting hole dropped from the schematic). KiCad closed.
Usage: rmfp.py <board> REF ..."""
import sys, os, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); gone = []
for r in sys.argv[2:]:
    f = b.FindFootprintByReference(r)
    if f: b.Remove(f); gone.append(r)
pcbnew.SaveBoard(sys.argv[1], b); print("removed", gone, flush=True); os._exit(0)
