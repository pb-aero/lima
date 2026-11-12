"""Build the self-contained shelf copy of a 3D harness page (company repo reports/ rules: one file, no CDN, no
external links, status banner after <body>). Inlines three.js r128 + GLTFLoader + OrbitControls from a local folder,
embeds each board model as gzip+base64 (the page decodes it with the browser's DecompressionStream), drops the web
font link, and adds the banner. Every text substitution must hit exactly once or the build stops.
Standard library only. Run from the repo root:
  python3 -I docs/h1-harness-3d/make_report.py <page.html> <three-dir> <banner.html> <out.html>
<three-dir> holds three.min.js, GLTFLoader.js, OrbitControls.js from cdn.jsdelivr.net/npm/three@0.128.0
(sha256 9274bbce…, 5c15967b…, 02bb4ade… as fetched 2026-11-12)."""
import sys, os, re, gzip, base64, hashlib

page, three_dir, banner_path, out = sys.argv[1:5]
here = os.path.dirname(os.path.abspath(page))
html = open(page, encoding="utf-8").read()
banner = open(banner_path, encoding="utf-8").read().strip()

def once(old, new):
    global html
    n = html.count(old)
    if n != 1: sys.exit(f"expected exactly one match, found {n}: {old[:70]!r}")
    html = html.replace(old, new)

SHA = {"three.min.js": "9274bbcec8d96168626c732b5d31c775aa8cfb7eaa0599bec0c175908a2c1ce2",
       "GLTFLoader.js": "5c15967ba830918a9caea6338712c994c354bccd4edc4569bde411c3ec06a3e6",
       "OrbitControls.js": "02bb4ade710f3e607329e37a21f098bc3ac70eb6e33daf8a65e79f4db785e7b2"}
lib = {}
for name, want in SHA.items():
    data = open(os.path.join(three_dir, name), "rb").read()
    if hashlib.sha256(data).hexdigest() != want: sys.exit(f"{name}: sha256 mismatch, not the vetted r128 file")
    text = data.decode("utf-8")
    if "</script" in text.lower(): sys.exit(f"{name} contains </script and cannot be inlined")
    lib[name] = text

# models the page loads, embedded gzip+base64 under id glb-<name>
models = re.findall(r"loadBoard\('([a-z0-9]+)\.glb\.txt'", html)
if not models: sys.exit("no loadBoard() calls found")
blocks = []
for m in models:
    raw = open(os.path.join(here, m + ".glb"), "rb").read()
    b64 = base64.b64encode(gzip.compress(raw, 9, mtime=0)).decode("ascii")
    blocks.append(f'<script type="application/octet-stream" id="glb-{m}">{b64}</script>')

once('<meta name="claude:viewport-fit-sides" content="cover">\n', '<meta name="viewport" content="width=device-width,initial-scale=1">\n')
once('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap">\n', '')
once('\n<header>', '\n</head>\n<body>\n' + banner + '\n<header>')
for name, path in [("three.min.js", "build/three.min.js"), ("GLTFLoader.js", "examples/js/loaders/GLTFLoader.js"),
                   ("OrbitControls.js", "examples/js/controls/OrbitControls.js")]:
    once(f'<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/{path}"></script>',
         ('\n'.join(blocks) + '\n' if name == "three.min.js" else '') + f'<script>/* three@0.128.0 {path}, MIT */\n{lib[name]}\n</script>')
once("""function fetchGLB(url){
  return glbCache[url] = glbCache[url] || fetch(url).then(r => { if (!r.ok) throw new Error(url + ' ' + r.status); return r.text(); })
    .then(t => { const s = atob(t.replace(/\\s+/g,'')), b = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) b[i] = s.charCodeAt(i); return b.buffer; });
}""", """function fetchGLB(url){   // shelf copy: models are embedded gzip+base64, not fetched
  return glbCache[url] = glbCache[url] || Promise.resolve().then(() => {
    const el = document.getElementById('glb-' + url.replace('.glb.txt', ''));
    if (!el) throw new Error(url + ' is not embedded');
    if (typeof DecompressionStream === 'undefined') throw new Error('this browser cannot unzip the embedded models; use a current Chrome, Edge, Safari or Firefox');
    const s = atob(el.textContent), b = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) b[i] = s.charCodeAt(i);
    return new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
  });
}""")
html = '<!doctype html>\n<html lang="en">\n<head>\n' + html.rstrip() + '\n</body>\n</html>\n'

bad = re.findall(r'(?:src|href)="(?:https?:|file:|/)[^"]*"', html)
if bad: sys.exit(f"not self-contained: {bad[:5]}")
if html.count("aerosense-report-status:") != 1: sys.exit("banner marker missing or duplicated")
open(out, "w", encoding="utf-8").write(html)
print(f"wrote {out} {len(html.encode())/1e6:.2f} MB, models {models}")
