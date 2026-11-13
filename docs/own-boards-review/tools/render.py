import sys, pickle, math
from PIL import Image, ImageDraw, ImageFont
B = pickle.load(open(sys.argv[1], 'rb'))
L = sys.argv[2]; x0, x1, ya, yb = map(float, sys.argv[3].split(','))  # window
nets = sys.argv[4].split(',') ; out = sys.argv[5]
S = float(sys.argv[6]) if len(sys.argv) > 6 else 40  # px per mm
COL = [(230,25,75),(60,180,75),(0,130,200),(245,130,48),(145,30,180),(70,240,240),(240,50,230),(210,245,60),(128,128,0),(0,128,128),(170,110,40),(128,0,0)]
cmap = {n: COL[i % len(COL)] for i, n in enumerate(nets)}
W, H = int((x1-x0)*S), int((yb-ya)*S)
im = Image.new('RGB', (W, H+40*len(nets)//3+60), (255,255,255)); d = ImageDraw.Draw(im)
P = lambda x, y: ((x-x0)*S, (yb-y)*S)
g = B[L]
def col(n, other=(200,200,200)):
    return cmap.get(n, other)
for r in g['regions']:
    c = col(r['net'], (225,225,225) if r['net']=='GND' else (205,205,205))
    if len(r['pts']) > 2: d.polygon([P(*p) for p in r['pts']], fill=c)
for t in g['tracks']:
    c = col(t['net'], (150,150,150))
    d.line([P(*p) for p in t['pts']], fill=c, width=max(1, int(t['w']*S)))
for f in g['flashes']:
    c = col(f['net'], (120,120,120))
    x, y = P(f['x'], f['y'])
    if f['func'][:1] == ['ViaPad']:
        r = f['params'][0]*S/2 if isinstance(f['params'], list) else 0.225*S
        d.ellipse([x-r, y-r, x+r, y+r], fill=c, outline=(0,0,0))
        d.ellipse([x-r/2.5, y-r/2.5, x+r/2.5, y+r/2.5], fill=(0,0,0))
    else:
        p = f['params']
        if isinstance(p, list) and f['shape'] in ('R','O'):
            w, h = p[0]*S/2, p[1]*S/2; d.rectangle([x-w, y-h, x+w, y+h], fill=c, outline=(0,0,0))
        elif isinstance(p, list) and f['shape'] == 'C':
            r = p[0]*S/2; d.ellipse([x-r, y-r, x+r, y+r], fill=c, outline=(0,0,0))
        elif isinstance(p, str) and f['shape'].startswith('RoundRect'):
            v = [float(q) for q in p.split('X')]
            pts = [(f['x']+v[1+2*k], f['y']+v[2+2*k]) for k in range(4)]
            d.polygon([P(*q) for q in pts], fill=c, outline=(0,0,0))
        else:
            d.rectangle([x-3, y-3, x+3, y+3], fill=c, outline=(0,0,0))
        if f['pin']:
            d.text((x+2, y-6), f['pin'][0]+'.'+(f['pin'][1] if len(f['pin'])>1 else ''), fill=(0,0,0))
# grid ticks every 5 mm
for gx in range(int(x0)//5*5, int(x1)+1, 5):
    X, _ = P(gx, ya); d.line([(X,0),(X,8)], fill=(0,0,0)); d.text((X+2, 0), str(gx), fill=(0,0,0))
for gy in range(int(ya)//5*5, int(yb)+1, 5):
    _, Y = P(x0, gy); d.line([(0,Y),(8,Y)], fill=(0,0,0)); d.text((10, Y-5), str(gy), fill=(0,0,0))
y = H + 5
for i, n in enumerate(nets):
    xx = 10 + (i % 3) * (W//3)
    d.rectangle([xx, y, xx+14, y+14], fill=cmap[n]); d.text((xx+18, y+2), n, fill=(0,0,0))
    if i % 3 == 2: y += 20
d.text((10, y+20), f'{L}  window x {x0}..{x1} y {ya}..{yb}', fill=(0,0,0))
im.save(out)
