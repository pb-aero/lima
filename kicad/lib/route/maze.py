"""Finish routing: A* maze router on F.Cu/B.Cu for the connections KiCad's DRC still reports unconnected.

Run with KiCad closed:  maze.py <board.kicad_pcb> <drc-report.rpt>
Obstacles are the board's real copper (pads, tracks, vias, holes, edge), inflated by clearance + half
track width, so every grid cell the path uses keeps clearance. Plane nets (GND, +3V3) treat every
via/THT pad that sits inside their plane as one connected cluster. New tracks are added unlocked.
"""
import sys, re, math, heapq
from array import array
import pcbnew

MM = 1_000_000
RES = 0.05                                   # grid pitch, mm
CL, CL_AIR, HOLE_CL, EDGE_CL, SLACK = 0.13, 0.52, 0.26, 0.52, RES * 0.75
VIA_D, VIA_DRILL, VIA_COST = 0.5, 0.25, 40   # via cost in grid steps (2 mm)
import os
AIRCRAFT = set(os.environ.get("AIRCRAFT_NETS", "").split())          # 0.5 mm clearance class
PLANES = set(os.environ.get("PLANE_NETS", "/GND,/+3V3").split(","))  # nets whose plane joins their vias
WIDTH = dict(kv.split("=") for kv in os.environ.get("MAZE_WIDTHS", "").split() if "=" in kv)  # "/NET=0.3 ..."
WIDTH = {k: float(v) for k, v in WIDTH.items()}                         # everything else 0.2
def width(net): return float(os.environ["MAZE_W"]) if "MAZE_W" in os.environ else WIDTH.get(net, 0.2)

b = pcbnew.LoadBoard(sys.argv[1])
# MAZE_LAYERS: routing layers, outer first; inner ones cost LAYER_COST x per step (plane slots only when needed)
LAYERS = tuple(b.GetLayerID(n) for n in os.environ.get("MAZE_LAYERS", "F.Cu,B.Cu").split(","))
NL = len(LAYERS)
STEP_COST = [1.0 if L in (pcbnew.F_Cu, pcbnew.B_Cu) else float(os.environ.get("LAYER_COST", "3")) for L in LAYERS]
_bb = b.GetBoardEdgesBoundingBox()
X0, Y0 = math.floor(_bb.GetX() / MM), math.floor(_bb.GetY() / MM)
X1, Y1 = math.ceil(_bb.GetRight() / MM), math.ceil(_bb.GetBottom() / MM)
NX, NY = int((X1 - X0) / RES) + 1, int((Y1 - Y0) / RES) + 1
N = NX * NY
OUTLINE = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(OUTLINE, False)
plane_outline = {z.GetNetname(): z.Outline() for z in b.Zones() if z.GetNetname() in PLANES}

def cell(x, y): return int(round((x - X0) / RES)), int(round((y - Y0) / RES))
def cxy(ix, iy): return X0 + ix * RES, Y0 + iy * RES

# ---------- copper items as (net, layers, kind, geom) ----------
items = []
SOFT = {}          # id(item tuple) -> net, for unlocked tracks/vias that rip-up may displace
def add_items():
    items.clear(); SOFT.clear()
    for f in b.GetFootprints():
        for p in f.Pads():
            lys = [L for L in LAYERS if p.IsOnLayer(L)]
            if p.HasHole():
                d = max(p.GetDrillSize().x, p.GetDrillSize().y) / MM
                items.append((None, LAYERS, "hole", (p.GetPosition().x / MM, p.GetPosition().y / MM, d / 2)))
            for L in lys:
                items.append((p.GetNetname(), (L,), "poly", (p.GetEffectivePolygon(L, pcbnew.ERROR_OUTSIDE), p)))
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            x, y = t.GetPosition().x / MM, t.GetPosition().y / MM
            items.append((t.GetNetname(), LAYERS, "circle", (x, y, t.GetWidth(pcbnew.F_Cu) / MM / 2)))
            items.append((None, LAYERS, "hole", (x, y, t.GetDrillValue() / MM / 2)))
            if not t.IsLocked() and t.GetNetname() not in PLANES:
                SOFT[id(items[-2])] = t.GetNetname(); SOFT[id(items[-1])] = t.GetNetname()
        elif t.GetLayer() in LAYERS:
            items.append((t.GetNetname(), (t.GetLayer(),), "seg",
                          (t.GetStart().x / MM, t.GetStart().y / MM, t.GetEnd().x / MM, t.GetEnd().y / MM, t.GetWidth() / MM / 2)))
            if not t.IsLocked() and t.GetNetname() not in PLANES: SOFT[id(items[-1])] = t.GetNetname()

