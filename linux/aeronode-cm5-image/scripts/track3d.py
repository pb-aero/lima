#!/usr/bin/env python3
"""ArduPilot dataflash log (.BIN) -> self-contained offline 3D trajectory viewer (.html).

usage: track3d.py LOG.BIN [OUT.html] [--title "BB1 walk"]

Two tracks, both in METRES relative to an origin, so the HTML holds no coordinates at all:
  * EKF  : XKF1 PN/PE/PD of core 0 (the EKF's own local position; exists even without GPS).
  * GPS  : GPS Lat/Lng/Alt (fix >= 3D) converted to local ENU about the EKF origin (ORGN), or about the
           first 3D fix if the EKF never set an origin. Colour/tooltip carry sats, HDOP and hAcc (GPA).
Also the EKF's "using GPS?" state over time is approximated from whether XKF1 moves with the GPS: shown
as stats only. The output is a single HTML file with no network dependencies. Keep it local: even
relative tracks reveal the shape of where you walked.
"""
import html
import json
import math
import sys

from pymavlink import DFReader

R_EARTH = 6378137.0


def enu(lat, lon, alt, lat0, lon0, alt0):
    dn = math.radians(lat - lat0) * R_EARTH
    de = math.radians(lon - lon0) * R_EARTH * math.cos(math.radians(lat0))
    return de, dn, alt - alt0


def thin(rows, min_dt):
    out, last = [], -1e9
    for r in rows:
        if r[0] - last >= min_dt:
            out.append(r)
            last = r[0]
    return out


def read(path):
    log = DFReader.DFReader_binary(path, zero_time_base=True)
    gps, gpa, ekf, origin, t0 = [], {}, [], None, None
    while True:
        m = log.recv_match(type=["GPS", "GPA", "XKF1", "ORGN"])
        if m is None:
            break
        t = m.TimeUS / 1e6
        if t0 is None:
            t0 = t
        typ = m.get_type()
        if typ == "GPS" and getattr(m, "I", 0) == 0:
            gps.append((t, m.Status, m.Lat, m.Lng, m.Alt, m.NSats, m.HDop))
        elif typ == "GPA" and getattr(m, "I", 0) == 0:
            gpa[round(t, 1)] = getattr(m, "HAcc", None)
        elif typ == "XKF1" and getattr(m, "C", 0) == 0:
            ekf.append((t, m.PE, m.PN, -m.PD))
        elif typ == "ORGN" and getattr(m, "Type", 0) == 0 and m.Lat != 0 and origin is None:
            origin = (m.Lat, m.Lng, m.Alt)
    return gps, gpa, ekf, origin, t0 or 0.0


