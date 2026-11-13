import sys, pickle, collections
B = pickle.load(open(sys.argv[1], 'rb'))
want = sys.argv[2].split(',')
for n in want:
    pads = set()
    for L in ('F.Cu', 'B.Cu'):
        for f in B[L]['flashes']:
            if f['net'] == n and f['pin']: pads.add((L, f['pin'][0], f['pin'][1] if len(f['pin'])>1 else '', f['pin'][2] if len(f['pin'])>2 else ''))
    for L in ('F.Cu','B.Cu'):
        for r in B[L]['regions']: pass
    print(n, sorted(pads))