# ---------- rasterising: per-row x-intervals for capsules/circles, Collide for pads ----------
def capsule_rows(ax, ay, bx, by, R):
    """yield (iy, ix0, ix1) cells within R of segment a-b"""
    ylo, yhi = min(ay, by) - R, max(ay, by) + R
    dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
    for iy in range(max(0, cell(0, ylo)[1] - 1), min(NY - 1, cell(0, yhi)[1] + 1) + 1):
        y = Y0 + iy * RES; lo, hi = 1e9, -1e9
        for (px, py) in ((ax, ay), (bx, by)):
            h = R * R - (y - py) ** 2
            if h >= 0: s = math.sqrt(h); lo, hi = min(lo, px - s), max(hi, px + s)
        if L2 > 0:
            # strip: 0 <= ((x-ax)dx + (y-ay)dy) <= L2  and |(x-ax)dy - (y-ay)dx| <= R*sqrt(L2)
            cons = []
            if abs(dx) > 1e-12:
                t0 = (0 - (y - ay) * dy) / dx + ax; t1 = (L2 - (y - ay) * dy) / dx + ax
                cons.append((min(t0, t1), max(t0, t1)))
            elif not (0 <= (y - ay) * dy <= L2): cons.append((1e9, -1e9))
            RL = R * math.sqrt(L2)
            if abs(dy) > 1e-12:
                c0 = (-RL + (y - ay) * dx) / dy + ax; c1 = (RL + (y - ay) * dx) / dy + ax
                cons.append((min(c0, c1), max(c0, c1)))
            elif abs((y - ay) * dx) > RL: cons.append((1e9, -1e9))
            slo = max(c[0] for c in cons) if cons else -1e9; shi = min(c[1] for c in cons) if cons else 1e9
            if slo <= shi: lo, hi = min(lo, slo), max(hi, shi)
        if lo <= hi:
            ix0 = max(0, int(math.ceil((lo - X0) / RES))); ix1 = min(NX - 1, int(math.floor((hi - X0) / RES)))
            if ix0 <= ix1: yield iy, ix0, ix1

def stamp(grid, it, infl, delta):
    net, lys, kind, g = it
    for li, L in enumerate(LAYERS):
        if L not in lys: continue
        base = li * N
        if kind in ("circle", "hole"):
            rows = capsule_rows(g[0], g[1], g[0], g[1], g[2] + infl)
        elif kind == "seg":
            rows = capsule_rows(g[0], g[1], g[2], g[3], g[4] + infl)
        else:
            poly, p = g; bb = poly.BBox(); rows = []
            x0, y0 = cell(bb.GetX() / MM - infl, bb.GetY() / MM - infl); x1, y1 = cell(bb.GetRight() / MM + infl, bb.GetBottom() / MM + infl)
            ip = int(infl * MM)
            for iy in range(max(0, y0), min(NY - 1, y1) + 1):
                run = None
                for ix in range(max(0, x0), min(NX - 1, x1) + 1):
                    x, y = cxy(ix, iy)
                    if poly.Collide(pcbnew.VECTOR2I(int(x * MM), int(y * MM)), ip):
                        grid[base + iy * NX + ix] += delta
            continue
        for iy, ix0, ix1 in rows:
            o = base + iy * NX
            for ix in range(ix0, ix1 + 1): grid[o + ix] += delta

def infl_for(it, w, net):
    onet, lys, kind, g = it
    if kind == "hole": return HOLE_CL + w / 2 + SLACK
    cl = CL_AIR if (onet in AIRCRAFT or net in AIRCRAFT) else CL
    return cl + w / 2 + SLACK

