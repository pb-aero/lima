"""Remove every unlocked track/via of the named nets, or of every net with unlocked copper within R mm of the given
pads.  Usage: ripnets.py <board> [--near REF.PAD,REF.PAD,... --r 2.5] [NET ...]   Run with KiCad closed."""
import sys, os, math, pcbnew
b = pcbnew.LoadBoard(sys.argv[1]); MM = 1e6
args = sys.argv[2:]; nets = set(); near = []; R = 2.5
while args:
    a = args.pop(0)
    if a == "--near": near = args.pop(0).split(",")
    elif a == "--r": R = float(args.pop(0))
    else: nets.add(a)
pts = []
for rp in near:
    ref, num = rp.split(".")
    f = b.FindFootprintByReference(ref)
    pts += [(p.GetPosition().x / MM, p.GetPosition().y / MM) for p in f.Pads() if p.GetNumber() == num]
def segd(t, x, y):
    if t.GetClass() == "PCB_VIA":
        return math.hypot(t.GetPosition().x / MM - x, t.GetPosition().y / MM - y)
    ax, ay, bx, by = t.GetStart().x / MM, t.GetStart().y / MM, t.GetEnd().x / MM, t.GetEnd().y / MM
    dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
    u = 0 if L2 == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L2))
    return math.hypot(x - ax - u * dx, y - ay - u * dy)
tracks = list(b.GetTracks())
planes = set(os.environ.get("PLANE_NETS", "/GND").split(","))
for t in tracks:
    if not t.IsLocked() and t.GetNetname() not in planes and any(segd(t, x, y) < R for x, y in pts): nets.add(t.GetNetname())
victims = [t for t in tracks if not t.IsLocked() and t.GetNetname() in nets]
for t in victims: b.Remove(t)
pcbnew.SaveBoard(sys.argv[1], b)
print("ripped", len(victims), "items on", len(nets), "nets:", " ".join(sorted(nets)), flush=True); os._exit(0)
