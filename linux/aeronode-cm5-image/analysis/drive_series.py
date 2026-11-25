"""23 Nov drive -> 30 s binned time series + stats, WITHOUT coordinates (safe to publish).
argv: track_points.json batt.csv power.csv out.json
track point = [lat, lon, kmh, t_s, utc]; only kmh and utc are read."""
import calendar
import json
import statistics as st
import sys
import time

trk, batt, powr, out = sys.argv[1:5]
BIN = 30.0


def iso(s):
    sec, _, frac = s.partition(".")
    return calendar.timegm(time.strptime(sec, "%Y-%m-%dT%H:%M:%S")) + (float("0." + frac) if frac else 0.0)


def rows(path):
    r = []
    for line in open(path):
        f = line.strip().split(",")
        try:
            r.append((iso(f[0]), [float(x) if x else None for x in f[1:]]))
        except (ValueError, IndexError):
            pass
    return r


B = rows(batt)            # soc, vbat_mv, ibat_ma, tdie
W = rows(powr)            # cpu_c, pmic_w
G = [(p[4], p[2]) for p in json.load(open(trk))]   # (utc, kmh) only
t0 = min(B[0][0], G[0][0])
t1 = max(B[-1][0], G[-1][0])
nb = int((t1 - t0) // BIN) + 1
acc = [dict() for _ in range(nb)]


def add(t, k, v):
    if v is None:
        return
    i = int((t - t0) // BIN)
    if 0 <= i < nb:
        acc[i].setdefault(k, []).append(v)


for t, (soc, mv, ma, td) in ((t, (r + [None] * 4)[:4]) for t, r in B):
    add(t, "soc", soc); add(t, "v", mv / 1000 if mv else None); add(t, "a", -ma / 1000 if ma is not None else None)
    add(t, "w", -mv * ma / 1e6 if mv and ma is not None else None); add(t, "chg_c", td)
for t, (cpu, pw) in ((t, (r + [None] * 2)[:2]) for t, r in W):
    add(t, "cpu_c", cpu); add(t, "pi_w", pw)
for t, k in G:
    add(t, "kmh", k)

series = []
for i, a in enumerate(acc):
    d = {"m": round(i * BIN / 60, 2)}
    for k, v in a.items():
        d[k] = round(st.fmean(v), 3)
    series.append(d)

# stats
bt = [t for t, _ in B]
wh = sum(-B[i][1][1] * B[i][1][2] / 1e6 * (B[i + 1][0] - B[i][0]) / 3600
         for i in range(len(B) - 1) if B[i][1][1] and B[i][1][2] is not None and B[i + 1][0] - B[i][0] < 10)
mah = sum(-B[i][1][2] * (B[i + 1][0] - B[i][0]) / 3600
          for i in range(len(B) - 1) if B[i][1][2] is not None and B[i + 1][0] - B[i][0] < 10)
dur_h = (bt[-1] - bt[0]) / 3600
pw = [-r[1] * r[2] / 1e6 for _, r in B if r[1] and r[2] is not None]
cur = [-r[2] / 1000 for _, r in B if r[2] is not None]
cpu = [r[0] for _, r in W if r[0] is not None]
piw = [r[1] for _, r in W if r[1] is not None]
tdie = [r[3] for _, r in B if r[3] is not None]
mov = [(t, k) for t, k in G if k > 3.6]


def band(lo, hi):
    """mean pack W while GPS speed in [lo, hi) km/h, matched by 30 s bin."""
    v = [s["w"] for s in series if "w" in s and "kmh" in s and lo <= s["kmh"] < hi]
    return (round(st.fmean(v), 2), len(v)) if v else (None, 0)


# first/last 5 min means for V (independent of SoC, which is integrated IBAT)
def mean_window(rows_, idx, a, b):
    v = [r[idx] for t, r in rows_ if a <= t < b and r[idx] is not None]
    return st.fmean(v) if v else None


stats = {
    "utc_start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(bt[0])),
    "utc_end": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(bt[-1])),
    "batt_rows": len(B), "power_rows": len(W), "gps_points": len(G),
    "dur_min": round(dur_h * 60, 1),
    "gps_first_min": round((G[0][0] - t0) / 60, 1), "gps_last_min": round((G[-1][0] - t0) / 60, 1),
    "moving_min": round(sum(1 for _ in mov) / 60, 1), "vmax": round(max(k for _, k in G)),
    "soc_start": B[0][1][0], "soc_end": B[-1][1][0],
    "v_start5": round(mean_window(B, 1, bt[0], bt[0] + 300) / 1000, 3),
    "v_end5": round(mean_window(B, 1, bt[-1] - 300, bt[-1] + 1) / 1000, 3),
    "wh": round(wh, 2), "mah": round(mah), "w_mean": round(st.fmean(pw), 2),
    "w_p95": round(sorted(pw)[int(0.95 * len(pw))], 2), "w_max": round(max(pw), 2), "w_min": round(min(pw), 2),
    "a_mean": round(st.fmean(cur), 3),
    "pi_w_mean": round(st.fmean(piw), 2), "pi_w_p95": round(sorted(piw)[int(0.95 * len(piw))], 2),
    "cpu_min": round(min(cpu), 1), "cpu_max": round(max(cpu), 1),
    "tdie_min": round(min(tdie), 1), "tdie_max": round(max(tdie), 1),
    "soc_per_h": round((B[0][1][0] - B[-1][1][0]) / dur_h, 2),
    "w_parked": band(0, 3.6), "w_town": band(3.6, 70), "w_road": band(70, 200),
}
json.dump({"stats": stats, "series": series}, open(out, "w"), separators=(",", ":"))
print(json.dumps(stats, indent=1))