def build_grid(w, net, soft=None):
    """block count per cell for a track of width w on `net` (own-net copper excluded).
    soft: an array to receive rip-able items instead of `grid` (rip-up mode)"""
    grid = array("H", bytes(2 * NL * N))
    for it in items:
        if it[0] == net and it[2] != "hole": continue
        if soft is not None and id(it) in SOFT and SOFT[id(it)] != net:
            stamp(soft, it, infl_for(it, w, net), 1); continue
        stamp(grid, it, infl_for(it, w, net), 1)
    # board edge: block every cell outside the outline deflated by edge clearance (scanline, handles holes)
    safe = pcbnew.SHAPE_POLY_SET(OUTLINE); safe.Deflate(int((EDGE_CL + w / 2 + SLACK) * MM), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, 5000)
    edges = []
    for oi in range(safe.OutlineCount()):
        chains = [safe.Outline(oi)] + [safe.Hole(oi, hi) for hi in range(safe.HoleCount(oi))]
        for ch in chains:
            n = ch.PointCount()
            for k in range(n):
                a, c = ch.CPoint(k), ch.CPoint((k + 1) % n)
                edges.append((a.x / MM, a.y / MM, c.x / MM, c.y / MM))
    for iy in range(NY):
        y = Y0 + iy * RES; xs = []
        for ax, ay, cx_, cy_ in edges:
            if (ay <= y < cy_) or (cy_ <= y < ay): xs.append(ax + (y - ay) * (cx_ - ax) / (cy_ - ay))
        xs.sort(); inside = [False] * NX
        for k in range(0, len(xs) - 1, 2):
            ix0 = max(0, int(math.ceil((xs[k] - X0) / RES))); ix1 = min(NX - 1, int(math.floor((xs[k + 1] - X0) / RES)))
            for ix in range(ix0, ix1 + 1): inside[ix] = True
        for ix in range(NX):
            if not inside[ix]:
                for li in range(NL): grid[li * N + iy * NX + ix] += 1
    return grid

# ---------- clusters of a net ----------
def touches(a, b2):
    la, lb = set(a[1]), set(b2[1])
    if not la & lb: return False
    def pts(it):
        k, g = it[2], it[3]
        if k == "circle": return [(g[0], g[1], g[2])]
        if k == "seg":
            n = max(1, int(math.hypot(g[2] - g[0], g[3] - g[1]) / 0.05))
            return [(g[0] + (g[2] - g[0]) * i / n, g[1] + (g[3] - g[1]) * i / n, g[4]) for i in range(n + 1)]
        bb = g[0].BBox(); return None
    def hit(it, x, y, r):
        k, g = it[2], it[3]
        if k == "circle": return math.hypot(x - g[0], y - g[1]) <= g[2] + r + 1e-4
        if k == "seg":
            ax, ay, bx, by, R = g; dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
            t = 0 if L2 == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L2))
            return math.hypot(x - ax - t * dx, y - ay - t * dy) <= R + r + 1e-4
        return g[0].Collide(pcbnew.VECTOR2I(int(x * MM), int(y * MM)), int(r * MM) + 100)
    pa = pts(a)
    if pa is not None: return any(hit(b2, x, y, r) for x, y, r in pa)
    pb = pts(b2)
    if pb is not None: return any(hit(a, x, y, r) for x, y, r in pb)
    pa_, pb_ = a[3][0], b2[3][0]
    return pa_.Collide(pb_.Outline(0).CPoint(0), 0) or pb_.Collide(pa_.Outline(0).CPoint(0), 0)

def clusters(net):
    its = [it for it in items if it[0] == net]
    parent = list(range(len(its)))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i in range(len(its)):
        for j in range(i + 1, len(its)):
            if find(i) != find(j) and touches(its[i], its[j]): parent[find(i)] = find(j)
    if net in plane_outline:   # everything that reaches the plane is one cluster
        o = plane_outline[net]; anchor = None
        for i, it in enumerate(its):
            if it[1] == LAYERS:   # via or THT pad on both outer layers -> through the plane
                g = it[3]; x, y = (g[0], g[1]) if it[2] == "circle" else (g[1].GetPosition().x / MM, g[1].GetPosition().y / MM)
                if o.Contains(pcbnew.VECTOR2I(int(x * MM), int(y * MM))):
                    if anchor is None: anchor = i
                    else: parent[find(i)] = find(anchor)
    groups = {}
    for i in range(len(its)): groups.setdefault(find(i), []).append(its[i])
    return list(groups.values())

def item_at(cl_list, x, y):
    for k, cl in enumerate(cl_list):
        for it in cl:
            g = it[3]
            if it[2] == "circle" and math.hypot(x - g[0], y - g[1]) <= g[2] + 0.02: return k
            if it[2] == "seg":
                ax, ay, bx, by, R = g; dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
                t = 0 if L2 == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L2))
                if math.hypot(x - ax - t * dx, y - ay - t * dy) <= R + 0.02: return k
            if it[2] == "poly" and g[0].Collide(pcbnew.VECTOR2I(int(x * MM), int(y * MM)), 20000): return k
    return None

