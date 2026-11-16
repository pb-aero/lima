"""Build the GMA match board report and its stripboard diagram.

  python3 -I kicad/gma-match-board/doc/make_report.py <record_sha> <source_sha>     (run from the lima repo root)

Writes kicad/gma-match-board/doc/stripboard-layout.svg (drawn from veroboard.py's checked layout) and
docs/LIMA_gma_match_board.html (self-contained: schematic and stripboard inlined, no external links), the lane
copy of the report. record_sha = `git -C <company repo> log -1 --format=%h -- record/`, measured, never chosen.
"""
import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import veroboard  # noqa: E402  (checked layout; check() must pass)

NETCOL = {
    "DAC_P": "#2f6fe0", "DAC_N": "#7a5cf0", "AIN1": "#0aa2c0", "AIN1REF": "#62a8d8", "COMMS_TAP": "#17b39a",
    "+3V3A": "#e0443e", "GND": "#6f7874", "EAR_HI": "#f08c1a", "EAR_RTN": "#b86a2e", "MIC_HI": "#d4b012",
    "MIC_LO": "#a8902c", "PV_SEC": "#f5a96b", "PV_ATT": "#e2743a", "SPK_L_A": "#e0529c", "SPK_L_B": "#a8366f",
    "SPK_R_A": "#c47ae2", "SPK_R_B": "#8a4fb0"}
PIN_SIDE = {"J1": -1, "J2": -1, "J3": 1, "J4": 1}


