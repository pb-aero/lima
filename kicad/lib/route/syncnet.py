"""Sync a board to a schematic netlist without the KiCad UI: add missing footprints (from the project's fp-lib-table
or KiCad's stock libraries, 3D models kept), remove footprints no longer in the netlist, and set every pad's net.
Usage: syncnet.py <board> <netlist.xml (kicad-cli sch export netlist --format kicadxml)> [--keep REF,...]
New footprints are parked at the board centre for the placer.  Run with KiCad closed."""
import sys, os, re, pcbnew
import xml.etree.ElementTree as ET
bpath, npath = sys.argv[1], sys.argv[2]
keep = set(sys.argv[sys.argv.index("--keep") + 1].split(",")) if "--keep" in sys.argv else set()
b = pcbnew.LoadBoard(bpath)
STOCK = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
libs = {}
tbl = os.path.join(os.path.dirname(os.path.abspath(bpath)), "fp-lib-table")
if os.path.exists(tbl):
    for m in re.finditer(r'\(lib\s+\(name\s+"?([^")\s]+)"?\).*?\(uri\s+"?([^")\s]+)"?\)', open(tbl).read(), re.S):
        libs[m.group(1)] = m.group(2).replace("${KIPRJMOD}", os.path.dirname(os.path.abspath(bpath)))
def libpath(lib): return libs.get(lib, os.path.join(STOCK, lib + ".pretty"))

root = ET.parse(npath).getroot()
comps = {c.get("ref"): (c.findtext("value"), c.findtext("footprint")) for c in root.iter("comp")}
fields = {c.get("ref"): {fl.get("name"): (fl.text or "") for fl in c.iter("field")} for c in root.iter("comp")}
pin2net = {}
for n in root.iter("net"):
    name = n.get("name")
    if name.startswith("Net-(") or name.startswith("unconnected-("): name = name[:5] + name[5:].replace("/", "{slash}")   # KiCad escapes '/' inside auto names
    elif not name.startswith("/"): name = "/" + name
    for nd in n.iter("node"): pin2net[(nd.get("ref"), nd.get("pin"))] = name

added, removed = [], []
on_board = {f.GetReference(): f for f in b.GetFootprints()}
for ref, f in on_board.items():
    if ref not in comps and ref not in keep and not ref.startswith("REF"): removed.append(ref)
for ref in removed: b.Remove(on_board[ref])
cx, cy = b.GetBoardEdgesBoundingBox().Centre().x, b.GetBoardEdgesBoundingBox().Centre().y
for ref, (val, fpid) in comps.items():
    if ref in on_board or not fpid or ref.startswith("#"): continue
    lib, name = fpid.split(":", 1)
    f = pcbnew.FootprintLoad(libpath(lib), name)
    if f is None: print("cannot load", fpid, "for", ref, flush=True); continue
    f.SetFPID(pcbnew.LIB_ID(lib, name))
    f.SetReference(ref); f.SetValue(val or ""); f.SetPosition(pcbnew.VECTOR2I(cx, cy))
    for k, v in fields.get(ref, {}).items():
        if k not in ("Footprint", "Datasheet", "Description"):
            try:
                f.SetField(k, v)
                fld = f.GetField(k) if f.HasField(k) else None
                if fld: fld.SetVisible(False)      # keep MPN/Note off the silkscreen
            except Exception as e: print("field", k, "not set:", e, flush=True)
    b.Add(f); added.append(ref)

nets = {}
def net(name):
    if name not in nets:
        ni = b.FindNet(name)
        if ni is None: ni = pcbnew.NETINFO_ITEM(b, name); b.Add(ni)
        nets[name] = ni
    return nets[name]
changed = 0
for f in b.GetFootprints():
    for p in f.Pads():
        want = pin2net.get((f.GetReference(), p.GetNumber()))
        if want is None:
            if p.GetNetCode() != 0 and p.GetNumber(): p.SetNetCode(0); changed += 1
            continue
        if p.GetNetname() != want: p.SetNet(net(want)); changed += 1
pcbnew.SaveBoard(bpath, b)
print("added", added, "removed", removed, "pad nets changed", changed, flush=True); os._exit(0)
