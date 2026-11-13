# Own boards review (13 Nov 2026) — how the numbers were made

LIMA's review of ALFA's four boards (`own_boards_pack_2026-11-13.zip`, sha256 `f7947dcb…d49d138`,
company repo `chris/golf/own-boards-2026-11-13/`). The report is `own-boards-review-2026-11-13.html`
beside this file; the shelf copy is `reports/peter/LIMA_own_boards_review.html`.

The pack holds no `.kicad_pcb` files, so every layout number comes from the **Gerber X2 files**
(`alfa/fab/<board>/<board>_gerbers.zip`), which carry net names (`%TO.N`) and pin names (`%TO.P`).

| Script | Does |
|---|---|
| `tools/gerb.py` | Minimal Gerber X2 parser: tracks (with arcs), flashes, regions, net and pin attributes |
| `tools/a1.py <tools> <gerber dir> <board> <out.pkl>` | Parses all copper layers, prints a per-layer summary and some pair lengths |
| `tools/a2.py <tools> <pkl>` | Fast pairs: length per layer, edge gap, uncoupled length, length off the reference plane |
| `tools/a3.py <pkl> net,net,...` | Which pads each net lands on |
| `tools/a4.py <pkl> net,net,...` | Track widths, pour areas and via count per net |
| `tools/render.py <pkl> <layer> x0,x1,y0,y1 nets out.png [px/mm]` | Picture of one layer with chosen nets coloured |

Run with `python3 -I` (the pack is untrusted data; keep it in its own directory).

**Positive control:** the parser's lengths agree with ALFA's own pcbnew numbers in `data/board_data.json` to 0.01 mm
(USB3_0_TX_P 44.45, TX_N 44.49, RX 41.62/41.62, PCIE_CLK 6.63/6.63).

The pack itself is not committed here: it holds BlackBox's confidential drawings.