def stripboard_svg():
    bad, find, segs, design = veroboard.check()
    if bad:
        sys.exit("veroboard check failed; refusing to draw an unchecked layout")
    pin2net = {p: n for n, ps in design.items() for p in ps}
    OFF, U, ML, MT = veroboard.OFF, 18, 118, 40
    X = lambda c: ML + c * U
    Y = lambda r: MT + (r + OFF) * U          # r is the logical row used in veroboard.py
    Wd, Ht = X(veroboard.COLS + 4), Y(veroboard.ROWS - OFF + 0.8)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {Wd:.0f} {Ht:.0f}" font-family="ui-monospace,Menlo,monospace">',
         f'<rect x="0" y="0" width="{Wd:.0f}" height="{Ht:.0f}" fill="#ffffff"/>',
         f'<rect x="{X(-0.6)}" y="{Y(-OFF - 0.6)}" width="{(veroboard.COLS - 1 + 1.2) * U}" height="{(veroboard.ROWS - 1 + 1.2) * U}" rx="4" fill="#ecd8b6" stroke="#a37a48"/>']
    seg_net = {}
    for ref, _, _, pins in veroboard.PARTS:
        for p, (c, r) in pins.items():
            seg_net[find(veroboard.seg_of(c, r, segs))] = pin2net[veroboard.PIN_MAP.get(f"{ref}.{p}", f"{ref}.{p}")]
    for r, a, b in segs:                           # copper strips, seen through the board, with a net stripe
        o.append(f'<rect x="{X(a) - 0.45 * U:.1f}" y="{Y(r) - 0.31 * U:.1f}" width="{(b - a + 0.9) * U:.1f}" height="{0.62 * U:.1f}" fill="#f2c18c" opacity="0.65"/>')
        n = seg_net.get(find((r, a, b)))
        if n:
            o.append(f'<line x1="{X(a) - 0.3 * U:.1f}" y1="{Y(r)}" x2="{X(b) + 0.3 * U:.1f}" y2="{Y(r)}" stroke="{NETCOL[n]}" stroke-width="2.4"/>')
    for r in range(-OFF, veroboard.ROWS - OFF):
        for c in range(veroboard.COLS):
            o.append(f'<circle cx="{X(c)}" cy="{Y(r)}" r="1.5" fill="#5a4630"/>')
        o.append(f'<text x="{X(-1.5)}" y="{Y(r) + 3.5}" font-size="10" text-anchor="middle" fill="#57534e">{chr(65 + r + OFF)}</text>')
    for c in [0] + list(range(4, veroboard.COLS, 5)) + [veroboard.COLS - 1]:
        o.append(f'<text x="{X(c)}" y="{Y(-OFF - 1.3)}" font-size="10" text-anchor="middle" fill="#57534e">{c + 1}</text>')
    for c, r in veroboard.MOUNT:
        o.append(f'<circle cx="{X(c)}" cy="{Y(r)}" r="{0.55 * U}" fill="#3b2a19"/>')
    for (a, b) in veroboard.LINKS:                  # links on the component side
        n = seg_net.get(find(veroboard.seg_of(*a, segs)))
        long_ = abs(a[1] - b[1]) > 1
        col = NETCOL[n] if long_ else "#8a8f94"
        o.append(f'<line x1="{X(a[0])}" y1="{Y(a[1])}" x2="{X(b[0])}" y2="{Y(b[1])}" stroke="{col}" stroke-width="{4 if long_ else 3}" stroke-linecap="round"/>')
        for c, r in (a, b):
            o.append(f'<circle cx="{X(c)}" cy="{Y(r)}" r="3" fill="{col}" stroke="#1c1917" stroke-width="0.8"/>')
    for r, cs in veroboard.CUTS.items():            # track cuts, made from the copper side
        for c in cs:
            d = 0.3 * U
            o.append(f'<path d="M{X(c) - d},{Y(r) - d}L{X(c) + d},{Y(r) + d}M{X(c) - d},{Y(r) + d}L{X(c) + d},{Y(r) - d}" stroke="#b91c1c" stroke-width="2.6"/>')

    def label(x, y, t, size=11, anchor="middle", fill="#1c1917", weight="600"):
        o.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" fill="{fill}" '
                 f'stroke="#ffffff" stroke-width="3" paint-order="stroke">{html.escape(t)}</text>')
    for ref, kind, _, pins in veroboard.PARTS:
        pts = {p: (X(c), Y(r)) for p, (c, r) in pins.items()}
        cx = sum(x for x, _ in pts.values()) / len(pts)
        cy = sum(y for _, y in pts.values()) / len(pts)
        if kind == "header":
            ys = [y for _, y in pts.values()]
            o.append(f'<rect x="{cx - 0.45 * U:.1f}" y="{min(ys) - 0.5 * U:.1f}" width="{0.9 * U:.1f}" height="{max(ys) - min(ys) + U:.1f}" fill="#1f2937" opacity="0.85" rx="2"/>')
            for p, (x, y) in pts.items():
                net = pin2net[f"{ref}.{p}"]
                o.append(f'<rect x="{x - 3}" y="{y - 3}" width="6" height="6" fill="#d4af37"/>')
                s = PIN_SIDE[ref]
                label(x + s * 0.8 * U, y + 3.5, f"{p} {net}", 9, "end" if s < 0 else "start", NETCOL[net], "500")
            label(cx, min(ys) - 0.75 * U, ref)
        elif kind == "pigtail":
            hx = X(veroboard.COLS + 1.6)
            for p, (x, y) in pts.items():
                net = pin2net[f"{ref}.{p}"]
                o.append(f'<path d="M{x},{y} C{x + 18},{y} {hx - 18},{cy + (y - cy) * 0.5} {hx},{cy + (y - cy) * 0.5}" fill="none" stroke="{NETCOL[net]}" stroke-width="2.4"/>')
                o.append(f'<circle cx="{x}" cy="{y}" r="3" fill="#111"/>')
            o.append(f'<rect x="{hx}" y="{cy - 0.9 * U:.1f}" width="{0.9 * U}" height="{1.8 * U}" fill="#efe9dc" stroke="#78716c"/>')
            label(hx + 0.45 * U, cy - 1.15 * U, "J5 (GH)")
        elif kind in ("res", "diode"):
            a, b = (pins["A"], pins["K"]) if kind == "diode" else (pins["1"], pins["2"])
            ax, ay, bx, by = X(a[0]), Y(a[1]), X(b[0]), Y(b[1])
            o.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="#6b7280" stroke-width="2"/>')
            o.append(f'<circle cx="{bx}" cy="{by}" r="2.6" fill="#111"/>')
            body = "#e07a2a" if kind == "diode" else "#6f9ad8"
            o.append(f'<circle cx="{ax}" cy="{ay}" r="{0.42 * U}" fill="{body}" stroke="{"#111" if kind == "diode" else "#1e3a8a"}" stroke-width="{2.4 if kind == "diode" else 1}"/>')
            label(ax + 0.62 * U, ay - 0.45 * U, ref, 10, "start")
        elif kind in ("mlcc", "film"):
            for x, y in pts.values():
                o.append(f'<line x1="{cx}" y1="{cy}" x2="{x}" y2="{y}" stroke="#6b7280" stroke-width="2"/>')
                o.append(f'<circle cx="{x}" cy="{y}" r="2.6" fill="#111"/>')
            if kind == "film":
                o.append(f'<rect x="{cx - 0.3 * U:.1f}" y="{cy - 0.75 * U:.1f}" width="{0.6 * U:.1f}" height="{1.5 * U:.1f}" fill="#b23a35" rx="1.5"/>')
            else:
                o.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{0.42 * U:.1f}" ry="{0.6 * U:.1f}" fill="#c9a25a" stroke="#8a6a2a"/>')
            label(cx + 0.6 * U, cy + 3.5, ref, 10, "start")
        else:   # transformers: body outline, legs, pin 1
            w, h = (12.8 / 2.54, 9.0 / 2.54) if kind == "lp5001" else (10.4 / 2.54, 7.9 / 2.54)
            o.append(f'<rect x="{cx - w / 2 * U:.1f}" y="{cy - h / 2 * U:.1f}" width="{w * U:.1f}" height="{h * U:.1f}" fill="#9ca3af" opacity="0.55" stroke="#374151" stroke-width="1.4" rx="2"/>')
            for p, (x, y) in pts.items():
                o.append(f'<circle cx="{x}" cy="{y}" r="{3.6 if p == "1" else 2.8}" fill="{"#b91c1c" if p == "1" else "#111"}"/>')
            label(cx, cy + 4, ref, 12)
    o.append("</svg>")
    return "\n".join(o)


