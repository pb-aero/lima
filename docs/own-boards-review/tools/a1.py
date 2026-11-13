import sys, collections, pickle
sys.path.insert(0, sys.argv[1]); import gerb
B = gerb.load_board(sys.argv[2], sys.argv[3])
pickle.dump(B, open(sys.argv[4], 'wb'))
for L, g in sorted(B.items()):
    nets = collections.Counter(r['net'] for r in g['regions'])
    print(L, 'tracks', len(g['tracks']), 'flashes', len(g['flashes']), 'regions', len(g['regions']), 'region nets', nets.most_common(6))
    print('   flash funcs', collections.Counter(tuple(f['func'][:1]) for f in g['flashes']).most_common(6))
def netlen(n):
    out = {}
    for L, g in B.items():
        s = sum(t['L'] for t in g['tracks'] if t['net'] == n)
        if s: out[L] = round(s, 2)
    v = sum(1 for f in B['F.Cu']['flashes'] if f['net'] == n and f['func'][:1] == ['ViaPad'])
    return out, v
for n in ['USB3_0_TX_P', 'USB3_0_TX_N', 'USB3_0_RX_P', 'USB3_0_RX_N', 'PCIE_CLK_P', 'PCIE_CLK_N', 'PCIE_TX_P', 'ETH_P0_P', 'ETH_P0_N', 'USB3_1_DP', 'USB3_1_DM']:
    print(n, netlen(n))
