"""Scratch-DSN edits for Freerouting (never touches the board): margins, power class split."""
import sys, re
t = open(sys.argv[1]).read()
t = t.replace("170000 -130000  100000 -130000  100000 -80000  170000 -80000\n            170000 -130000",
              "169900 -129900  100100 -129900  100100 -80100  169900 -80100\n            169900 -129900")
t = t.replace("(clearance 127)", "(clearance 150)").replace("(clearance 500)", "(clearance 550)")
m = re.search(r"\(class Power,Default[^(]*", t)
t = t[:m.start()] + m.group(0).replace(" /VBAT", "").replace(" /+3V3A", "") + t[m.end():]
p = t.index("(class Power,Default"); q = t.index("(width 500)", p); t = t[:q] + "(width 300)" + t[q+11:]
q = t.index("800:400", p); t = t[:q] + "600:300" + t[q+7:]
cls = '    (class PowerFine /VBAT /+3V3A\n      (circuit\n        (use_via "Via[0-3]_600:300_um")\n      )\n      (rule\n        (width 200)\n        (clearance 150)\n      )\n    )\n'
i = t.index("  (wiring"); j = t.rindex("  )\n", 0, i); t = t[:j] + cls + t[j:]
open(sys.argv[2], "w").write(t)