def schematic_svg():
    s = open(os.path.join(HERE, "gma-match-board.svg"), encoding="utf-8").read()
    s = s[s.index("<svg"):]
    return re.sub(r'\s(width|height)="[^"]*mm"', "", s, count=2)


CSS = """
 :root{color-scheme:light dark}
 body{margin:0;padding:32px 24px;font:16px/1.65 system-ui,-apple-system,"Segoe UI",sans-serif;
      color:#1c1917;background:#fdfdfc;max-width:62rem;margin-inline:auto}
 h1{font-size:1.9rem;line-height:1.25;margin:0 0 .3em}
 h2{font-size:1.3rem;margin:2.2em 0 .5em;padding-bottom:.25em;border-bottom:2px solid #e7e5e4}
 code{font:13.5px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;background:#f5f5f4;padding:1px 5px;border-radius:3px}
 table{border-collapse:collapse;width:100%;margin:1em 0;font-size:14.5px;display:block;overflow-x:auto}
 th,td{border:1px solid #d6d3d1;padding:7px 10px;text-align:left;vertical-align:top}
 th{background:#f5f5f4;font-weight:600}
 td.m{background:#fffbeb;color:#92400e;font-style:italic;white-space:nowrap}
 li{margin:.4em 0}
 .lede{font-size:1.08rem;color:#44403c}
 .key{border-left:4px solid #15803d;background:#f0fdf4;padding:12px 16px;margin:1.2em 0;border-radius:0 6px 6px 0}
 .warn{border-left:4px solid #b45309;background:#fffbeb;padding:12px 16px;margin:1.2em 0;border-radius:0 6px 6px 0}
 .open{border-left:4px solid #b91c1c;background:#fef2f2;padding:12px 16px;margin:1.2em 0;border-radius:0 6px 6px 0}
 .key p,.warn p,.open p{margin:.4em 0}
 .meta{color:#57534e;font-size:14px}
 .tag{font:11.5px/1 ui-monospace,Menlo,monospace;background:#e7e5e4;color:#44403c;padding:2px 5px;border-radius:3px;white-space:nowrap}
 figure{margin:1.5em 0;border:1px solid #d6d3d1;border-radius:6px;overflow:hidden;background:#fff}
 .sheet{overflow:auto;background:#fff}
 .sheet svg{display:block;width:100%;height:auto}
 figcaption{font-size:13.5px;color:#57534e;padding:8px 12px;border-top:1px solid #d6d3d1;background:#fafaf9}
 @media(prefers-color-scheme:dark){
  body{color:#e7e5e4;background:#1c1917}
  h2{border-color:#44403c} code{background:#292524} th{background:#292524}
  th,td{border-color:#44403c} .lede,.meta{color:#a8a29e} td.m{background:#2a2011;color:#fbbf24}
  .key{background:#14261a} .warn{background:#2a2011} .open{background:#2a1414}
  .tag{background:#292524;color:#a8a29e}
  figure{border-color:#44403c}
  figcaption{background:#292524;border-color:#44403c;color:#a8a29e}
 }
"""

