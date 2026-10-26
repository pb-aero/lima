"""Scratch-DSN edits for Freerouting (never touches the board): margins, power class split."""
import sys, re
t = open(sys.argv[1]).read()
t = t.replace("170000 -130000  100000 -130000  100000 -80000  170000 -80000\n            170000 -130000",
              "169900 -129900  100100 -129900  100100 -80100  169900 -80100\n            169900 -129900")
t = t.replace("(clearance 127)", "(clearance 130)").replace("(clearance 500)", "(clearance 520)")
m = re.search(r"\(class Power,Default[^(]*", t)
t = t[:m.start()] + m.group(0).replace(" /VBAT", "").replace(" /+3V3A", "") + t[m.end():]
p = t.index("(class Power,Default"); q = t.index("(width 500)", p); t = t[:q] + "(width 300)" + t[q+11:]
q = t.index("800:400", p); t = t[:q] + "600:300" + t[q+7:]
cls = '    (class PowerFine /VBAT /+3V3A\n      (circuit\n        (use_via "Via[0-3]_600:300_um")\n      )\n      (rule\n        (width 200)\n        (clearance 130)\n      )\n    )\n'
i = t.index("  (wiring"); j = t.rindex("  )\n", 0, i); t = t[:j] + cls + t[j:]
import os
t = t.replace('(use_via "Via[0-3]_600:300_um")', '(use_via "Via[0-3]_500:250_um")')
if os.environ.get("IN2", "plane") == "signal":
  # In2 becomes a routing layer; +3V3 is routed as tracks and poured on In2 afterwards
  i = t.index("(layer In2.Cu"); j = t.index("(type power)", i); t = t[:j] + "(type signal)" + t[j+12:]
  i = t.index("(plane /+3V3"); depth = 0
  for k in range(i, len(t)):
      depth += t[k] == "("; depth -= t[k] == ")"
      if depth == 0: break
  t = t[:i] + t[k+1:]
open(sys.argv[2], "w").write(t)
