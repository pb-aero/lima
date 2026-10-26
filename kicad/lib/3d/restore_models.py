"""Copy each board footprint's 3D model list from its library footprint (what 'Update Footprints from Library'
does for models). Pads, nets, position and orientation are not touched."""
import sys, os, re, pcbnew
board = sys.argv[1]; proj = os.path.dirname(os.path.abspath(board))
KS = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'
libs = {}
for blk in re.findall(r'\(lib\s(.*?)\)\s*\n', open(os.path.join(proj, 'fp-lib-table')).read()):
    n = re.search(r'\(name "?([^")]+)"?\)', blk); u = re.search(r'\(uri "?([^")]+)"?\)', blk)
    if n and u: libs[n.group(1)] = u.group(1).replace('${KIPRJMOD}', proj)
print("project libs:", sorted(libs))
b = pcbnew.LoadBoard(board); done = 0; skipped = {}
cache = {}
for f in b.GetFootprints():
    fid = f.GetFPID(); nick, name = str(fid.GetLibNickname()), str(fid.GetLibItemName())
    path = libs.get(nick) or os.path.join(KS, nick + '.pretty')
    key = (path, name)
    if key not in cache:
        cache[key] = pcbnew.FootprintLoad(path, name) if os.path.exists(os.path.join(path, name + '.kicad_mod')) else None
    lf = cache[key]
    if lf is None or len(lf.Models()) == 0:
        skipped[nick + ':' + name] = skipped.get(nick + ':' + name, 0) + 1; continue
    f.Models().clear()
    for m in lf.Models(): f.Models().push_back(m)
    done += 1
pcbnew.SaveBoard(board, b)
b2 = pcbnew.LoadBoard(board)
print("footprints:", len(b2.GetFootprints()), "| with model now:", sum(1 for f in b2.GetFootprints() if len(f.Models())), "| updated:", done)
print("no model in library:", skipped)
