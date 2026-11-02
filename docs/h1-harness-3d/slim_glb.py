"""Slim a KiCad-exported GLB for the web page: bake node transforms, merge primitives by material, drop normals
(the page recomputes them), quantise positions to uint16 (KHR_mesh_quantization) and write uint16 index chunks.
Output is in millimetres, frame unchanged (x right, y up, z = KiCad y-down). Standard library only.
Usage: slim_glb.py <in.glb> <out.glb>"""
import sys, struct, json, math
from array import array

src, dst = sys.argv[1], sys.argv[2]
b = open(src, "rb").read()
jlen = struct.unpack("<I", b[12:16])[0]
j = json.loads(b[20:20 + jlen])
binoff = 20 + jlen + 8
BIN = memoryview(b)[binoff:]

def mat_mul(a, c):
    return [sum(a[r * 4 + k] * c[k * 4 + col] for k in range(4)) for r in range(4) for col in range(4)]

def node_matrix(n):
    if "matrix" in n:                       # glTF is column-major
        m = n["matrix"]; return [m[col * 4 + r] for r in range(4) for col in range(4)]
    tx, ty, tz = n.get("translation", [0, 0, 0]); qx, qy, qz, qw = n.get("rotation", [0, 0, 0, 1]); sx, sy, sz = n.get("scale", [1, 1, 1])
    r = [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw),
         2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw),
         2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)]
    return [r[0] * sx, r[1] * sy, r[2] * sz, tx, r[3] * sx, r[4] * sy, r[5] * sz, ty, r[6] * sx, r[7] * sy, r[8] * sz, tz, 0, 0, 0, 1]

def read(acc_i):
    a = j["accessors"][acc_i]; bv = j["bufferViews"][a["bufferView"]]
    fmt = {5126: "f", 5125: "I", 5123: "H", 5121: "B"}[a["componentType"]]; w = {"SCALAR": 1, "VEC3": 3}[a["type"]]
    size = struct.calcsize(fmt); stride = bv.get("byteStride", size * w); start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    if stride == size * w:
        out = array(fmt); out.frombytes(bytes(BIN[start:start + a["count"] * stride])); return out
    out = array(fmt)
    for i in range(a["count"]): out.frombytes(bytes(BIN[start + i * stride:start + i * stride + size * w]))
    return out

buckets = {}                                  # material -> (positions float list, indices list)
def walk(i, m):
    n = j["nodes"][i]; m = mat_mul(m, node_matrix(n))
    if "mesh" in n:
        for p in j["meshes"][n["mesh"]]["primitives"]:
            if p.get("mode", 4) != 4: continue
            pos = read(p["attributes"]["POSITION"]); idx = read(p["indices"]) if "indices" in p else array("I", range(len(pos) // 3))
            P, I = buckets.setdefault(p.get("material", -1), (array("f"), array("I")))
            base = len(P) // 3
            for k in range(0, len(pos), 3):
                x, y, z = pos[k], pos[k + 1], pos[k + 2]
                P.append((m[0] * x + m[1] * y + m[2] * z + m[3]) * 1000); P.append((m[4] * x + m[5] * y + m[6] * z + m[7]) * 1000); P.append((m[8] * x + m[9] * y + m[10] * z + m[11]) * 1000)
            I.extend(v + base for v in idx)
    for c in n.get("children", []): walk(c, m)
I4 = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
for r in j["scenes"][j.get("scene", 0)]["nodes"]: walk(r, I4)

allP = [P for P, _ in buckets.values()]
lo = [min(min(P[k::3]) for P in allP if len(P)) for k in range(3)]; hi = [max(max(P[k::3]) for P in allP if len(P)) for k in range(3)]
ext = [max(hi[k] - lo[k], 1e-6) for k in range(3)]
print("bbox mm", [round(v, 2) for v in lo], [round(v, 2) for v in hi])

out_bin = bytearray(); views, accs, prims, mats = [], [], [], []
def add_view(data, target):
    while len(out_bin) % 4: out_bin.append(0)
    views.append({"buffer": 0, "byteOffset": len(out_bin), "byteLength": len(data), "target": target}); out_bin.extend(data); return len(views) - 1
for mat, (P, I) in buckets.items():
    if mat >= 0:
        src_m = j["materials"][mat]; pbr = src_m.get("pbrMetallicRoughness", {})
        mats.append({"pbrMetallicRoughness": {"baseColorFactor": pbr.get("baseColorFactor", [0.7, 0.7, 0.7, 1]), "metallicFactor": pbr.get("metallicFactor", 0), "roughnessFactor": pbr.get("roughnessFactor", 0.6)}, "doubleSided": True})
    else:
        mats.append({"pbrMetallicRoughness": {"baseColorFactor": [0.7, 0.7, 0.7, 1], "metallicFactor": 0, "roughnessFactor": 0.6}, "doubleSided": True})
    mi = len(mats) - 1; t = 0
    while t < len(I):                          # chunk to <= 65535 vertices so indices fit uint16
        remap, qpos, qidx = {}, array("H"), array("H")
        while t < len(I) and len(remap) <= 65532:
            for v in I[t:t + 3]:
                k = remap.get(v)
                if k is None:
                    k = remap[v] = len(remap)
                    for c in range(3): qpos.append(int(round((P[v * 3 + c] - lo[c]) / ext[c] * 65535)))
                    qpos.append(0)               # pad to an 8-byte stride (4-byte alignment)
                qidx.append(k)
            t += 3
        pv = add_view(qpos.tobytes(), 34962); views[pv]["byteStride"] = 8
        accs.append({"bufferView": pv, "componentType": 5123, "count": len(remap), "type": "VEC3", "min": [0, 0, 0], "max": [65535, 65535, 65535]})
        iv = add_view(qidx.tobytes(), 34963)
        accs.append({"bufferView": iv, "componentType": 5123, "count": len(qidx), "type": "SCALAR"})
        prims.append({"attributes": {"POSITION": len(accs) - 2}, "indices": len(accs) - 1, "material": mi})
while len(out_bin) % 4: out_bin.append(0)
g = {"asset": {"version": "2.0", "generator": "slim_glb.py (from KiCad GLB)"}, "extensionsUsed": ["KHR_mesh_quantization"], "extensionsRequired": ["KHR_mesh_quantization"],
     "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "translation": lo, "scale": [ext[k] / 65535 for k in range(3)], "name": "model"}],
     "meshes": [{"primitives": prims}], "materials": mats, "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(out_bin)}]}
js = json.dumps(g, separators=(",", ":")).encode()
while len(js) % 4: js += b" "
with open(dst, "wb") as f:
    f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(out_bin)))
    f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
    f.write(struct.pack("<II", len(out_bin), 0x004E4942)); f.write(out_bin)
print("wrote", dst, round((28 + len(js) + len(out_bin)) / 1e6, 2), "MB,", len(prims), "primitives,", len(mats), "materials")
