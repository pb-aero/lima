"""Generate ADAU1467 and IM68A130A symbols in the house style of kicad/lib/*.kicad_sym.

Pin tables transcribed from:
  ADAU1463/ADAU1467 Rev. A, Table 18 (88-lead LFCSP CP-88-10; EP numbered 89 here)
  IM68A130A datasheet Rev 1.10, Table 3 (PG-TLGA-4-2)
Usage: python3 gen_syms.py <lib_dir>   (appends; refuses if the symbol already exists)
"""
import re
import sys

P = 2.54


def prop(name, val, y, hide=False):
    h = " (hide yes)" if hide else ""
    return (f'    (property "{name}" "{val}" (at 0 {y:.4f} 0) (show_name no) (do_not_autoplace no){h} '
            f'(effects (font (size 1.27 1.27))))\n')


def pin(kind, x, y, rot, name, num):
    return (f'    (pin {kind} line (at {x:g} {y:g} {rot})\n'
            f'      (length 2.54)\n'
            f'      (name "{name}" (effects (font (size 1.27 1.27))))\n'
            f'      (number "{num}" (effects (font (size 1.27 1.27))))\n'
            f'    )\n')


def symbol(name, value, w2, h2, pins, fp, ds, desc, ref_off=2.54):
    s = (f'  (symbol "{name}"\n    (pin_names\n      (offset 1.016))\n    (exclude_from_sim no)\n'
         f'    (in_bom yes)\n    (on_board yes)\n    (in_pos_files yes)\n'
         f'    (duplicate_pin_numbers_are_jumpers no)\n')
    s += prop("Reference", "U", h2 + ref_off)
    s += prop("Value", value, -(h2 + ref_off))
    s += prop("Footprint", fp, 0, True)
    s += prop("Datasheet", ds, 0, True)
    s += prop("Description", desc, 0, True)
    s += (f'    (symbol "{name}_0_1"\n      (rectangle (start {-w2:.4f} {-h2:.4f}) (end {w2:.4f} {h2:.4f})\n'
          f'        (stroke (width 0.254) (type default))\n        (fill (type background))\n      )\n')
    s += "".join(pins)
    s += '    )\n    (embedded_fonts no)\n  )\n'
    return s


def column(entries, x, top, rot):
    """entries: list of (kind, name, num) or None for a gap; laid top-down from y=top."""
    out, y = [], top
    for e in entries:
        if e is not None:
            out.append(pin(e[0], x, round(y, 2), rot, e[1], e[2]))
        y -= P
    return out


def row(entries, y, rot, w2):
    n = len(entries)
    x0 = -((n - 1) * P) / 2
    return [pin(k, round(x0 + i * P, 2), y, rot, nm, num) for i, (k, nm, num) in enumerate(entries)]


