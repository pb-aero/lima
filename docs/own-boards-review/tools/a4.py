import sys, pickle, collections, math
B = pickle.load(open(sys.argv[1], 'rb'))
def area(pts):
    return abs(sum(pts[i][0]*pts[i-1][1]-pts[i-1][0]*pts[i][1] for i in range(len(pts))))/2
for n in sys.argv[2].split(','):
    print('==', n)
    for L in ['F.Cu','In2.Cu','B.Cu']:
        ts = [t for t in B[L]['tracks'] if t['net']==n]
        rs = [r for r in B[L]['regions'] if r['net']==n]
        if not ts and not rs: continue
        wl = collections.Counter()
        for t in ts: wl[round(t['w'],3)] += t['L']
        print(f'  {L}: tracks {sorted(((w, round(l,2)) for w,l in wl.items()))}  pours {[round(area(r["pts"]),1) for r in rs]} mm2')
    vias = [f for f in B['F.Cu']['flashes'] if f['net']==n and f['func'][:1]==['ViaPad']]
    print('  vias', len(vias))