def build(path, title):
    gps, gpa, ekf, origin, t0 = read(path)
    good = [g for g in gps if g[1] >= 3 and g[2] != 0]
    src = "EKF origin"
    if origin is None and good:
        origin, src = (good[0][2], good[0][3], good[0][4]), "first 3D GPS fix"
    gtrack = []
    if origin:
        for t, st, la, lo, al, ns, hd in good:
            e, n, u = enu(la, lo, al, *origin)
            hacc = gpa.get(round(t, 1))
            gtrack.append([round(t - t0, 2), round(e, 2), round(n, 2), round(u, 2), ns, round(hd, 2),
                           None if hacc is None else round(hacc, 1)])
    etrack = [[round(t - t0, 2), round(e, 3), round(n, 3), round(u, 3)] for t, e, n, u in thin(ekf, 0.1)]
    gtrack = thin(gtrack, 0.2)
    dur = max([r[0] for r in etrack + gtrack] or [0])

    def extent(tr):
        if not tr:
            return 0.0
        es, ns = [r[1] for r in tr], [r[2] for r in tr]
        return round(math.hypot(max(es) - min(es), max(ns) - min(ns)), 1)
    fix_share = round(100.0 * len(good) / len(gps), 1) if gps else 0.0
    meta = {"title": title, "duration_s": round(dur, 1), "origin": src if origin else "none (no GPS fix, no EKF origin)",
            "gps_points": len(gtrack), "ekf_points": len(etrack), "gps_fix_pct": fix_share,
            "gps_extent_m": extent(gtrack), "ekf_extent_m": extent(etrack),
            "median_hacc_m": (sorted(r[6] for r in gtrack if r[6] is not None)[len(gtrack) // 2]
                              if any(r[6] is not None for r in gtrack) else None)}
    return meta, gtrack, etrack


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f6f7f9;--panel:#fff;--ink:#16181d;--mute:#5d6470;--line:#d9dde3;--gps:#d9822b;--ekf:#1f8fa3;--grid:#e3e6ea;--axis:#9aa1ab}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f1115;--panel:#171a20;--ink:#e8eaed;--mute:#9aa1ab;--line:#2a2f37;--gps:#ffb14e;--ekf:#49c5d1;--grid:#232831;--axis:#5d6470}}
:root[data-theme=dark]{--bg:#0f1115;--panel:#171a20;--ink:#e8eaed;--mute:#9aa1ab;--line:#2a2f37;--gps:#ffb14e;--ekf:#49c5d1;--grid:#232831;--axis:#5d6470}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,system-ui,Segoe UI,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:16px}h1{font-size:20px;margin:0 0 4px}.sub{color:var(--mute);margin:0 0 12px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-bottom:12px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 10px}.stat b{display:block;font-size:17px}.stat span{color:var(--mute);font-size:12px}
.view{background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
canvas{display:block;width:100%;height:min(62vh,560px);touch-action:none;cursor:grab}
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:10px;border-top:1px solid var(--line)}
.bar label{display:flex;gap:5px;align-items:center;color:var(--mute)}input[type=range]{flex:1;min-width:160px}
button{background:transparent;color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:4px 10px;cursor:pointer}
.sw{display:inline-block;width:14px;height:3px;border-radius:2px;vertical-align:middle}.readout{font-variant-numeric:tabular-nums;color:var(--mute);min-width:260px}
.note{color:var(--mute);font-size:12px;margin-top:10px}
</style></head><body><div class="wrap">
<h1>__TITLE__</h1><p class="sub">__SUB__ No coordinates are stored in this file.</p>
<div class="stats" id="stats"></div>
<div class="view"><canvas id="c"></canvas>
<div class="bar">
<label><input type="checkbox" id="sg" checked><span class="sw" style="background:var(--gps)"></span>GPS</label>
<label><input type="checkbox" id="se" checked><span class="sw" style="background:var(--ekf)"></span>EKF</label>
<label><input type="checkbox" id="sgr" checked>grid</label>
<button id="top">top view</button><button id="rst">reset</button>
<input type="range" id="tt" min="0" max="1000" value="1000"><span class="readout" id="ro"></span>
</div></div>
<p class="note">Drag to orbit, scroll or pinch to zoom, slider to scrub time. GPS points are 3D fixes only.
If the EKF track is a dot while GPS wanders, the EKF was in constant-position mode (not using GPS).</p>
</div>
<script>
const META=__META__, G=__GPS__, E=__EKF__;
(function(){
const st=document.getElementById('stats');
const S=[[META.duration_s+' s','duration'],[META.gps_points,'GPS 3D fixes'],[META.gps_fix_pct+' %','of GPS samples with 3D fix'],
 [META.gps_extent_m+' m','GPS track extent'],[META.ekf_extent_m+' m','EKF track extent'],[META.median_hacc_m==null?'—':META.median_hacc_m+' m','median GPS hAcc']];
st.innerHTML=S.map(s=>'<div class="stat"><b>'+s[0]+'</b><span>'+s[1]+'</span></div>').join('');
const cv=document.getElementById('c'),ctx=cv.getContext('2d'),css=getComputedStyle(document.documentElement);
const col=k=>css.getPropertyValue(k).trim();
let az=-0.7,el=0.55,zoom=1,W=0,H=0,showG=true,showE=true,showGrid=true,tcut=1;
const all=G.concat(E);let span=1,cx=0,cy=0,cz=0,zmin=0;
if(all.length){const xs=all.map(p=>p[1]),ys=all.map(p=>p[2]),zs=all.map(p=>p[3]);
 cx=(Math.min(...xs)+Math.max(...xs))/2;cy=(Math.min(...ys)+Math.max(...ys))/2;cz=(Math.min(...zs)+Math.max(...zs))/2;
 span=Math.max(Math.max(...xs)-Math.min(...xs),Math.max(...ys)-Math.min(...ys),Math.max(...zs)-Math.min(...zs),2);zmin=Math.min(...zs);}
const TMAX=META.duration_s||1;
function step(s){const r=s/6,p=Math.pow(10,Math.floor(Math.log10(r))),m=r/p;return (m<2?1:m<5?2:5)*p}
const GS=step(span);
function resize(){const r=cv.getBoundingClientRect(),d=Math.min(devicePixelRatio||1,2);cv.width=r.width*d;cv.height=r.height*d;ctx.setTransform(d,0,0,d,0,0);W=r.width;H=r.height;draw()}
function proj(x,y,z){x-=cx;y-=cy;z-=cz;const ca=Math.cos(az),sa=Math.sin(az),ce=Math.cos(el),se=Math.sin(el);
 const X=x*ca-y*sa,Y=x*sa+y*ca;const sx=X,sy=Y*se+z*ce,d=-Y*ce+z*se;const k=Math.min(W,H)/(span*1.6)*zoom;return [W/2+sx*k,H/2-sy*k,d]}
function line(a,b,c,w){const p=proj(...a),q=proj(...b);ctx.strokeStyle=c;ctx.lineWidth=w;ctx.beginPath();ctx.moveTo(p[0],p[1]);ctx.lineTo(q[0],q[1]);ctx.stroke()}
function draw(){if(!W)return;ctx.clearRect(0,0,W,H);
 const z0=zmin,half=Math.ceil(span/GS/2+1)*GS;
 if(showGrid){for(let v=-half;v<=half+1e-9;v+=GS){line([cx-half,cy+v,z0],[cx+half,cy+v,z0],col('--grid'),1);line([cx+v,cy-half,z0],[cx+v,cy+half,z0],col('--grid'),1)}
  ctx.fillStyle=col('--axis');ctx.font='11px system-ui';const n=proj(cx,cy+half,z0);ctx.fillText('N',n[0]+4,n[1]);const e=proj(cx+half,cy,z0);ctx.fillText('E',e[0]+4,e[1]);
  const s=proj(cx-half,cy-half,z0);ctx.fillText('grid '+GS+' m',s[0]+4,s[1]+14)}
 const tc=tcut*TMAX;
 function track(T,c,w){let prev=null,k=0;ctx.globalAlpha=1;for(const p of T){if(p[0]>tc)break;k++;if(prev){line(prev.slice(1,4),p.slice(1,4),c,w);
   if(showGrid&&T===E&&k%25===0){const a=proj(p[1],p[2],p[3]),b=proj(p[1],p[2],z0);ctx.globalAlpha=.25;ctx.strokeStyle=c;ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke();ctx.globalAlpha=1}}prev=p}
  if(prev){const q=proj(prev[1],prev[2],prev[3]);ctx.fillStyle=c;ctx.beginPath();ctx.arc(q[0],q[1],4.5,0,7);ctx.fill()}return prev}
 const lg=showG?track(G,col('--gps'),1.2):null,le=showE?track(E,col('--ekf'),2.4):null;
 const ro=document.getElementById('ro');let s='t = '+tc.toFixed(1)+' s';
 if(lg)s+=' · GPS '+lg[4]+' sats, HDOP '+lg[5]+(lg[6]!=null?', hAcc '+lg[6]+' m':'');ro.textContent=s}
let drag=null;cv.addEventListener('pointerdown',e=>{drag=[e.clientX,e.clientY];cv.setPointerCapture(e.pointerId);cv.style.cursor='grabbing'});
cv.addEventListener('pointermove',e=>{if(!drag)return;az+=(e.clientX-drag[0])*0.008;el=Math.max(-0.05,Math.min(1.55,el+(e.clientY-drag[1])*0.008));drag=[e.clientX,e.clientY];draw()});
cv.addEventListener('pointerup',()=>{drag=null;cv.style.cursor='grab'});
cv.addEventListener('wheel',e=>{e.preventDefault();zoom*=Math.exp(-e.deltaY*0.0015);zoom=Math.max(0.2,Math.min(40,zoom));draw()},{passive:false});
document.getElementById('sg').onchange=e=>{showG=e.target.checked;draw()};document.getElementById('se').onchange=e=>{showE=e.target.checked;draw()};
document.getElementById('sgr').onchange=e=>{showGrid=e.target.checked;draw()};document.getElementById('tt').oninput=e=>{tcut=e.target.value/1000;draw()};
document.getElementById('top').onclick=()=>{el=1.55;az=0;draw()};document.getElementById('rst').onclick=()=>{az=-0.7;el=0.55;zoom=1;draw()};
matchMedia('(prefers-color-scheme: dark)').addEventListener('change',draw);addEventListener('resize',resize);resize();
})();
</script></body></html>
"""


def main():
    args = sys.argv[1:]
    title = "BB1 trajectory"
    if "--title" in args:
        i = args.index("--title")
        title = args[i + 1]
        del args[i:i + 2]
    if not args:
        sys.exit(__doc__)
    path = args[0]
    out = args[1] if len(args) > 1 else path.rsplit(".", 1)[0] + "_track3d.html"
    meta, g, e = build(path, title)
    sub = (f"Trajectory in metres relative to the {meta['origin']}." if not meta["origin"].startswith("none")
           else "This log has no GPS 3D fix and the EKF never set an origin, so there is no trajectory to place: "
                "the EKF track is its local position only.")
    page = (PAGE.replace("__TITLE__", html.escape(title)).replace("__SUB__", html.escape(sub))
            .replace("__META__", json.dumps(meta)).replace("__GPS__", json.dumps(g, separators=(",", ":")))
            .replace("__EKF__", json.dumps(e, separators=(",", ":"))))
    with open(out, "w") as f:
        f.write(page)
    print(f"wrote {out}: {json.dumps(meta)}")


if __name__ == "__main__":
    main()
