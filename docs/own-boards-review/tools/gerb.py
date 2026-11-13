"""Minimal Gerber X2 parser for KiCad output: tracks, arcs, flashes, regions, with net/pin attributes."""
import re, math, json, sys, os

def parse(path):
    txt = open(path).read()
    # split into commands: extended (%...%) and normal (...*)
    toks = re.findall(r'%[^%]*%|[^%*]+\*', txt, re.S)
    ap = {}          # dcode -> dict(shape, params, func)
    cur_ap_attr = {}
    obj_attr = {}
    cur = None
    x = y = 0.0
    mode = 'G01'
    region = False
    region_pts = []
    regions = []; tracks = []; flashes = []
    fs = 1e6
    for t in toks:
        t = t.strip()
        if t.startswith('%'):
            body = t[1:-1].strip().rstrip('*')
            if body.startswith('FSLA'):
                m = re.match(r'FSLAX(\d)(\d)Y', body); fs = 10 ** int(m.group(2))
            elif body.startswith('TA.'):
                k, *v = body[3:].split(','); cur_ap_attr[k] = v
            elif body.startswith('TO.'):
                k, *v = body[3:].split(','); obj_attr[k] = v
            elif body.startswith('TD'):
                k = body[2:].lstrip('.')
                if not k:
                    obj_attr = {}; cur_ap_attr = {}
                else:
                    obj_attr.pop(k, None); cur_ap_attr.pop(k, None)
            elif body.startswith('AD'):
                m = re.match(r'ADD(\d+)([A-Za-z_0-9]+?)(?:,(.*))?$', body, re.S)
                if m:
                    d = int(m.group(1)); shape = m.group(2)
                    params = [float(p) for p in m.group(3).split('X')] if m.group(3) and shape in ('C', 'R', 'O', 'P') else (m.group(3) or '')
                    ap[d] = dict(shape=shape, params=params, func=cur_ap_attr.get('AperFunction', [''])[:])
            continue
        cmd = t.rstrip('*')
        if cmd.startswith('G04') or not cmd:
            continue
        if cmd == 'G36': region = True; region_pts = []; continue
        if cmd == 'G37':
            if region_pts: regions.append(dict(pts=region_pts, net=obj_attr.get('N', [''])[0]))
            region = False; region_pts = []; continue
        for g in ('G01', 'G02', 'G03'):
            if cmd.startswith(g):
                mode = g; cmd = cmd[3:]
        if cmd in ('G75', 'G74', ''):
            continue
        m = re.match(r'^D(\d+)$', cmd)
        if m and int(m.group(1)) >= 10:
            cur = int(m.group(1)); continue
        m = re.match(r'^(?:X(-?\d+))?(?:Y(-?\d+))?(?:I(-?\d+))?(?:J(-?\d+))?D0?([123])$', cmd)
        if not m:
            continue
        nx = int(m.group(1)) / fs if m.group(1) else x
        ny = int(m.group(2)) / fs if m.group(2) else y
        i = int(m.group(3)) / fs if m.group(3) else 0.0
        j = int(m.group(4)) / fs if m.group(4) else 0.0
        op = m.group(5)
        if region:
            if op == '2':
                if region_pts: regions.append(dict(pts=region_pts, net=obj_attr.get('N', [''])[0]))
                region_pts = [(nx, ny)]
            elif op == '1':
                if mode == 'G01': region_pts.append((nx, ny))
                else: region_pts += arcpts(x, y, nx, ny, i, j, mode)[1:]
            x, y = nx, ny; continue
        a = ap.get(cur, {})
        if op == '1':
            w = a.get('params', [0])[0] if a.get('shape') == 'C' else 0
            if mode == 'G01':
                L = math.hypot(nx - x, ny - y); pts = [(x, y), (nx, ny)]
            else:
                pts = arcpts(x, y, nx, ny, i, j, mode)
                L = sum(math.hypot(pts[k+1][0]-pts[k][0], pts[k+1][1]-pts[k][1]) for k in range(len(pts)-1))
            tracks.append(dict(pts=pts, w=w, L=L, net=obj_attr.get('N', [''])[0], func=a.get('func')))
        elif op == '3':
            flashes.append(dict(x=nx, y=ny, d=cur, shape=a.get('shape'), params=a.get('params'), func=a.get('func'),
                                net=obj_attr.get('N', [''])[0], pin=obj_attr.get('P', [])))
        x, y = nx, ny
    return dict(tracks=tracks, flashes=flashes, regions=regions, ap=ap)

def arcpts(x0, y0, x1, y1, i, j, mode, n=16):
    cx, cy = x0 + i, y0 + j
    r = math.hypot(x0 - cx, y0 - cy)
    a0 = math.atan2(y0 - cy, x0 - cx); a1 = math.atan2(y1 - cy, x1 - cx)
    if mode == 'G03':  # CCW
        while a1 <= a0: a1 += 2 * math.pi
    else:
        while a1 >= a0: a1 -= 2 * math.pi
    return [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]

def load_board(d, name):
    layers = {}
    for f in os.listdir(d):
        m = re.match(name + r'-(F_Cu|In\d_Cu|B_Cu)\.', f)
        if m: layers[m.group(1).replace('_', '.')] = parse(os.path.join(d, f))
    return layers
