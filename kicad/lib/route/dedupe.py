"""Drop duplicate tracks/vias (SES re-imports protected wiring with nm rounding). Keeps locked copies."""
import pcbnew
def dedupe(b, tol=2000):
    def q(v): return (round(v.x / tol), round(v.y / tol))
    seen, dup = {}, []
    for t in list(b.GetTracks()):          # no sorted(): sorting SWIG proxies segfaults pcbnew 10.0.3
        a, c = q(t.GetStart()), q(t.GetEnd())
        k = (t.GetClass(), t.GetNetCode(), t.GetLayer(), min(a, c), max(a, c))
        if k not in seen: seen[k] = t
        elif t.IsLocked() and not seen[k].IsLocked(): dup.append(seen[k]); seen[k] = t
        else: dup.append(t)
    for t in dup: b.Remove(t)
    return len(dup)
if __name__ == "__main__":
    import sys
    b = pcbnew.LoadBoard(sys.argv[1]); n = dedupe(b); pcbnew.SaveBoard(sys.argv[1], b); print("dropped", n, flush=True); import os; os._exit(0)