M = '<td class="m">to measure</td>'


def report(record, source, strip):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The audio board's panel interface, tested on a GMA 245R</title>
<style>{CSS}</style></head><body>
<!-- aerosense-report-status: needs-revalidation -->
<div style="border:2px solid #b45309;background:#fffbeb;color:#1c1917;padding:12px 16px;margin:0 0 24px;font:14px/1.5 system-ui,sans-serif;border-radius:6px">
  <strong style="font-size:15px">STATUS: NEEDS-REVALIDATION</strong><br>
  Reviewed 2026-11-16 by LIMA · verified against record <code>{record}</code><br>
  Source: <code>lima@{source}</code> · Supersedes: —<br>
  <strong>What changed:</strong> the demo codec is the ADAU1860 eval board, not the ADAU1372 the board was first wired for; the hookup below is the ADAU1860 one.<br>
  <strong>Next:</strong> build the stripboard and run the measurements in section 5; with the numbers in, this goes to CURRENT and onto the shelf.
</div>
<div class="warn"><p><strong>Draft, lane copy only.</strong> Peter, 2026-11-16: hold the shelf until the board is built and tested.
Every measurement cell below is empty on purpose. The expected values beside them are derived or borrowed from other panels, and say so.</p></div>

<h1>The audio board's panel interface, tested on a GMA 245R</h1>
<p class="meta">LIMA (Peter Bruce's lane) · drafted 2026-11-16 · bench rig, stripboard · not reviewed</p>
<p class="lede">The AeroNode audio board meets the aircraft through two small transformer networks: one carries the pilot's
processed voice into the audio panel's mic input, the other taps the panel's earphone audio for recording. Both were
sized from datasheets and a spec sheet for a different panel. This bench board pulls those two networks out on their own,
same parts and values, so they can be measured against a real Garmin GMA 245R before the audio board is built.</p>

<h2>1 · The question it answers</h2>
<p>Three numbers decide whether the audio board's panel interface works, and none of them has been measured on a GMA 245R:</p>
<ul>
<li><strong>The panel's earphone output:</strong> how many volts it delivers into the headset load, and from what source impedance.
The only figure on file is the GMA 340 spec sheet's 100 mW into 150 Ω, about 3.87 V rms <span class="tag">fetched, different panel</span>.</li>
<li><strong>The panel's mic input:</strong> its DC bias voltage and its input impedance. The design assumed a bias of 8–16 V and
a mic node of about 470 Ω <span class="tag">assumed</span>; the interface spec leaves this open (§9).</li>
<li><strong>What our transmit path actually delivers</strong> into that input, and whether it sounds right on the intercom.</li>
</ul>

<h2>2 · The circuit</h2>
<figure><div class="sheet">{schematic_svg()}</div>
<figcaption>The board's schematic (KiCad, <code>kicad/gma-match-board</code>). Nets are joined by name labels. Reference designators
and values match the audio board, so a value changed here maps straight back to it.</figcaption></figure>
<p><strong>Transmit.</strong> The codec's differential headphone output drives T4, a Bourns SM-LP-5001 600:600 transformer, directly.
Its secondary feeds R10 (10 kΩ), which sets the level, and C37 (220 nF film, 63 V or more), which keeps the panel's mic bias off the
winding. The output goes to the panel's MIC_HI and returns on MIC_LO. Nothing on the aircraft side touches our ground.</p>
<p><strong>Receive.</strong> The panel's earphone line drives the primaries of T2 and T3, Triad SP-74s, as it will on the audio
board, so the panel sees the same load of about 158 Ω. T2's secondary feeds the cup L driver; R7 and R8 tap it at half amplitude
for the codec's ADC.</p>
<p><strong>Left out on purpose:</strong> the audio board's K1 bypass relays and the failsafe electret. This board is always in
normal mode.</p>

<h2>3 · How it connects</h2>
<table>
<tr><th>Board</th><th>Net</th><th>Goes to</th><th>Note</th></tr>
<tr><td><code>J1.1</code> / <code>J1.2</code></td><td>DAC_P / DAC_N</td><td>ADAU1860 eval board HPOUTP / HPOUTN</td><td>Remove the eval board's default 32 Ω load on the P30 headphone output first. P16 is the external-load header; check its pin order in UG-2017.</td></tr>
<tr><td><code>J1.8</code></td><td>COMMS_TAP</td><td>Eval board P11 tip (ADC2)</td><td>ADC2 jumpered single-ended (P13/P15 pins 2–3). The eval board's 22 µF series cap does the coupling.</td></tr>
<tr><td><code>J1.3</code></td><td>GND</td><td>Eval board P11 sleeve (ground)</td><td></td></tr>
<tr><td><code>J1.4</code>, <code>J1.5</code>, <code>J1.6</code></td><td>AIN1, AIN1REF, clamp rail</td><td>Not connected</td><td>The ADAU1860 has no AINxREF pin. <strong>Never put 3.3 V on J1.6</strong>: the ADAU1860's signal pins are limited to 2.1 V.</td></tr>
<tr><td><code>J2.1</code> / <code>J2.2</code></td><td>EAR_HI / EAR_RTN</td><td>GMA 245R J2402-16 (LEFT, headphone tip) / J2402-1 (LO, sleeve)</td><td>Or the panel harness on J5</td></tr>
<tr><td><code>J2.3</code> / <code>J2.4</code></td><td>MIC_HI / MIC_LO</td><td>GMA 245R J2401-33 (mic ring) / J2401-35 (mic sleeve)</td><td></td></tr>
<tr><td><code>J3</code>, <code>J4</code></td><td>SPK_L, SPK_R</td><td>Cup L and cup R earphone drivers</td><td>Secondaries in parallel, which suits 32 Ω drivers; see section 7</td></tr>
</table>
<p class="meta">GMA 245R contacts from Garmin installation manual 190-01879-11 Rev 14 <span class="tag">fetched</span>. ADAU1860 levels from its datasheet; eval-board jacks and jumpers from UG-2017 <span class="tag">repo</span>.</p>

<h2>4 · The build</h2>
<figure><div class="sheet">{strip}</div>
<figcaption>Component side of the 0.1-inch stripboard, 38 holes × 24 strips, with the copper strips shown through the board.
Red ✕ = track cut (28, made from the copper side). Thick coloured lines = insulated links; grey = bare tinned links (15 in all).
Blue discs = upright resistors, orange = upright Schottky diodes (band up), red dot = transformer pin 1.
Header labels give pin and net. Drawn from the same layout file the connectivity check reads.</figcaption></figure>
<p>Most of the PCB's parts are surface-mount, so the stripboard uses through-hole stand-ins at the same values: upright ¼ W
resistors, radial ceramic capacitors, a radial film C37, and two discrete Schottky diodes in place of the BAT54S. T4 has no
through-hole version, so it sits on four short wire legs. Its feet are 12.0 mm apart and the holes 12.7 mm.</p>
<div class="key"><p><strong>Checked before building.</strong> A script rebuilds every net from the strips, cuts, links and part
legs and compares it with the schematic's netlist: they match exactly. Removing one link (N28–O28) splits a net, and removing one
cut (N24) shorts two nets; both make the check fail, as they should.</p></div>

<h2>5 · Measurements</h2>
<p>All at 1 kHz unless stated. Fill in the measured column; the expected column is what the design assumed, so a large
difference is the finding.</p>
<h3>The panel</h3>
<table>
<tr><th>Quantity</th><th>How</th><th>Expected</th><th>Measured</th></tr>
<tr><td>Earphone output, open circuit, full volume</td><td>Scope or true-RMS meter on the panel's headphone contacts, board unplugged</td><td>3.87 V rms <span class="tag">GMA 340 sheet</span></td>{M}</tr>
<tr><td>Earphone output, into the board (~158 Ω)</td><td>Same, board plugged in, across J2.1–J2.2</td><td>—</td>{M}</tr>
<tr><td>Earphone source impedance</td><td>From the two readings above</td><td>unknown</td>{M}</tr>
<tr><td>Mic input DC bias</td><td>DC volts, J2.3 to J2.4 (C37 blocks it from the board)</td><td>8–16 V <span class="tag">assumed</span></td>{M}</tr>
<tr><td>Mic input impedance</td><td>Known tone through R10, ratio of levels either side of it</td><td>~470 Ω <span class="tag">assumed</span></td>{M}</tr>
</table>
<h3>Transmit: codec to panel mic</h3>
<table>
<tr><th>Quantity</th><th>How</th><th>Expected</th><th>Measured</th></tr>
<tr><td>Level at the mic input, 0 dBFS</td><td>Tone from the codec; AC volts across J2.3–J2.4</td><td>~35 mV rms <span class="tag">derived</span></td>{M}</tr>
<tr><td>Low-frequency corner</td><td>Sweep 50 Hz – 1 kHz</td><td>~69 Hz (C37 with 10.47 kΩ) <span class="tag">derived</span></td>{M}</tr>
<tr><td>Heard on the intercom</td><td>Speech through the panel, by ear</td><td>clear, no hum</td>{M}</tr>
</table>
<h3>Receive: panel earphone to codec</h3>
<table>
<tr><th>Quantity</th><th>How</th><th>Expected</th><th>Measured</th></tr>
<tr><td>Tap level at full volume</td><td>AC volts at J1.8 to J1.3</td><td>≤ 0.62 V rms open circuit <span class="tag">derived</span></td>{M}</tr>
<tr><td>ADC level at full volume</td><td>Codec meter, PGA 0 dB</td><td>about −1.5 dBFS <span class="tag">derived, assumes ~10 kΩ input</span></td>{M}</tr>
<tr><td>Cup drivers</td><td>Headset on J3/J4, by ear and level</td><td>loud enough, undistorted</td>{M}</tr>
</table>

<h2>6 · What changes on the audio board</h2>
<p><em>To be written from section 5.</em> The values this test can move: R10 (transmit level), the R7/R8 ratio (tap level against
the ADC's full scale), and whether the SP-74 secondaries should be wired in series for 150 Ω drivers.</p>

<h2>7 · Open items</h2>
<div class="open">
<p><strong>SP-74 secondary polarity</strong> is unverified, carried from the audio board. Wired wrongly, the paralleled windings
short each other: check before full volume.</p>
<p><strong>Parallel or series secondaries.</strong> Parallel suits 32 Ω drivers; for 150 Ω drivers our own power budget recommends
series. Settle which drivers the demo uses.</p>
<p><strong>Mono headphone plug.</strong> The GMA's failsafe check expects the headphone plug's ring shorted to its sleeve; the
harness should use a 2-circuit plug.</p>
<p><strong>P16 pin order</strong> on the ADAU1860 eval board is not in our notes.</p>
<p><strong>Strip spacing.</strong> On strip F a single cut at F13 is all that separates our ground from EAR_HI. Meter it.</p>
</div>

<h2>8 · How it was checked</h2>
<ul>
<li>Schematic netlist (exported by KiCad) compared pin for pin with the intended connectivity: match. A deliberately moved pin fails the check.</li>
<li>Electrical rules check: 0 errors, 0 warnings.</li>
<li>Stripboard connectivity compared with the same intended connectivity: match, with two negative controls (section 4).</li>
<li>The measurements in section 5: <em>not yet run</em>.</li>
</ul>

<h2>9 · What went wrong on the way</h2>
<ul>
<li><strong>The codec changed under the design.</strong> The board's codec header and its notes were written for the ADAU1372,
the audio board's codec. The demo uses the ADAU1860 eval board, which has no input reference pin, runs its analog side at 1.8 V
and has half the DAC output. The board needs no change, but its codec-side wiring does, and a 3.3 V clamp rail would now
over-drive the codec's inputs. Caught before anything was built.</li>
<li><strong>T4 is not a stripboard part.</strong> The SM-LP-5001 is surface-mount with feet off the 0.1-inch grid, so the
stripboard carries it on wire legs. A through-hole equivalent was not looked for.</li>
</ul>
<p class="meta">Interactive 3D views of the board and the stripboard build are kept in the lima repo
(<code>docs/gma-match-board-3d.html</code>, <code>docs/gma-match-veroboard.html</code>), not on the shelf.</p>
</body></html>
"""


if __name__ == "__main__":
    record, source = sys.argv[1], sys.argv[2]
    strip = stripboard_svg()
    open(os.path.join(HERE, "stripboard-layout.svg"), "w", encoding="utf-8").write(strip)
    root = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
    out = os.path.join(root, "docs", "LIMA_gma_match_board.html")
    open(out, "w", encoding="utf-8").write(report(record, source, strip))
    print("wrote", out)