def seed_cells(cl):
    s = set()
    for it in cl:
        for li, L in enumerate(LAYERS):
            if L not in it[1]: continue
            g = array("H", [0]); tmp = {}
            # cells inside the item itself
            k, gg = it[2], it[3]
            if k == "circle": rows = capsule_rows(gg[0], gg[1], gg[0], gg[1], gg[2] - RES)
            elif k == "seg": rows = capsule_rows(gg[0], gg[1], gg[2], gg[3], max(RES / 2, gg[4] - RES))
            else:
                poly = gg[0]; bb = poly.BBox(); rows = []
                x0, y0 = cell(bb.GetX() / MM, bb.GetY() / MM); x1, y1 = cell(bb.GetRight() / MM, bb.GetBottom() / MM)
                for iy in range(y0, y1 + 1):
                    for ix in range(x0, x1 + 1):
                        x, y = cxy(ix, iy)
                        if poly.Contains(pcbnew.VECTOR2I(int(x * MM), int(y * MM))): s.add(li * N + iy * NX + ix)
                continue
            for iy, ix0, ix1 in rows:
                for ix in range(ix0, ix1 + 1): s.add(li * N + iy * NX + ix)
    return s

# ---------- A* ----------
SOFT_COST = float(os.environ.get("SOFT_COST", "25"))
def astar(grid, src, dst, sgrid=None, svgrid=None):
    free = lambda n: grid[n] == 0
    pen = (lambda m: SOFT_COST if sgrid[m] else 0) if sgrid is not None else (lambda m: 0)
    vpen = (lambda idx: SOFT_COST * 4 if any(svgrid[li * N + idx] for li in range(NL)) else 0) if svgrid is not None else (lambda idx: 0)
    def via_ok(idx):   # both layers free for a via (bigger than the track) -> checked on a via grid
        return all(vgrid[li * N + idx] == 0 for li in range(NL))
    tx = [((n % N) % NX, (n % N) // NX) for n in list(dst)[:400]]
    def h(n):
        ix, iy = (n % N) % NX, (n % N) // NX
        return min(max(abs(ix - a), abs(iy - c)) + 0.414 * min(abs(ix - a), abs(iy - c)) for a, c in tx)
    openh, g, came = [], {}, {}
    for n in src:
        if free(n): g[n] = 0; heapq.heappush(openh, (h(n), n))
    steps = ((1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414))
    seen = 0
    while openh:
        f, n = heapq.heappop(openh)
        if n in dst:
            path = [n]
            while path[-1] in came: path.append(came[path[-1]])
            return path[::-1]
        seen += 1
        if seen > 3_000_000: return None
        li, idx = divmod(n, N); iy, ix = divmod(idx, NX); gn = g[n]
        for dx, dy, c0 in steps:
            c = c0 * STEP_COST[li]
            jx, jy = ix + dx, iy + dy
            if 0 <= jx < NX and 0 <= jy < NY:
                m = li * N + jy * NX + jx
                if free(m):
                    cm = c + pen(m)
                    if gn + cm < g.get(m, 1e18):
                        g[m] = gn + cm; came[m] = n; heapq.heappush(openh, (gn + cm + h(m), m))
        if via_ok(idx):
            for lj in range(NL):
                if lj == li: continue
                m = lj * N + idx
                vc = VIA_COST + vpen(idx)
                if free(m) and gn + vc < g.get(m, 1e18):
                    g[m] = gn + vc; came[m] = n; heapq.heappush(openh, (gn + vc + h(m), m))
    return None

def clear_line(grid, li, a, c):
    (ax, ay), (cx_, cy_) = a, c
    n = int(max(abs(cx_ - ax), abs(cy_ - ay)) * 2) + 1
    for k in range(n + 1):
        ix = int(round(ax + (cx_ - ax) * k / n)); iy = int(round(ay + (cy_ - ay) * k / n))
        if grid[li * N + iy * NX + ix]: return False
    return True

def emit(grid, path, net, w):
    """smooth each same-layer run by line of sight, then add tracks + vias"""
    runs, cur = [], [path[0]]
    for n in path[1:]:
        if n // N != cur[-1] // N: runs.append(cur); cur = [n]
        else: cur.append(n)
    runs.append(cur)
    nt = nv = 0
    for ri, run in enumerate(runs):
        li = run[0] // N; pts = [((n % N) % NX, (n % N) // NX) for n in run]
        keep, i = [pts[0]], 0
        while i < len(pts) - 1:
            j = len(pts) - 1
            while j > i + 1 and not clear_line(grid, li, pts[i], pts[j]): j -= 1
            keep.append(pts[j]); i = j
        for a, c in zip(keep, keep[1:]):
            t = pcbnew.PCB_TRACK(b); (x0, y0), (x1, y1) = cxy(*a), cxy(*c)
            t.SetStart(pcbnew.VECTOR2I(int(x0 * MM), int(y0 * MM))); t.SetEnd(pcbnew.VECTOR2I(int(x1 * MM), int(y1 * MM)))
            t.SetWidth(int(w * MM)); t.SetLayer(LAYERS[li]); t.SetNet(b.FindNet(net)); b.Add(t); nt += 1
        if ri < len(runs) - 1:
            x, y = cxy(*pts[-1]); v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
            v.SetWidth(int(VIA_D * MM)); v.SetDrill(int(VIA_DRILL * MM)); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(b.FindNet(net)); b.Add(v); nv += 1
    return nt, nv

# ---------- connections to make, from the DRC report ----------
rep = open(sys.argv[2]).read()
pairs = []
for blk in re.findall(r"\[unconnected_items\].*?\n(.*?)\n(?=\[|\s*\n|\Z)", rep, re.S):
    locs = re.findall(r"@\(([\d.]+) mm, ([\d.]+) mm\): .*?\[([^\]]+)\]", blk)
    if len(locs) >= 2: pairs.append((locs[0][2], (float(locs[0][0]), float(locs[0][1])), (float(locs[1][0]), float(locs[1][1]))))
first = os.environ.get("MAZE_FIRST", "").split()      # route these nets first, in this order
pairs.sort(key=lambda pr: first.index(pr[0]) if pr[0] in first else len(first))
print("connections to route:", len(pairs), flush=True)

done = 0
for net, A, B_ in pairs:
    add_items()
    cls = clusters(net); ka, kb = item_at(cls, *A), item_at(cls, *B_)
    if ka is None or kb is None: print(f"  {net}: endpoint not found", flush=True); continue
    if ka == kb: print(f"  {net}: already connected", flush=True); continue
    w = width(net)
    grid = build_grid(w, net)
    vgrid = build_grid(VIA_D, net)
    src, dst = seed_cells(cls[ka]), seed_cells(cls[kb])
    src = {n for n in src if grid[n] == 0}; dst = {n for n in dst if grid[n] == 0}
    if not src or not dst: print(f"  {net}: no free seed cells ({len(src)}/{len(dst)})", flush=True); continue
    path = astar(grid, src, dst)
    if not path and os.environ.get("RIPUP") == "1":
        sg = array("H", bytes(2 * NL * N)); svg = array("H", bytes(2 * NL * N))
        grid = build_grid(w, net, sg); vgrid = build_grid(VIA_D, net, svg)
        src = {n for n in seed_cells(cls[ka]) if grid[n] == 0}; dst = {n for n in seed_cells(cls[kb]) if grid[n] == 0}
        path = astar(grid, src, dst, sg, svg) if src and dst else None
        if path:
            hit = set()
            pts = [n for i, n in enumerate(path) if sg[n] or (i and path[i - 1] // N != n // N and any(svg[l * N + n % N] for l in range(NL)))]
            for it in items:
                if id(it) not in SOFT or SOFT[id(it)] in hit: continue
                infl = infl_for(it, VIA_D, net) + RES
                k, g_ = it[2], it[3]
                for n in pts:
                    x, y = cxy((n % N) % NX, (n % N) // NX)
                    if k in ("circle", "hole") and math.hypot(x - g_[0], y - g_[1]) <= g_[2] + infl: hit.add(SOFT[id(it)]); break
                    if k == "seg":
                        ax, ay, bx, by, R = g_; dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
                        u = 0 if L2 == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L2))
                        if math.hypot(x - ax - u * dx, y - ay - u * dy) <= R + infl: hit.add(SOFT[id(it)]); break
            victims = [t for t in b.GetTracks() if not t.IsLocked() and t.GetNetname() in hit]
            nt, nv = emit(grid, path, net, w)
            for t in victims: b.Remove(t)
            pcbnew.SaveBoard(sys.argv[1], b)
            print(f"  {net}: routed by rip-up ({nt} segments, {nv} vias), ripped {len(victims)} items of {sorted(hit)}", flush=True)
            os._exit(3)        # pcbnew: no further board walking after Remove() -> caller re-runs DRC + maze
    if not path: print(f"  {net}: no path", flush=True); continue
    nt, nv = emit(grid, path, net, w); done += 1
    print(f"  {net}: routed, {nt} segments, {nv} vias", flush=True)
    pcbnew.SaveBoard(sys.argv[1], b)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard(sys.argv[1], b)
print("routed", done, "of", len(pairs), flush=True)
import os; os._exit(0)
