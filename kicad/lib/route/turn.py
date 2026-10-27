"""Turn footprints in place by a relative angle, optionally parking others off-board first.
Usage: turn.py <board> REF:DEG [REF:DEG ...] [--park REF,REF,...]   Run with KiCad closed."""
import sys, os, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); args = sys.argv[2:]; park = []
if "--park" in args: i = args.index("--park"); park = args[i + 1].split(","); args = args[:i] + args[i + 2:]
for a in args:
    ref, deg = a.split(":"); f = b.FindFootprintByReference(ref); f.SetOrientationDegrees(f.GetOrientationDegrees() + float(deg))
    print(ref, "->", round(f.GetOrientationDegrees(), 1), flush=True)
for k, ref in enumerate(park):
    b.FindFootprintByReference(ref).SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(250 + 6 * k), pcbnew.FromMM(250)))
pcbnew.SaveBoard(sys.argv[1], b); os._exit(0)
