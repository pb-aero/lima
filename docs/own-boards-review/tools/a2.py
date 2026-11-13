import sys, pickle, math, collections
sys.path.insert(0, sys.argv[1]); import raster as R
B = pickle.load(open(sys.argv[2], 'rb'))
allx = [p[0] for g in B.values() for r in g['regions'] for p in r['pts']]
ally = [p[1] for g in B.values() for r in g['regions'] for p in r['pts']]
x0, x1, y0, y1 = min(allx)-1, max(allx)+1, min(ally)-1, max(ally)+1
W, H = x1-x0, y1-y0
grids = {}
for L in B:
    grids[L] = {}
REF = {'F.Cu': ['In1.Cu'], 'B.Cu': ['In4.Cu'], 'In2.Cu': ['In1.Cu', 'In3.Cu']}
plane = {L: R.raster(B[L], x0, y1, W, H) for L in ['In1.Cu', 'In3.Cu', 'In4.Cu']}
plane_net = {L: collections.Counter(r['net'] for r in B[L]['regions']) for L in plane}
print('planes', plane_net, {L: round(g.mean()*W*H,0) for L,g in plane.items()}, 'board bbox', round(W,1), round(H,1))
def samples(t, step=0.05):
    pts = t['pts']
    for k in range(len(pts)-1):
        (ax, ay), (bx, by) = pts[k], pts[k+1]
        L = math.hypot(bx-ax, by-ay); n = max(1, int(L/step))
        for s in range(n):
            f = (s+0.5)/n; yield ax+(bx-ax)*f, ay+(by-ay)*f, L/n
def segdist(px, py, t):
    best = 1e9
    pts = t['pts']
    for k in range(len(pts)-1):
        (ax, ay), (bx, by) = pts[k], pts[k+1]
        dx, dy = bx-ax, by-ay; LL = dx*dx+dy*dy
        u = 0 if LL == 0 else max(0, min(1, ((px-ax)*dx+(py-ay)*dy)/LL))
        best = min(best, math.hypot(px-ax-u*dx, py-ay-u*dy))
    return best
pairs = [('PCIE_TX_P','PCIE_TX_N'),('PCIE_RX_P','PCIE_RX_N'),('PCIE_CLK_P','PCIE_CLK_N'),('USB3_0_TX_P','USB3_0_TX_N'),('USB3_0_RX_P','USB3_0_RX_N'),('USB3_0_DP','USB3_0_DM'),('USB3_1_DP','USB3_1_DM'),('ETH_P0_P','ETH_P0_N'),('ETH_P1_P','ETH_P1_N'),('ETH_P2_P','ETH_P2_N'),('ETH_P3_P','ETH_P3_N')]
for p, n in pairs:
    print('==', p, n)
    for L in ['F.Cu', 'In2.Cu', 'B.Cu']:
        tp = [t for t in B[L]['tracks'] if t['net'] == p]; tn = [t for t in B[L]['tracks'] if t['net'] == n]
        if not tp and not tn: continue
        widths = sorted(set(round(t['w'],3) for t in tp+tn))
        gaps = collections.Counter(); unc = 0; tot = 0; noref = collections.Counter()
        for t in tp:
            for x, y, dl in samples(t):
                tot += dl
                d = min([segdist(x, y, u) for u in tn] or [99])
                g = round(d - t['w'], 2)
                if g > 0.6: unc += dl
                else: gaps[round(g, 2)] += dl
        for t in tp + tn:
            for x, y, dl in samples(t):
                for ref in REF[L]:
                    if not R.lookup(plane[ref], x0, y1, x, y): noref[ref] += dl
        top = sorted(gaps.items(), key=lambda kv: -kv[1])[:3]
        print(f'  {L}: P {sum(t["L"] for t in tp):.2f} N {sum(t["L"] for t in tn):.2f} mm, w {widths}, gap(edge) mm:len {[(g, round(l,2)) for g,l in top]}, P uncoupled(>0.6) {unc:.2f} mm, off-plane mm {dict((k, round(v,2)) for k,v in noref.items())}')
    vp = [(round(f['x'],2), round(f['y'],2)) for f in B['F.Cu']['flashes'] if f['net'] == p and f['func'][:1]==['ViaPad']]
    vn = [(round(f['x'],2), round(f['y'],2)) for f in B['F.Cu']['flashes'] if f['net'] == n and f['func'][:1]==['ViaPad']]
    print('  vias P', vp, 'N', vn)
