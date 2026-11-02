"""Find where named parts sit in a STEP assembly (AP214, as KiCad/OpenCASCADE write it): follows
NEXT_ASSEMBLY_USAGE_OCCURRENCE -> CONTEXT_DEPENDENT_SHAPE_REPRESENTATION -> ITEM_DEFINED_TRANSFORMATION up to the root
and prints each part's placement origin in the root frame (mm). Usage: step_find.py <file.step> NAME ..."""
import sys, re, math
txt = open(sys.argv[1], "r", errors="replace").read()
ents = {}
for m in re.finditer(r"#(\d+)\s*=\s*(.*?);\s*(?=#\d+\s*=|ENDSEC)", txt, re.S):
    ents[int(m.group(1))] = " ".join(m.group(2).split())
refs = lambda s: [int(x) for x in re.findall(r"#(\d+)", s)]
def nums(s): return [float(x) for x in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)]
by_kind = {}
for i, s in ents.items(): by_kind.setdefault(s.split("(", 1)[0].strip(), []).append(i)
pdf_of_product = {refs(ents[i])[-1]: i for i in by_kind.get("PRODUCT_DEFINITION_FORMATION", [])}
pd_of_pdf = {refs(ents[i])[0]: i for i in by_kind.get("PRODUCT_DEFINITION", [])}
nauo = {}                                       # child pd -> (nauo id, parent pd)
for i in by_kind.get("NEXT_ASSEMBLY_USAGE_OCCURRENCE", []):
    r = refs(ents[i]); nauo.setdefault(r[1], []).append((i, r[0]))
pds_of = {refs(ents[i])[0]: i for i in by_kind.get("PRODUCT_DEFINITION_SHAPE", []) if refs(ents[i])}
cdsr = {refs(ents[i])[1]: refs(ents[i])[0] for i in by_kind.get("CONTEXT_DEPENDENT_SHAPE_REPRESENTATION", [])}
def axis(i):                                     # AXIS2_PLACEMENT_3D -> 4x4
    r = refs(ents[i]); o = nums(ents[r[0]].split("(", 2)[2]); z = nums(ents[r[1]].split("(", 2)[2]) if len(r) > 1 else [0, 0, 1]
    x = nums(ents[r[2]].split("(", 2)[2]) if len(r) > 2 else [1, 0, 0]
    y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
    return [[x[0], y[0], z[0], o[0]], [x[1], y[1], z[1], o[1]], [x[2], y[2], z[2], o[2]], [0, 0, 0, 1]]
def inv(m):
    R = [[m[c][r] for c in range(3)] for r in range(3)]; t = [m[k][3] for k in range(3)]
    ti = [-sum(R[r][k] * t[k] for k in range(3)) for r in range(3)]
    return [R[0] + [ti[0]], R[1] + [ti[1]], R[2] + [ti[2]], [0, 0, 0, 1]]
mm = lambda a, b: [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]
def occ_transform(nauo_id):
    rr = cdsr.get(pds_of.get(nauo_id))
    if rr is None: return None
    idt = [x for x in refs(ents[rr]) if ents[x].startswith("ITEM_DEFINED_TRANSFORMATION")][0]
    a1, a2 = refs(ents[idt])
    return mm(axis(a2), inv(axis(a1)))
def placements(pd):
    if pd not in nauo: return [[[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]]
    out = []
    for nid, parent in nauo[pd]:
        t = occ_transform(nid)
        if t is None: continue
        for up in placements(parent): out.append(mm(up, t))
    return out
for name in sys.argv[2:]:
    for i in by_kind.get("PRODUCT", []):
        if re.match(r"PRODUCT\('%s'" % re.escape(name), ents[i]):
            pd = pd_of_pdf.get(pdf_of_product.get(i))
            for m in placements(pd):
                ang = math.degrees(math.atan2(m[1][0], m[0][0]))
                print(name, "origin mm", [round(m[k][3], 3) for k in range(3)], "x-axis angle %.1f deg" % ang)