def adau1467():
    B, I, O, PI, PS = "bidirectional", "input", "output", "power_in", "passive"
    left = [(I, "~{RESET}", 28), (I, "SELFBOOT", 42), None,
            (I, "~{SS}/ADDR0", 41), (I, "MOSI/ADDR1", 40), (I, "SCLK/SCL", 39), (B, "MISO/SDA", 38), None,
            (I, "XTALIN/MCLK", 25), (O, "XTALOUT", 26), (O, "CLKOUT", 27), (PS, "PLLFILT", 20),
            (O, "VDRIVE", 3), None]
    for p in range(4):
        left += [(B, f"BCLK_IN{p}", (73, 76, 81, 84)[p]), (B, f"LRCLK_IN{p}/MP{10 + p}", (74, 77, 82, 85)[p]),
                 (I, f"SDATA_IN{p}", (75, 78, 83, 86)[p])]
    left += [None] + [(I, f"AUXADC{i}", 10 + i) for i in range(8)] + [None, (PS, "THD_P", 80), (PS, "THD_M", 79)]

    right = []
    for p in range(4):
        right += [(B, f"BCLK_OUT{p}", (48, 51, 56, 59)[p]), (B, f"LRCLK_OUT{p}/MP{(4, 5, 8, 9)[p]}", (47, 50, 55, 58)[p]),
                  (O, f"SDATA_OUT{p}", (49, 52, 57, 60)[p])]
    right += [None] + [(B, f"SDATAIO{i}/MP{16 + i}", (72, 71, 70, 69, 64, 63, 62, 61)[i]) for i in range(8)]
    right += [None, (B, "~{SS_M}/MP0", 32), (B, "MOSI_M/MP1", 33), (B, "SCL_M/SCLK_M/MP2", 34),
              (B, "SDA_M/MISO_M/MP3", 35), (B, "SCL2_M/MP24", 30), (B, "SDA2_M/MP25", 31), None,
              (B, "MP6", 53), (B, "MP7", 54), (B, "MP14", 6), (B, "MP15", 7), None,
              (I, "SPDIFIN", 4), (O, "SPDIFOUT", 5)]
    top = [(PI, "IOVDD", n) for n in (2, 22, 37, 46, 68)] + [(PI, "AVDD", 9), (PI, "PVDD", 19)] + \
          [(PI, "DVDD", n) for n in (24, 43, 65, 87)]
    bot = [(PI, "DGND", n) for n in (1, 21, 23, 29, 36, 44, 45, 66, 67, 88)] + \
          [(PI, "AGND", 8), (PI, "PGND", 18), (PI, "EP", 89)]
    rows = max(len(left), len(right))
    h2 = (rows + 1 + 8) * P / 2  # 4 pitches clear of the vertical top/bottom pin names
    h2 = round(h2 / P + 0.5) * P
    w2 = 22.86
    ytop = round(((rows - 1) * P) / 2 / P) * P
    pins = column(left, -(w2 + P), ytop, 0) + column(right, w2 + P, ytop, 180)
    pins += row(top, h2 + P, 270, w2) + row(bot, -(h2 + P), 90, w2)
    nums = [e[2] for e in left + right + top + bot if e]
    return symbol("ADAU1467", "ADAU1467", w2, h2, pins, "",
                  "https://www.analog.com/media/en/technical-documentation/data-sheets/adau1463-1467.pdf",
                  "SigmaDSP audio processor, 294.912 MHz, 24 kWord program, 88-lead LFCSP 12x12 (EP = pin 89)", 7.62), nums


def im68a130a():
    pins = [pin("output", 10.16, 0, 180, "OUT", 1), pin("power_in", 0, 10.16, 270, "VDD", 3),
            pin("power_in", -2.54, -10.16, 90, "GND", 2), pin("power_in", 2.54, -10.16, 90, "GND", 4)]
    return symbol("IM68A130A", "IM68A130A", 7.62, 7.62, pins, "",
                  "https://www.infineon.com/dgdl/Infineon-IM68A130A-DataSheet-v01_00-EN.pdf",
                  "XENSIV analog MEMS microphone, single-ended, 2.4-3.3 V, PG-TLGA-4-2", 7.62), [1, 2, 3, 4]


def paren_balanced(t):
    t = re.sub(r'"(?:[^"\\]|\\.)*"', '""', t)
    return t.count("(") == t.count(")")


def append(path, name, text):
    src = open(path).read()
    if f'(symbol "{name}"' in src:
        sys.exit(f"{name} already in {path}")
    assert src.rstrip().endswith(")")
    out = src.rstrip()[:-1] + text + ")\n"
    assert paren_balanced(text) and paren_balanced(out), "paren imbalance"
    open(path, "w").write(out)


if __name__ == "__main__":
    lib = sys.argv[1]
    t, nums = adau1467()
    assert sorted(nums) == list(range(1, 90)), sorted(set(range(1, 90)) ^ set(nums))
    append(f"{lib}/AnalogDevices.kicad_sym", "ADAU1467", t)
    t, nums = im68a130a()
    assert sorted(nums) == [1, 2, 3, 4]
    append(f"{lib}/Infineon.kicad_sym", "IM68A130A", t)
    print("ok")
