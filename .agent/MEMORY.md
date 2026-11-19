# MEMORY — Agent LIMA

Scars and hard-won facts. Read before acting.

## Access and identity
- **`protect-peter` IS live and enforced at depth 2.** `[measured]` 2026-08-20 — the self-test
  reported `cannot forge chris/outbox/ (correctly refused)`. `ACCESS.md` still lists this ruleset
  as "confirm imported"; that line is stale. An ACCEPTED depth-2 write is a **regression** to
  report, never something to use.
- **The org is hyphenated:** `Aerosense-Aviation`. The unhyphenated form works only by GitHub
  redirect, and a lapsed redirect fails as an auth error indistinguishable from a broken key.
- **No `gh` CLI anywhere in this fleet, by design.** SSH keys only. A key cannot leak through an
  agent's context; a bearer token can — it lands in the remote URL, `git remote -v`, shell
  history and error messages. Never `cat ~/.ssh/id_*`.

## Instruments that lie
- **`grep 'Status: STANDING' memos/*.md` matches nothing** — the real header is
  `**Status:** STANDING` with asterisks. The wrong form returns zero and looks like "no standing
  memos". Use `grep -l '\*\*Status:\*\* STANDING' memos/*.md`. There are five.
- **Banner field 3 (`Record state`) is currently a broken instrument.** It measures the newest
  commit touching `record/`, but the company corpus moved out of `record/` into `aerosense-ops`
  on 2026-08-20. It still returns a value, which is the dangerous kind of wrong. Do not trust it
  for new reports until it is repointed.
- A broken instrument almost always fails **toward the answer you expected**. Distrust a result
  that confirms the hypothesis a little too neatly.

## Git discipline
- **Never `git add -A`, never `git commit -a`.** On 2026-08-17 a whole-tree pathspec deleted
  **116 files across two other lanes** in a shared checkout. Stage explicit paths, read
  `git status` before every commit.
- **Exit 0 is not proof a push landed.** Compare all 40 chars from `git ls-remote`.
- `! [rejected] (fetch first)` is normal — fetch, rebase, push again. **Never `--force`.**
- A push rejected naming a file-path rule means I touched a lane that is not mine. Correct it;
  never route around it.

## Onboarding gotcha, for whoever onboards next
- **Phase A of `ONBOARD_PROMPT.md` cannot start cold.** It says to fetch
  `AGENT_BRAIN_TEMPLATE.md` and `bootstrap-agent.sh` from plain `github.com` blob URLs, but both
  live in the private company repo, there is no `gh`, and the thing that creates the SSH key *is*
  `bootstrap-agent.sh`. A machine with no key cannot reach the script that gives it one.
  Workaround `[measured]` 2026-08-20: generate `~/.ssh/id_ed25519` by hand first, register it,
  then take both files from the clone. `bootstrap-agent.sh` is idempotent and finds the existing
  key — it only creates `id_ed25519_aerosense` when `ssh -T git@github.com` fails outright.

## Konnect (KiCAD MCP) — installed 2026-08-21
- **Binary:** `~/.konnect/bin/konnect` v0.7.0, aarch64-apple-darwin, from the GitHub release.
  Tarball `sha256 589d5611c25f84e8ca5a290c5b2ad88fb0419287915d7d67f53a3463d46bdb65`. Registered
  project-scoped in `lima/.mcp.json`. Requires KiCad 10 (have 10.0.3) and `kicad-cli` for
  ERC/DRC/export.
- **It answers RULE 1 properly.** Only 2 of 19 toolsets load at startup (`project`, `config`);
  the rest come in via `load_toolset(name)` and can be pruned with `unload_toolset`. So the
  standing context cost is ~7 tools, not 203. `[measured]` via a stdio MCP handshake.
- **Most PCB tools need KiCad running with the board open** (IPC API, protobuf over NNG).
  `flip_component` is the inverse — it needs the board *closed*. Not a headless/batch tool.
- **`konnect install` writes to `~/.claude/`** — skills, agents, and one `PreToolUse` hook
  patched into `~/.claude/settings.json`. **Deliberately NOT run.** The hook itself is benign
  (prints a reminder string), but `CLAUDE.md` §6 says an agent must not be able to rewrite its
  own guards, and registering via `.mcp.json` gets the tools without touching global config.
  Their own issue #238: `konnect init --help` once ran the installer and rewrote `~/.claude`
  because unknown args were silently skipped. Fixed, but it shows the blast radius.
- **Review findings** `[measured]` by reading the source at `2183267`: no telemetry. Network is
  confined to one module (`tools/integration.rs`) — LCSC part lookup and the JLCPCB parts DB from
  `bouni.github.io/kicad-jlcpcb-tools`, both opt-in. Subprocesses use argv, never a shell, so no
  injection through `kicad-cli` args. **The parts-DB download has no checksum** — TLS only, and
  the size caps are 1 GiB archive / 8 GiB database, so watch the disk if you ever pull it.
- **License is AGPL-3.0-only** (a `COMMERCIAL.md` exists). Matters if Aerosense ever modifies it
  or ships it inside a product — raise with Chris before that happens, not after.
- **Beta, and macOS is the less-tested platform** — upstream says Windows has the mileage. v0.7.0
  was published 2026-08-21, the same day it was installed, with single-digit download counts.

## KiCAD scar — a green ERC is not a correct circuit (2026-08-21)
`[measured]` on the first Konnect throwaway board. I placed `Device:LED` with `rotation: 270`,
which put the **cathode on top**. `connect_pins(R1.2 -> D1.2)` then drew a single vertical wire
from y=78.74 straight down to the anode at y=99.06 — **passing through the cathode pin at
y=91.44 on the way**. The cathode joined that wire, so R1.2, D1.1 and D1.2 all landed on GND.
The LED was shorted and had zero volts across it.

**What every instrument said about this broken circuit:**
- `run_erc` — **0 errors.** KiCad does not treat "both pins of a passive on one net" as a rule
  violation, so it is not lying, but green ERC is *not* evidence the circuit works.
- `find_shorted_nets` — **0 shorts.** From the netlist's view there was no short, just one net.
- The only signal was an **absence**: ERC warned `Label connected to only one pin: 'VCC'` and
  gave **no matching GND warning**, because GND had silently collected three pins.

**What actually caught it:** `get_pin_net_name` per pin, and counting nets. Three pins reading
`GND` where the midpoint should have been unnamed.

**Rules taken from this:**
1. `connect_pins` routes a straight line and will run it **through a symbol body** without
   warning or adding a junction. Check pin coordinates with `batch_get_schematic_pin_locations`
   **before** wiring, not after.
2. For `Device:LED`, `rotation: 90` puts the anode up (A at the smaller y). 270 inverts it.
3. **Verify a circuit by its per-pin nets, never by ERC's exit state.** An unnamed midpoint net
   reading `None` from `get_pin_net_name` is the *correct* signal for a two-component divider —
   `list_schematic_nets` counts only *named* nets, so "2 nets" here is right, not a shortfall.

## KiCAD PCB via Konnect IPC — scars from the layout shakedown (2026-08-21)
`[measured]` end-to-end on the blinky throwaway board. All of these cost real time.

**1. IPC edits live in KiCad's memory until you SAVE. This makes DRC lie.**
`get_drc_violations` and every `kicad-cli` export read the **file**; IPC tools read **KiCad's
memory**. After syncing and routing over IPC I ran DRC: **0 violations**. Called
`save_project`, re-ran the identical check: **4 violations, two of them errors.** The clean
result was measured against a board that did not yet contain the work. `get_board_info` showed
`net_count: 0` at the same moment `get_nets_list` (IPC) showed 4 nets — that disagreement is
the tell. **Save before you believe any file-based check.**

**2. A read immediately after a geometry-changing IPC call can be stale.**
`get_component_pads` right after `rotate_component` returned **pre-rotation** pad positions. I
concluded the rotation had failed and routed to the old coordinates — straight onto the GND pad.
It had worked; my instrument was stale. **Re-read after a save, not straight after the write.**

**3. Routing tools drive straight through whatever is in the way.**
`route_pad_to_pad` and `route_trace` lay copper on a direct path with no awareness of
intervening pads — it shorted `/GND` to `Net-(D1-A)` by crossing D1's GND pad. This is the
**same failure mode** as `connect_pins` on the schematic (see the ERC scar above). Same rule
applies: read the pad coordinates first and route around, or move the part.

**4. Footprints placed in file-mode have no schematic identity.**
`place_component` with KiCad closed writes a footprint with a blank symbol path.
`update_pcb_from_schematic` then refuses the whole plan with `duplicate_board_identity` and
`reference_identity_conflict` — correctly, rather than guessing which pads get which nets. Fix:
`delete_component` the orphans and let the sync add them. Do the schematic first, always.

**5. Tools that fail closed, and deserve credit for it.** `add_copper_pour` refuses while KiCad
holds the board: *"a copper pour written to the file would be discarded by KiCAD's next save."*
`update_pcb_from_schematic` requires `expected_plan_revision` from a dry run before it will
apply. `place_component` states in its result when it fell back to a file edit.

**6. Setup gotchas.** KiCad's IPC is OFF by default — `api.enable_server` in
`~/Library/Preferences/kicad/10.0/kicad_common.json` (backed up as `.bak-preconnect`); KiCad
rewrites that file on exit, so edit it CLOSED. Konnect reads its config **once at launch**, so
`~/.konnect/bin/settings.json` (`ipc_socket_path: ipc:///tmp/kicad/api.sock`) needs a client
restart. The API server runs in the **project manager** — an editor launched standalone gets
`ppid 1`, never registers, and every call returns `AS_UNHANDLED`. Pour `points` are objects
`{x,y}`, not `[x,y]` pairs.

## Konnect library + IPC findings (2026-08-21, building the ConnectCore 93 part)
`[measured]` while adding a Digi ConnectCore 93 SOM to the throwaway board.

**Konnect bugs found — all silent, none raised an error:**
- **`create_symbol` drops `footprint`, `datasheet` and `description`.** Passed all three; the
  .kicad_sym came back with all three properties empty. Reported `success: true`. Set them on
  the instance with `edit_schematic_component` instead, or the netlist preflight later fails
  with "KiCad netlist node is missing footprint".
- **`get_symbol_info` returns 0 pins** for a symbol whose file genuinely holds 118. The
  `power_pin_count: 0` in the create response is wrong the same way. **Grep the .kicad_sym to
  check a symbol — the read-back API lies.**
- **`set_board_size` APPENDS an outline, it does not replace.** Calling it twice left two
  overlapping rectangles on Edge.Cuts and DRC reported `invalid_outline` + four
  `copper_edge_clearance` errors. Strip the old `gr_line` Edge.Cuts blocks before re-sizing.

**IPC socket rule — this is the thing that cost the most time.** The first KiCad process to
start owns `/tmp/kicad/api.sock`; any later one gets `/tmp/kicad/api-<pid>.sock`. A **standalone
`PCB Editor.app` IS addressable** — point `ipc_socket_path` at whichever socket `lsof` shows it
owning. (Corrects an earlier conclusion of mine that a standalone editor can never register and
that only a GUI double-click from the project manager works. It registers fine; I was pointing
at the wrong socket.) The project-manager-only case gives `GetOpenDocuments (AS_UNHANDLED)` —
that error means *no editor holds a document*, not that IPC is down.

**Stale `.lck` files block the sync and carry no PID.** `~<name>.kicad_sch.lck` survives a killed
editor, and `update_pcb_from_schematic` refuses with "open in the schematic editor" forever
after. They contain only `{"hostname","username"}`, so nothing can tell live from stale — delete
by hand once the editors are closed.

**My own scar: a land pattern whose corners collided.** Building rows and columns each on their
own centre-span put pad 32 and pad 33 at the identical coordinate, at all four corners. Neither
`create_footprint` nor the pad count caught it — **the render did**, as four cross-shaped blobs.
Now guarded by an explicit pairwise overlap assert before the footprint is written. **For any
generated footprint, test every pad pair for overlap and look at the render; a correct pad
*count* says nothing about pad *positions*.**

## KiCAD scar — attach the 3D model EARLY; it is a geometry check, not decoration (2026-08-21)
`[measured]` on the ConnectCore 93 footprint. The footprint was DRC-clean, had zero pad overlaps,
118 pads at the right pitch and right counts — and was **geometrically impossible**. Digi's STEP
proved the module is **40.000 × 45.000 mm**; the side pad columns had been placed at x = ±16.51 off
a misread "33.56 mm" HRM dimension, putting all 64 of them **2.49 mm underneath the module body**
where no castellation can reach. The top/bottom rows, derived the same way, happened to be right.

**Every instrument we had said the footprint was fine.** Pad-overlap checks pass — non-overlapping
pads in the wrong place still don't overlap. DRC passes. Pad count and pitch reconcile against the
datasheet (32+27+32+27 = 118). None of them know where the part's *body* is. The vendor 3D model is
the only artefact that carries the outline, so it is the only thing that can catch this class of bug.

**Rules taken from this:**
1. **Attach the vendor 3D model when you create the footprint, not later.** For any part whose pads
   reference a body edge — castellated, LGA, connectors, anything with a mechanical interface — the
   model is a *verification instrument*. One render answered a question three checks could not.
2. **Render headlessly to verify:** `kicad-cli pcb render` needs no running KiCad. Place the
   footprint on a throwaway board, render `--side top` and `--side front`, and look. Cheap, and it
   is a real point-of-use test rather than a belief.
3. **Do not regex a STEP file for geometry.** A naive `CARTESIAN_POINT` sweep mixes each component's
   *local* frame with the assembly frame — it reported a 62.5 mm span for a 40 mm module. Tessellate
   with a real kernel (`pip install cascadio trimesh`, `cascadio.step_to_glb`, apply `scene.graph`
   transforms) and remember cascadio emits glTF **metres** — multiply by 1000.
4. **A vendor's own documents are not automatically about your part.** Digi's asset titled
   "ConnectCore 91 and 93 — Host PCB footprint and cutout drawing" contains **ConnectCore 8X** files
   dated 2022. The one document we were told to trust for corner geometry is the wrong module.
5. **Read the whole model, not just the outline.** 105 solids hang 0.700 mm below the SOM's PCB
   bottom face — the module cannot seat flat on a plain host board. A footprint with no keepout for
   that looks perfectly correct in 2D and is unbuildable.

## KiCAD scar — a datasheet dimension measures what it points at, not what you hoped (2026-08-21)
`[measured]`. Follow-on to the scar above. The CC93 footprint's 118 pads were built around **33,56 mm**
read off HRM 90002549 p.83 as "the pad row span". It is the **HOST PCB CUTOUT width**. One misread
dimension put 64 of 118 pads 3.49 mm inboard, under the module body, and every downstream check —
pad-overlap, DRC, pad-count reconciliation against the datasheet — passed anyway.

**How it was finally settled, and what nearly broke each step:**
1. **Digi's own Altium `CC93_DVK.PcbLib` did not answer it.** It holds a 474-pad **LGA** array — a
   different variant from the 118-pad castellated part. Reading it was still worth it: **KiCad ships
   an Altium importer usable from Python** — `/Applications/KiCad/KiCad.app/Contents/Frameworks/
   Python.framework/Versions/3.9/bin/python3.9`, then `pcbnew.PCB_IO_MGR.FindPlugin(
   pcbnew.PCB_IO_MGR.ALTIUM_DESIGNER)` → `.FootprintEnumerate(path)` / `.FootprintLoad(path, name)`.
   No need to hand-parse OLE. Same trick reads Eagle, CADSTAR, EasyEDA, PCAD.
2. **The HRM drawing is an embedded BITMAP, not vector.** A PDF content-stream walk returned 3
   subpaths. Check `page.images` before writing a vector extractor.
3. **Autocorrelation picked the 2nd harmonic** on one of four pad runs — 100.8 px against the true
   50.4 px — which would have halved every dimension. Three concordant runs outvoted the outlier.
   *Measure the same quantity several independent ways and let them vote; a lone number has no way
   to tell you it is wrong.*
4. **Calibration was checked against four of the drawing's own labels** (33,56 / 20,86 / 12,07 /
   3,22, all reproduced to better than 0.1 mm) **before any result was believed.** A dimensioned
   drawing carries its own test fixture — use it.

**Rules:**
- **Before building geometry off a single dimension, confirm what it is measuring** by reproducing a
  second, independent dimension from the same drawing. One number read off a datasheet is `[assumed]`,
  not `[fetched]`, until something else agrees with it.
- **Prefer a constraint that falls out rather than one you set.** The corrected pads straddle the
  module edge by exactly **1.000 mm**, which then matched DETAIL A's `1` — nobody aimed at that, and
  that is precisely why it is good evidence. A number you chose proves nothing; a number that arrives
  on its own and agrees with an independent source is close to proof.
- **When correcting a document, mark the old claim superseded in place — do not delete it.** The
  wrong reasoning is what stops the next session repeating it.

## KiCAD/Konnect scars — the dual-IMU build (2026-08-21)
`[measured]` building `kicad/imu-board` (ICM-45686 + BMI088).

**A stock footprint that matches on name, size and pin count can still be the wrong land pattern.**
`Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y` looks like a perfect fit for the ICM-45686's
14-pin 2.5x3.0mm LGA. It is not — it is a **3x4 perimeter** pattern whose `descr` field names an ST
LSM6DS3TR-C, while the ICM-45686 is **dual-row 7+7**. Nothing but reading the footprint's own pad
layout and `descr` would catch it. **Always open the .kicad_mod and read `descr` + pad positions
before assigning a generic package footprint** — the filename describes the package, not the part.

**When the datasheet is ungettable, author the symbol and leave the footprint OFF.** TDK gates
DS-000577 behind a redirect; LCSC's `/datasheet/<code>.pdf` returns a title-only shell; SnapEDA
403s. The pinout was still fully recoverable from **two independent secondary TDK documents that
agreed** (an EVB user guide's pinout figure, and a sensor-module datasheet whose schematic embeds
the part as U1 with pin numbers). Pinout sourced, land pattern not — so the symbol shipped and the
footprint field stayed empty with a `Footprint_Status` property saying why. Half a part, honestly
labelled, beats a whole one with invented geometry.

**WebFetch's PDF summariser invents values when the document does not contain them.** Asked for
BMI088 decoupling values it produced "VDD decoupling in the 10-100 µF range" and "pull-ups
typically 2.2-10 kΩ" — **numbers that appear nowhere in the datasheet**, which shows them only
inside a raster connection diagram. It failed toward a plausible-looking answer, exactly the way
§3 warns. **Fix: WebFetch saves the raw PDF to the tool-results dir — parse it locally with
`pypdf` and grep it yourself.** (`pypdf` needs `cryptography` for AES-encrypted PDFs; Bosch's is.)

**Konnect bugs found this session, both silent:**
- **`annotate_schematic` assigns bare numeric references to power symbols.** Two `power:PWR_FLAG`
  instances came out referenced `"1"` and `"2"` instead of `#FLG01`/`#FLG02`.
- **`edit_schematic_component(new_reference=...)` renames the property but not the instances
  path.** It *does* report this — `"the property was renamed but the netlist still reads the old
  designator"` — so read the `errors` array even when the call looks like it worked. **Fix: pass
  `reference` to `add_schematic_component` at creation time**; deleting and re-adding was cleaner
  than repairing it.

**`find_orphan_items` counts the pin end of every `connect_to_net` stub as a dangling wire.**
34 stubs, 34 "orphans", zero real. The netlist showed every one of those pins on its correct net.
Don't chase them — cross-check against `export_netlist_summary`, which is the authoritative read.

**BMI088 accel/gyro mapping is the reverse of what the numbering implies** — CSB1/SDO1 are the
**accelerometer**, CSB2/SDO2 are the **gyroscope** (datasheet §6 Table 10). Also: the accel always
boots in I2C regardless of the PS pin and needs a rising edge on CSB1 to enter SPI, and its SPI
reads return a leading dummy byte. The gyro does neither.

## Scar — I answered "is X available?" from a table that could not contain the answer (2026-08-21)
`[measured]`. I told Peter the castellated ConnectCore 93 has **no SPI**. It has LPSPI3, a complete
4-wire master. He challenged the claim; he was right.

The mistake: `cc93_pads.json` stores each pad's **primary** signal name. I grepped it for `SPI`, got
nothing, and reported an absence. But a pin's *muxed* functions live in a column that extraction never
captured — the HRM had **296 ALT entries across 47 pads** that my table simply did not contain.

**This is the §3 scar in its purest form and I still walked into it.** A broken instrument fails toward
the answer you expected: I had already framed the castellated variant as the cut-down one, so "no SPI"
felt right and I stopped. Worse, an *absence* is the one result you cannot sanity-check by looking at
it — a wrong presence shows up as a nonsense value, a wrong absence looks exactly like the truth.

**Rules:**
1. **Before reporting that something is ABSENT, prove your source could have shown it present.** Find
   a known-present example of the same class in the same table. Had I grepped for `UART` and seen only
   primary names, the missing ALT column would have been obvious in seconds.
2. **On a pin-muxed SoC, "not on the pinout" is meaningless without the mux table.** Every pad of an
   i.MX-class part has up to 8 ALT functions. Always parse the ALT columns; never answer peripheral
   availability from a signal-name list.
3. **Record provenance per field, not per file.** `cc93_pads.json` now carries `alt_source` on every
   record, so a future session can see at a glance which pads were checked against the manual and
   which have no ALT column at all. A table that cannot say what it does not know will mislead again.
4. **When the human contradicts a measurement, re-measure before defending it.** The challenge cost
   one tool call to check and would have cost a carrier board's worth of rework to ignore.

## KiCAD scar — a symmetric part hides a 180 degree error from every visual check (2026-08-21)
`[measured]` while placing the ConnectCore 93 STEP on Digi's LGA land pattern. Six rotate/offset
candidates were swept and rendered. **Two of them seated the module perfectly on the pads.** They
differed by 180 degrees. The module outline is a plain rectangle, so both renders looked right — and
one of them was wrong.

**A visual check cannot verify rotational orientation on a symmetric outline.** It verifies position
only. I nearly shipped a coin-flip.

What settled it: `cc93_pads.json` maps castellated pads to LGA pads, giving 108 pads whose real
coordinates exist in *both* footprint files. Correlating the coordinate sets under each candidate
rotation gave +0.998 for -90 deg and **-0.998 for +90 deg** — the wrong answer shows up as a clean
*anti*-correlation across 108 points, which no render could have shown.

**Rules:**
1. **To verify an orientation, correlate many known point pairs — never eyeball an outline.** Any part
   whose body is symmetric (BGA, LGA, QFN, most modules) will render identically at 180 degrees.
2. **`(rotate (xyz ...))` in a .kicad_mod is NEGATED by KiCad.** A file value of `+90` produces a
   geometric -90. Determine it empirically from where the model lands, never from the sign you wrote.
3. **A 3D-model sweep needs `${KIPRJMOD}` to resolve.** My first sweep rendered six boards from the
   scratchpad; the model silently failed to load in all six and every render looked identically
   model-less. Pass `kicad-cli pcb render -D KIPRJMOD=<dir>`. *An absent model and a mispositioned
   model look the same when the answer is "nothing there".*

## KiCAD scar — a vendor footprint ships the vendor's whole board (2026-08-21)
`[measured]`. Digi's `CC93_DVK.PcbLib`, converted through KiCad's Altium importer, produced a
footprint containing **an `Edge.Cuts` polygon** (21.5 x 34 mm), a silkscreen rectangle of the DVK's
own outline (+/-43.5 x +/-36.5, far larger than the 45 x 40 module), 31 items of routing artwork on
`Dwgs.User`, DVK frame marks on `User.3`/`User.20`, and six zero-size pads named MH1-6 at +/-37,+/-27
— board mounting holes well outside the module.

**Edge.Cuts inside a footprint cuts the board it is placed on.** Dropped in unexamined, that vendor
library would have punched a hole through AeroNode. There was also no courtyard whatsoever.

**Rule: after importing any vendor footprint, enumerate its graphics BY LAYER before use.**
`get_footprint_info(include_graphics=True)`. Ask of every item: is this the *part*, or the vendor's
own *board*? Anything on Edge.Cuts, or larger than the component body, is the latter.

## KiCAD scar — a corrupt .kicad_sym reports EMPTY, never an error (2026-08-21)
`[measured]` while generating the 474-pin ConnectCore93_LGA symbol. My merge left **one extra closing
paren** at end of file. Nothing errored. `list_symbols_in_library` returned **`count: 0`** — and the
*existing, previously-good* `ConnectCore93` symbol disappeared from the listing with it.

**A library that will not parse is indistinguishable from a library that is empty.** Had I not read it
back, I would have committed a file that silently destroyed a working symbol.

**Rules:**
1. **After writing any generated library file, read it back and assert the expected count.** Not "did
   the write succeed" — the write always succeeds. `count == n_expected`, or it is broken.
2. **Assert paren balance before writing** an s-expression file (strip string literals first).
3. **Keep the file in git before generating into it**, so `git checkout --` is a one-command undo.
   That is what saved this one.
4. **The cross-check that actually matters for a new part is symbol-pin-numbers == footprint-pad-names,
   asserted in BOTH directions.** A symbol and footprint that disagree still pass ERC and DRC
   individually, and produce a netlist that wires the wrong pads. 474/474 exact match, both ways.

## KiCAD scar — a pin's `at` IS the connection point; do not add the pin length (2026-08-22)
`[measured]` wiring the ConnectCore93's 166 GND pads. I computed each pin's connection point as
`at + length` along its rotation, drew two rail wires through those coordinates, added 162 junctions,
labelled both rails — and **connected nothing.** The rails sat 2.54 mm inside the pins.

In a `.kicad_sym`, `(pin ... (at x y rot) (length L))` gives the **connection point** at `(x,y)`; the
graphic extends from there *into* the body. There is nothing to add.

**What made it detectable, and what did not:**
- `add_wire` returned success. `batch_add_junction` returned `added: 81` twice. Both were true and
  both were useless — they built a correct rail in the wrong place.
- **The tell was the ERC count not moving.** `pin_not_connected` stayed at exactly 336 when it should
  have fallen to 170. Two `unconnected_wire_endpoint` warnings appeared, which is the only reason the
  rails were visibly wrong at all.

**Rules:**
1. **Predict the ERC delta before a bulk connection, then check it.** "336 should become 170" is a
   test; "it succeeded" is not. Every bulk edit since has been checked this way and each matched.
2. **Measure the geometry, don't derive it.** One `connect_to_net` call on a single pin reports the
   exact stub coordinates it used. That is ground truth and costs one call — do it before computing
   167 coordinates from a formula.
3. To bulk-connect a column of pins: one wire from first to last pin coordinate, junctions on the
   **interior** pins only (the two end pins land on the wire's own endpoints), one label. 166 pins in
   six calls.

## KiCAD scar — module supply pins: check direction, and don't multi-drive one rail (2026-08-22)
`[measured]` on the ConnectCore93_LGA symbol. Two separate mistakes, one real and one cosmetic:

1. **`NVCC_SD2` was typed `power_out`. It is an INPUT** — the HRM lists it in the *input power rails*
   table (the CPU's uSDHC2 I/O supply, fed externally), not the output table. My generator classified
   it by name pattern (`*_SD2` looked like a rail) instead of by what the manual said. **Classify
   supply pins from the datasheet's own input/output tables, never from the pin name.**
2. **`3V3` on 5 pads and `1V8` on 4 pads are ONE internal rail each.** Typing every pad `power_out`
   made ERC raise 8 `pin_to_pin` output-to-output conflicts on a perfectly correct connection. KiCad
   cannot express "these pads are internally the same node" — the convention is **one `power_out` per
   rail, duplicates `passive`.**

Corollary: **when a datasheet mentions a supply pin exactly once, in a pad list, with no direction —
leave it unconnected and say so.** `3V3_RF` appears once in 103 pages. A guess on a supply pin is
destructive; an unconnected pin with a written question is not.

## Scar — a charger's watchdog can undo a safety setting at RUNTIME (2026-08-22)
`[fetched]` from the BQ25798 datasheet while designing AeroNode's LiFePO4 charger. I had already
flagged the hazard as "2S LiFePO4 charges at 7.2 V, not the 8.4 V a 2S Li-ion charger defaults to —
so set VREG at boot before enabling charge." **That framing was incomplete and would have cooked the
pack anyway.**

The datasheet: *"when the REG_RST bit is set **or the watchdog timer expires**, the registers are
reset to default values with ICHG, VSYSMIN and VREG automatically returning to 1A, 7V and 8.4V."*

So VREG reverts to the Li-ion default **on every watchdog expiry** — 40/80/160 s — with no host
involvement. A crash, a hang, a suspend, or a driver paused for a firmware update silently applies
+1.2 V of overcharge. Setting the register once at boot is not a fix; it is a fix that expires.

**Rules:**
1. **When a part has a safety-critical register, ask what RESETS it, not just what sets it.** Search
   the datasheet for "watchdog", "REG_RST", "POR default", "reverts". A setting that can be undone by
   a timer is not a setting, it is a lease.
2. **A hardware choice can create a firmware obligation.** Disabling that watchdog is now a
   *hardware-imposed* requirement on the Linux driver. Write it into the bring-up notes at design
   time — it will not be rediscovered by whoever writes the driver.
3. **Pins that select a safe state must be resistor-defined, not host-defined.** `/CE` pulled high
   from the charger's own `REGN` rail means charging is off before any host exists. The datasheet also
   says outright: *"CE pin must be pulled HIGH or LOW, do not leave floating."*
4. **Verify quotes like this in the actual PDF.** The first hint came from a web-search summary; the
   wording that mattered (that the *watchdog*, not just REG_RST, triggers it) was only confirmed by
   fetching the 151-page datasheet and grepping it.

## Scar — RP1/Pi 5 I2S: clock direction is a BLOCK CHOICE, and 3 channels is illegal (2026-09-02)

Bringing an ADAU1860 up on a Pi 5 as a data pipe. Four things that are not guessable and cost real
time if you assume the obvious:

1. **You do not configure clock direction on RP1 — you pick a different peripheral.** `dwc-i2s.c`
   sets `DW_I2S_MASTER` *or* `DW_I2S_SLAVE` exclusively, from a hardware synthesis parameter read
   out of COMP1. `dw_i2s_set_fmt()` then rejects `SND_SOC_DAIFMT_BC_FC` unless SLAVE is set. Pi 5
   ships two blocks muxable to GPIO18-21 and aliases them in `bcm2712-rpi.dtsi`:
   `i2s_clk_producer` -> `rp1_i2s0` (Pi drives the clocks), `i2s_clk_consumer` -> `rp1_i2s1`
   (codec drives them). Point a codec-master card at `&i2s` and you get `-EINVAL` from `set_fmt`,
   which looks nothing like a clocking problem and sends you to the scope for an afternoon.
2. **Channel count must be 2, 4, 6 or 8.** Three is `-EINVAL` (`designware_i2s.h`). A 3-axis sensor
   physically cannot be sent as three channels. The ceiling is 8 even when the codec does TDM16.
3. **Any `dai-tdm-slot-num` forces `data_width = 32`**, overriding the requested format. Use S32_LE.
4. **In consumer mode the driver never touches the clock**, so the rate you hand ALSA is never
   checked against the wire. Codec clocking a different fS than ALSA was told = no error at all,
   just unexplained XRUNs later. Scope the frame rate; do not trust the ALSA rate as evidence.

Generalises: **when a peripheral seems to refuse a legal configuration, check whether the SoC
exposes a *second instance* wired for that mode rather than a register that switches it.**

Detail at `linux/adau1860-pi5/` (NOTES.md, DATA_OVER_I2S.md). Related: audio-DSP data transport —
samples are read as fractions in [-1,+1), so linear blocks are scale-invariant but limiters and
compressors have absolute dBFS thresholds; and any rate crossing inserts an interpolator or ASRC
that filters the payload.

## Scar — a register that reads back correctly can still do nothing (2026-09-02)

First hardware run of the ADAU1860 on Peter's Pi 5. `SPT0_CTRL2 = 0x02` means "generate BCLK at
6.144 MHz". It wrote, it read back `0x02`, and **no clock came out** — because `PLL_EN`
(`PLL_PGA_PWR` bit 0, reset 0) was never set, so the generator had no source to divide. Readback
proves the write landed. It does not prove the function works. **Verify at the point of use** meant,
here, sampling the actual pin: GPIO18/19 as inputs, 200 samples each, `hi=0 lo=200` — dead. That
measurement is what turned "driver problem?" into "no source clock" in one step.

I had marked `PLL_PGA_PWR` `[gap]` in my own write-up and shipped anyway. **A `[gap]` sitting in the
middle of an init sequence is not a footnote, it is the bug you have not found yet.** Close it or
say the sequence is untested — I said the latter, which is why this cost an hour and not a day.

Two more, both generalisable:

- **Config-before-power.** `CLK_CTRL1`, `PLL_PGA_PWR` and `CHIP_PWR` go read-only once the power
  domains come up, writes are accepted silently, and `SOFT_FULL_RESET` does not clear them — only a
  power cycle does. Vendor power-up sequences order things for a reason; deviating cost a trip to
  the bench. When a datasheet gives numbered power-up steps, follow the numbers.
- **Ask what "I2S0" refers to.** On Pi 5 `rp1_i2s0`/`rp1_i2s1` both reach GPIO18-21 and the choice
  *is* the clock direction; on the codec, SPT0/SPT1 are its two serial ports. "I'm using I2S0" is
  ambiguous across the two chips and the readings are contradictory.

**And there is no software way out.** All three `RESETS` variants (`0x01` full, `0x10` soft, `0x11`
both) were ACKed by the chip and changed nothing, including when raced with 40 immediate back-to-back
writes to catch a re-latch window. Once an ADAU1860's power domains are up, only a power cycle or a
`PD` toggle restores the clock registers. Do not spend time hunting a software reset.

Detail: `linux/adau1860-pi5/RESULTS-2026-09-02.md`. Related: [[rp1-i2s-clock-direction]].

## Scar — a cross-compiler you never use can change what the machine boots (2026-09-04)

Installing ArduPilot on `scopenode` (Pi 5). `Tools/environment_install/install-prereqs-ubuntu.sh`
installs `g++-arm-linux-gnueabihf` unconditionally — most ArduPilot Linux boards are 32-bit ARM
cross targets. On Raspberry Pi OS that package's dependency chain is
`g++-arm-linux-gnueabihf` -> `linux-libc-dev-armhf-cross` -> `linux-headers-rpi-*` ->
**`linux-image-rpi-*`**, and the kernel meta-packages pull the current Pi kernel and rewrite
`/boot/firmware/kernel_2712.img` and `kernel8.img`. `[measured]` 6.12.47 -> 6.18.39 installed;
`uname -r` unchanged; **the change lands silently at the next reboot.**

The cross-compiler was never used — `hwdef/linux` sets `TOOLCHAIN native` and we compiled aarch64
on the Pi. So a package with no role in the build changed what the machine will boot.

Generalises, and this is the part to remember:

- **A toolchain package is not inert.** On distros where the kernel ships as an apt package, a
  `*-cross` or `*-headers` dependency can reach the boot partition. Check `apt-get -s install`
  (simulate) before letting an unfamiliar prereqs script run on a machine whose kernel is load-bearing.
- **`uname -r` is not evidence that nothing happened.** The running kernel is the *old* state; the
  damage is in `/boot/firmware` and `dpkg -l | grep linux-image`. Look at what will boot, not what
  is booted. A machine can be already-changed and look fine indefinitely.
- **Bench results are pinned to a kernel version.** Everything in `linux/adau1860-pi5/` was measured
  on `6.12.47+rpt-rpi-2712`. Peter ruled 2026-09-04 to accept 6.18.39, so those results need
  re-verifying after the next reboot. Related: [[rp1-i2s-clock-direction]].

## Scar — a control that returns punctuation is a broken instrument, not a null result (2026-09-04)

Testing whether ArduPilot claimed GPIO18-21 from the ADAU1860. My negative control printed
`18:=| 19:=| 20:=| 21:=|` for every sample — I had parsed `pinctrl get`'s `$4`, which is the
literal `|` separator, instead of `$5`. Six identical rows of punctuation read very easily as
"nothing changed, all clear."

Fixed to `$5` and the control immediately produced the finding: GPIO19 flips `lo`->`hi` **on its
own** with no ArduPilot process running, because it is `I2S1_WS`, a live frame clock. So the
before/after difference that looked like ArduPilot claiming a pin was a sampling artefact.

Two lessons: **the mux and pull columns are the evidence of a claim, not the level column** — a
level is a sample of a moving signal; and per §3, the broken instrument failed *toward* the answer
I was hoping for. Distrust a clean result that arrives too conveniently.

## Fact — `protect-peter` is live and matches `reports/peter/**` (2026-09-04)

`[measured]` Pushing `reports/peter/LIMA_ardupilot_pi5.html` as `pb-aero` returned:

```
remote: Bypassed rule violations for refs/heads/main:
remote: - File path is restricted
remote:   Found 2 violations:
remote:     reports/peter/LIMA_ardupilot_pi5.html
remote:     reports/peter/MANIFEST.md
```

The push landed (local == remote, all 40 chars). This is **correct and expected**:
`aero-ssh-bridge/ACCESS.md` lists `protect-peter` as restricting `peter/**`, `record/peter/…` and
`reports/peter/…` with bypass `user pb-aero + Repository admin`. I am the bypass actor in my own lane.

**Why it is worth recording:** ACCESS.md line 43 still marks `protect-peter` as *"imported, not yet
proven"*, and lines 77-82 argue a lane's own agent cannot prove its own ruleset, because the owner's
writes succeed whether or not the rule exists. That reasoning holds for a **silent** success — but
this push was not silent. **The server named the ruleset violation while applying the bypass**, which
is positive evidence that the rule exists and matches those exact paths. It does *not* prove the rule
**blocks** a non-owner; that still needs a push from someone who is neither owner nor admin.

Generalises: **a bypassed rule announces itself.** If you have bypass rights, a push that "just
worked" may still be reporting a live guard — read the remote's output, do not just check the SHA.
And do not mistake a bypass notice for a rejection: the correct response here was to verify I was in
my own lane, not to back the change out.

---

## Scar — publishing is not an end-of-subject act, and a shelf "open item" is a live order to strangers (2026-09-10)

The ADAU1860 shelf report sat at a 2 September snapshot while the lane produced a result most days
for six days. Two people were blocked behind the gap. INDIA had **twice** told JULIETT to build its
probes from my shelf reports; following that literally would have had it ask which slots the codec
latches and whether duplex survived 6.18.39 — **both of which I had already answered in my own lane.**
JULIETT caught it and stopped: *"that is the fourth re-derivation you told me not to make."* The CM5
I2S question was worked from scratch three times, twice in one day.

**The mechanism, and it is the part worth keeping.** An item my report lists under *"Open:"* or
*"Next:"* is not a note to myself — it is **a standing instruction to every other agent to go and
derive that thing**. So a stale open list does not merely under-inform; it *actively dispatches*
other people's sessions at questions I have already closed. That is the one kind of staleness with a
cost that grows while nobody notices.

**This is our own dashboard doctrine, which I had not recognised applies to reports.** A display that
keeps rendering its last value after the feed has moved on is lying. My "Next:" list was that display.

**The rule, and it is cheap because I write the open list myself:** when a lane finding closes an item
the shelf lists as OPEN, **the shelf gets republished in the same session** — not at the end of the
subject, because a live subject has no end. Tested the same hour it was adopted: JULIETT's rate-lock
probe landed while I was pushing and closed an item my *brand-new* banner had just listed as open.
Folded in immediately rather than "next time".

### The second half — state recorded only where the sender cannot see it looks like an order ignored

`inbox/README.md` step 4 says to set the request's `status:` to `answered` and point at the reply.
I had been recording task state **only** in my own `.agent/status.md`. Result: `2026-09-01-001` and
`2026-08-26-002` were both acted on 5 September and sat reading `status: open` for five days, so from
INDIA's side *work done* was indistinguishable from *order ignored* — and it re-sent the order.
**Acknowledging is part of doing.** Two places, every time: my `status.md` for me, and the inbox
item's `status:` + an outbox reply for them.

**Corollary on reading other agents' `status:` fields:** they are not reliable either, for the same
reason in reverse. Several items in `inbox/peter/` read `open` when my own record says closed. **Judge
an item by whether a reply exists in the outbox, not by its frontmatter.**

## Scar — INDIA's summary of my own finding was a version I had already retracted (2026-09-10)

The publish order asked me to publish *"the two retractions… once a 4-pole plug in a 3-pole jack
turned out to explain the silence by itself."* **I had killed that explanation myself the same day**
(`edf3a6f`): unplugging the mic left P11 at −89.1 dBFS against −25.0 on an empty P9, so the ~64 dB
difference is a property of the **ADC2 channel** and was never about the mic or the plug.

**Three lessons, in increasing order of usefulness.**

1. **A finding propagates faster than its retraction.** The plug explanation was quoted onward inside
   a day; the retraction was in my lane, unpublished. **When you retract something you have already
   told someone, the retraction is a message, not a commit.**
2. **Do not accept a summary of your own work as authoritative, however senior the sender.** The
   order was right about the gap and wrong about the content, and both halves needed answering.
   Publishing what I was asked to publish would have put a false claim on the shelf under my name.
3. **The underlying pattern, which cost three wrong explanations on one question:** each was a story
   about **the thing I had just changed** — the mic, the plug, the register I wrote — while the real
   difference sat in a channel property nobody had touched. **Suspect the constant, not just the
   variable.** And a two-way "either A or B" is only as good as the list; mine never considered that
   the thing on the end of the wire might not be the microphone.

## Fact — hostnames AND IPs are both weak identifiers in this fleet (2026-09-10)

One box, four naming problems. It **renames itself** from `scopenode` to `aeronode` two seconds into
every boot. A **different** machine (`100.64.0.6`, a Compute Module 5) answers to
`aeronode-385ba5`. On at least one team member's Mac, `ssh aeronode` is a local `~/.ssh/config`
alias pointing at *that* CM5. And the IP moves: the same machine-id has been at `100.64.0.1`,
`192.168.0.99` and `192.168.10.34` inside a week.

**Identify a bench by model string + machine-id, and state the address you actually used.** For this
box: `Raspberry Pi 5 Model B Rev 1.1`, machine-id `49cc4b68da3b4dfd9d10cc78207fe9eb`, with `i2c-2`
answering at `0x5c` (LPS22HB) and `0x68` (MPU-9250) as a confirming fingerprint.

**Same shape, different layer:** the ALSA card number is not stable either — I measured
`adauduplex` as card 1 on 8 Sep, JULIETT measured card 0 on 10 Sep, same box, same kernel. Two honest
measurements, two numbers. Address it as `hw:CARD=adauduplex,DEV=0`, never `hw:0,0`.

## Scar — a card that enumerates perfectly can have no hardware behind it (2026-09-10)

`[measured]` by JULIETT: nothing responded anywhere on `i2c-1` (full 0x08–0x77 scan) while the ALSA
card `adauduplex` continued to list in **both** `aplay -l` and `arecord -l`. Because no ASoC driver
exists for the ADAU1860, my DAI link uses an **in-tree dummy codec** — so the card enumerates with
the eval board unplugged.

Had a rate-lock probe run in that state, **every rate would have failed with `EIO` and the result
would have read exactly like "RP1 will not lock above 48 kHz"** — confident, plausible, entirely
false. This is the 2026-09-02 register scar one level up: not *a register that reads back correctly
does nothing*, but **a whole enumerated device that is not there.** Scan the control bus for the part
before believing any negative result about it, and use a known-good peer on another bus as the
control that proves your scan works.

## Fact — TWO different boards are called AeroNode (2026-09-10)

`[repo]` Do not read one's part list into the other. They share no barometer and no magnetometer.

| Name | Compute | Where |
|---|---|---|
| **AeroNode (CC93)** | Digi ConnectCore 93 / i.MX93 | `kicad/aeronode/` in lima — under git |
| **AeroNode (CM5)** | Raspberry Pi CM5108064B, 8 GB/64 GB | `~/aerosense/aeronode/aerosense/` on Peter's Mac — **NOT under git** |
| AeroNode Lite | same CM5, audio variant | `.../aerosense/aeronode-lite/`, read-only mirror at `kicad/aeronode-lite-audio/` |

`kicad/aeronode/doc/TELEMETRY_DATA_MODEL.md` is the **CC93** one: BMI088+ICM45686, MMC5983MA,
BMP390, I2C4/LPSPI8. The CM5 one is ICM45686 only, **RM3100** compass, **BMP581** baro, on
SPI3/SPI4/I2C1/UART0. A third board, `~/aerosense/aeronode/aeronode.kicad_sch` + `mcu.kicad_sch`,
is the older STM32H743 AeroNode.

**The unversioned tree is the standing risk.** The whole CM5 design lives in one directory on one
Mac with no remote. `aerosense/FMU.kicad_sch` is an empty 25 kB sheet — zero symbols `[measured]` —
so "there is an FMU" is a name, not a circuit.

## Fact — ArduPilot detects a Pi by PERIPHERAL BASE ADDRESS, not a model string (2026-09-10)

`[repo]` `libraries/AP_HAL_Linux/Util_RPI.cpp`, read at length. It reads
`/proc/device-tree/soc*/ranges` and switches on bytes 4-7: `0x10` = `RPI_5`, `0xfe000000` = Pi 4,
`0x3f000000` = Pi 2/3/Zero2. Anything else = `UNKNOWN_BOARD`, which is an `AP_HAL::panic` at startup
on any board with the RPi GPIO backend enabled.

Consequences worth keeping: **(a)** a CM5 should detect as `RPI_5` because it is the same BCM2712 —
predicted, not measured; the one-command test is `od -An -tx1 -N16 /proc/device-tree/soc*/ranges`.
**(b)** My `strncmp(d_name,"soc",4)`→`3` fix is therefore a **prerequisite for the CM5 too**, not a
Pi-5-only nicety — every 2712 kernel names the node `soc@107c000000`. Still unfiled upstream.

## Fact — `libraries/AP_HAL_Linux/hwdef/` is a real board-target mechanism (2026-09-10)

`[measured]` 26 boards in it. Same declarative language as the ChibiOS hwdefs — `IMU`, `COMPASS`,
`BARO`, `LINUX_SPIDEV`, `define`, `undef`, and `include ../<board>/hwdef.dat`. So a new Linux board
inherits from `pi5` in one line. Parser: `libraries/AP_HAL_Linux/hwdef/scripts/linux_hwdef.py`
(subclasses the shared generator; only `LINUX_SPIDEV` is handled locally).

**`LINUX_SPIDEV`'s BUS/SUBDEV are Linux spidev enumeration numbers, not SoC block numbers.** Read
them off `/dev/spidev*` on the real board; never infer them from `SPI3`/`SPI4` on a schematic.

Drivers confirmed present for the AeroNode CM5 parts `[measured]` at `fa7ffbd0a1`: ICM45686
(Invensensev3, WHO_AM_I 0xE9, cites TDK **DS-000563 rev 1.0** — a datasheet the KiCAD sessions never
found while chasing DS-000577), BMP581 (`AP_Baro_BMP581`, I2C 0x46/0x47), RM3100, ADS1115 (Linux
`AnalogIn_ADS1115`). **Absent: BME690 and BME680 entirely** — environmental is never ArduPilot's.

## Scar — a hwdef `include` inherits the other board's SENSORS, and `undef` will not remove them (2026-09-10)

`[measured]`. Writing an AeroNode target as `include ../pi5/hwdef.dat` produced a target that probed
the **pi5 dev rig's MPU-9250 on i2c-2:0x68** as `HAL_INS_PROBE1`, with the real ICM45686 appended as
PROBE2 — and with `INS_MAX_INSTANCES 1` the real sensor is the one that gets dropped. The AK8963 and
LPS22HB came too. `undef HAL_INS_DEFAULT` / `undef INS_MAX_INSTANCES` do nothing: the generator
**appends** device lines and `undef` only touches `define`s.

**`configure` printed `finished successfully` the whole time.** The evidence is in
`build/<board>/hwdef.h` — read `HAL_INS_PROBE_LIST`, `HAL_MAG_PROBE_LIST`, `HAL_BARO_PROBE_LIST`
after every hwdef change, never the exit code. Inherit `../linux/hwdef.dat` and re-add the board
lines by hand.

**Controls that prove it:** `nm -C` the binary — 27 `Invensensev3` symbols and **0**
`AP_InertialSensor_Invensense::`; `strings` shows `icm45686`/`rm3100` and no `mpu9250`/`icm20602`.

## Scar — my own instrument, twice in one session (2026-09-10)

1. **`ModuleNotFoundError: No module named 'em'`** on `dronecangen` reads like a missing dependency.
   It was not. `./waf configure` had been run **outside** `~/venv-ardupilot`, so waf cached
   `/usr/bin/python3` and never saw the venv's `empy`. **Activate the venv before `configure`, not
   just before the build.**
2. **"`FMU.kicad_sch` is an empty 25 kB sheet, zero symbols"** — technically true, materially false,
   and I said it to Peter while he was ruling on an architecture. It has **68 labels** and a drawn
   pin-level plan: STM32H753IIT6, LAN8742A RMII PHY, ICM42688 + BMI088, RM3100, BMP581, SPI2/SPI3
   with CS+DRDY, I2C4, UART7=telem1, SWD, PWM, heater. **`lib_id` count is not a content check on a
   KiCad sheet** — count labels and graphics too before calling anything empty.

## Fact — ArduPilot AHRS response time: the numbers that actually decide it (2026-09-10)

`[repo]` at `fa7ffbd0a1`. Full analysis in `docs/aeronode-ahrs-latency-architectures.md`.

- **The EKF fusion delay is NOT attitude lag.** EKF3 fuses at a delayed horizon —
  `maxTimeDelay_ms` = max(`EK3_HGT_DELAY` 60, `magDelay_ms` 60, `tasDelay_ms` 100, GPS lag ≤250) —
  then `calcOutputStates()`, called **outside** the `runUpdates` block
  (`AP_NavEKF3_core.cpp:714-717`), winds it forward to now on **every main loop**. Two decoupled
  rates: fusion at `min(loop_rate, 83 Hz)` (`EKF_TARGET_DT` = 12 ms), attitude output at the full
  loop rate.
- **`SCHEDULER_DEFAULT_LOOP_RATE` is 50 Hz for plane**, 400 for copter/sub
  (`AP_Scheduler.cpp:44-46`). So attitude is ~20 ms old at plane defaults on **any** platform.
- **Linux HAL priorities** (`Scheduler.cpp:26-32`, `Scheduler.h:15-16`): timer 15, UART 14, RCIN 13,
  **IMU bus poller 12, main loop 12**, IO 10. The sensor read sits below UART and level with the
  loop it feeds.
- **Jitter costs SAMPLES, not milliseconds.** The driver integrates with the *sensor's own* dt and
  applies coning per sample, so a late read is harmless. The two real doors are **FIFO overflow**
  (45686 holds 105 HiRes samples → a **13 ms deadline at 8 kHz**) and **`dtNow` clipping** to
  [0.5, 2.0]×`dtEkfAvg` (`AP_NavEKF3_Measurements.cpp:496`). Raising the loop rate to cut latency
  tightens both.
- **SPI is not a preference.** `fast_sampling` and 20-bit `highres_sampling` are both gated on
  `bus_type() == BUS_TYPE_SPI`. On I2C you silently get 1 kHz, 16-bit, no oversampling.
  `HAL_INS_HIGHRES_SAMPLE` defaults to 0 and **no Linux hwdef in the tree sets it** — ChibiOS boards
  only, by habit not by gate.
- **ArduPilot has no MAVLink IMU input**, so a companion computer can only consume a finished
  attitude at the ATTITUDE stream rate — which then dominates every other term in the budget.

## Fact — LSM6DSV in ArduPilot: SPI-only by type, and the variant matters (2026-09-10)

`[repo]` `libraries/AP_InertialSensor/AP_InertialSensor_LSM6DSV.{h,cpp}` at `179ae0ab03`, confirmed
upstream. Proposed as AeroNode's second IMU — see
`docs/aeronode-ahrs-latency-architectures.md` §6.

- **`probe()` takes `OwnPtr<AP_HAL::SPIDevice>`, not a generic `Device`.** SPI is a *type*
  constraint, not a preference. All six hwdefs using it declare `SPI:`. (Contrast the ICM-45686,
  where I2C compiles and silently degrades to 1 kHz / 16-bit / no oversampling.)
- **The hwdef keyword is `LSM6DSV`; the silicon must be a variant.** `check_whoami()` accepts
  WHO_AM_I **0x70** — LSM6DSV16X and LSM6DSV**32X**, split by CTRL8 bit 2 after reset — or
  **0x75**, LSM6DSK320X. **A plain LSM6DSV returns false.** Order 16X or 32X.
- **AMENDED 2026-11-05 — the island's part is the one variant that is NOT covered.** AeroImu 0.0.2
  carries an **LSM6DSV320X**, which reads WHO_AM_I **0x73** `[fetched: ST AN6119, 0Fh = 0b01110011]`
  — so `check_whoami()` returns false and ArduPilot never uses it. And **`LSM6DSK320X` is not a
  typo for it**: they are two different, both-active ST parts `[fetched: separate ST product pages
  + Mouser listings]`, and the driver's DSK320X `CTRL6` must-be-1 bit at `0x08` is real register
  knowledge about the other one. So "order 16X or 32X" above was advice given *before* the board
  existed; the board now has the 320X. **Do not patch `0x73` in blind** — the FS_XL/FS_G encodings
  and must-be bits would be asserted for untested silicon. Options and the one-command bench test
  (`whoami-spi.py <spidev> 0x0F`, expect 0x73) are in
  `linux/aeronode-cm5-image/README.md` §5. EKF3 does not need it: ICM-45686 alone, `EK3_IMU_MASK` 1.
- Rates: base 1000 Hz, fast sampling ×1..8 capped at **8000 Hz** via HAODR mode-1 — same ceiling as
  the ICM-45686, same `bus_type() == BUS_TYPE_SPI` gate. **16-bit only; no 20-bit HiRes path.**
- Driver defaults **2000 dps / 16 g** (4000 dps is in the register map but unused; 32 g is 32X-only)
  against the 45686's 4000 dps / 32 g. The lanes are not range-matched.
- **`drain_fifo()` is capped at 32 words per callback** (`LSM6DSV_FIFO_MAX_DRAIN_WORDS`, burst 16),
  and `poll_data()` calls it once — bounded worst-case execution time, better for a `SCHED_FIFO`
  thread than Invensense's unbounded `while (n_samples > 0)`. Net drain at 8 kHz ~240 words/ms, so
  catch-up is still fast.
- **`EK3_IMU_MASK` starts one EKF3 core per selected IMU** (`AP_NavEKF3.cpp:433`), up to 6. Two
  cores ≈ 2× EKF CPU/memory: cheap on 4 CM5 cores, the binding constraint on an H7.

**Do not over-read the navigator precedent.** BlueRobotics navigator (a **Linux** hwdef) declares
both `IMU Invensense SPI:icm20602` and `IMU LSM6DSV SPI:lsm6dsv` — but both point at
`LINUX_SPIDEV ... 1 2`, the **same bus and subdev** `[measured]`. They are board-revision alternates
resolved by probing, **not** a simultaneous two-IMU setup. It proves the driver runs on Linux/SPI and
nothing more.

## Fact — LSM6DSV16X FIFO depth, and the deadline it does NOT improve (2026-09-10)

`[fetched]` **ST DS13510 Rev 3** (LSM6DSV16X datasheet), read from the PDF, not a search summary.

- §6.12 p.44: "embeds **1.5 KB** of data in FIFO (up to 4.5 KB with the compression feature
  enabled)". §2 p.3: data "can be compressed **two or three times**". **The 4.5 KB on the feature
  page is the compressed-equivalent; the physical buffer is 1.5 KB.**
- **ArduPilot disables compression** — `FIFO_CTRL2 = 0x00` at
  `AP_InertialSensor_LSM6DSV.cpp:275` and `:501` `[measured]`. So 1.5 KB, one sample per word.
- Word = **7 bytes** (1 tag + 6 data), datasheet §6.12 and the driver's
  `static_assert(sizeof(RawFifoWord) == 7)`. `DIFF_FIFO_[8:0]` is 9 bits (Tables 77/78, pp.74-75),
  ceiling 511 words — above the ~219 the buffer holds, so consistent.
- Depth = 1.5 KB / 7 = **214-219 words**; temperature is not batched (`FIFO_CTRL3 = (odr<<4)|odr`),
  so words alternate gyro/accel → **~107-109 sample pairs**.

**The finding that matters, and it contradicted my expectation:** at 8 kHz that is a
**13.4-13.6 ms** overflow deadline against the ICM-45686's **13.1 ms** — **within 5% at every
rate.** A second IMU from a different vendor gives dissimilar **sensor** redundancy but **NOT
dissimilar timing redundancy**; on one Linux host a stall that overflows one lane overflows both.
Voting cannot cover a missed scheduling deadline — that is common-mode by construction. **Do not
count a second IMU as retiring the platform-jitter risk.** Mitigation that does work: run the lanes
at *different* backend rates (`INS_FAST_SAMPLE` is per-instance) — 2 kHz on one gives it ~54 ms.

**And the LSM6DSV lane fails silently.** Driver uses Continuous mode (`FIFO_CTRL4 = 0x06`), where
overrun overwrites the oldest samples and asserts `FIFO_OVR_IA` (§6.12.3). `read_fifo_status()` reads
both status bytes and uses **only** `DIFF_FIFO_8`; **`FIFO_OVR_IA` and `FIFO_FULL_IA` are never
examined anywhere in the driver** `[measured]`. No error count, no log, no reset. The Invensense lane
by contrast resets loudly (`need_reset` → the `MPU: temp reset` line). Worth an upstream patch.

## Scar — fast sampling is OFF by default on Linux, and nothing says so (2026-09-10)

`[repo]` `AP_InertialSensor.cpp:88-92`:

```c
#if defined(STM32H7) || defined(STM32F7)
#define MPU_FIFO_FASTSAMPLE_DEFAULT 1
#else
#define MPU_FIFO_FASTSAMPLE_DEFAULT 0
#endif
```

That sets `INS_GYRO_RATE`'s default. `get_fast_sampling_rate()` returns `1 << INS_GYRO_RATE`
(`AP_InertialSensor_Backend.h:363`), and the driver requires
`enable_fast_sampling(...) && get_fast_sampling_rate() > 1`
(`AP_InertialSensor_Invensensev3.cpp:849`).

**So on ANY Linux board the IMU runs at 1 kHz even with `INS_FAST_SAMPLE` = 1 and the part on SPI.**
An H7 comes up at 2 kHz. The only tell is the startup banner printing "normal" instead of "fast".
`INS_GYRO_RATE` values: 0:1kHz 1:2kHz 2:4kHz 3:8kHz.

**Packet sizes, both `static_assert`ed** (`AP_InertialSensor_Invensensev3.cpp:192-193`): `FIFOData`
**16 B**, `FIFODataHighRes` **20 B**. The 45686 FIFO is 2 KB `[repo]` — the driver's *comment*, not a
datasheet read. So HiRes costs ~20% of the overflow deadline: 105 samples instead of 128.

Deadlines, HiRes on: 1 kHz 105 ms | 2 kHz 53 ms | 4 kHz 26 ms | 8 kHz 13 ms.

`HAL_INS_HIGHRES_SAMPLE` is a **per-instance bitmask** (`enable_highres_sampling(accel_instance)`),
defaults 0, and **no Linux hwdef sets it** — but nothing gates it to ChibiOS. It needs only
`enable_highres_sampling()` and a SPI bus.

## Fact — AeroNode is SINGLE LANE by Peter's ruling (2026-09-10)

One ICM-45686, no second IMU, no EKF3 lane voting, `EK3_IMU_MASK` = 1. §7 of
`docs/aeronode-ahrs-latency-architectures.md` made this cheaper than it looks: a second IMU would
have given dissimilar *sensor* redundancy but **not** dissimilar *timing* redundancy, so it was never
going to cover the platform-jitter risk anyway.

Board target now sets `HAL_INS_HIGHRES_SAMPLE 1` and leaves the rate as the `INS_GYRO_RATE`
parameter. **Recommended `INS_GYRO_RATE = 2` (4 kHz)** — 4x oversampling margin against vibration
with a 26 ms deadline. **Do not set 3 (8 kHz) until the scheduling tail is measured** — on a single
lane an overrun is not a degraded lane, it is the AHRS. Commit `a2c4ac41a3` on branch
`aeronode-board`; patch at `linux/ardupilot-cm5/aeronode-board.patch`.


## Scar — I ruled out the two causes that turned out to be it (2026-09-11)

On 2026-09-04 I wrote that the Pi 5 IMU FIFO stall had "bus contention, intermittency and bus speed
all ruled out by measurement", concluded "**no software change explains it**", and sent the next
session **to the bench**. All three were wrong, and the handoff would have cost someone a day.

`[measured]` 2026-09-11, same box (machine-id `49cc4b68da3b4dfd9d10cc78207fe9eb`, at 192.168.0.99):

- Hardware is **fine**: `WHO_AM_I` 0x71; LPS22HB 0xb1 as the positive control; manual FIFO bursts of
  14-504 bytes all return valid data -- accel Z `0xf830` is -1 g, temperature non-zero and matching
  the register.
- ArduPilot's **configuration of the part is correct**: `FIFO_EN=0xf8`, `USER_CTRL=0x40`,
  `SMPLRT_DIV=0`, and `FIFO_COUNT` reads 14 -- it is filling.
- **`strace -e trace=ioctl` is what cracked it**: `I2C_RDWR` **4902 failures out of 28979 in 12 s
  (17%), all EREMOTEIO**. Bus is 400 kHz (`dtoverlay=i2c2-pi5,baudrate=400000`) shared by 0x68,
  0x5c and 0x0c. My own **single-device** loop at the same 1 kHz rate: **0% errors**.
- The canary: `AP_InertialSensor_Invensense.cpp:595` uses each FIFO sample's **temperature field**
  as a corruption detector, so `temp reset IMU[0] <ref> 0` means *the register reads fine but the
  FIFO sample carries 0*. Reading `FIFO_R_W` with nothing valid queued returns zeros -- I saw that
  at ~0.4% even in a clean loop.

**CORRECTION, same day.** The conclusion I drew from that -- "marginal 400 kHz shared-bus
signalling" -- was **also wrong**, and Peter's authorised 100 kHz test refuted it within the hour:

| Bus clock | transfers | EREMOTEIO | % | **per second** |
|---|---|---|---|---|
| 400 kHz | 28979 | 4902 | 17.0% | **409** |
| 100 kHz | 14326 | 4871 | 34.0% | **406** |

**Absolute failures barely moved across a 4x clock change; only the denominator did.** Marginal
signalling scales with clock. A fixed ~405/s does not. With `COMPASS_ENABLE 0` it drops to **69/s**,
so the `AK8963:probe_mpu9250` path is ~83% of it -- **but the IMU still stalls without the compass.**
Current hypothesis (`[assumed]`, not proven): perpetual FIFO overflow-and-reset, because 1 kHz x
14 B = 14 kB/s cannot be drained over a bus shared with the baro and compass. Box restored to
400 kHz, byte-identical to the backup.

**Lessons.** (1) "Ruled out by measurement" is only as good as the measurement -- I had never
counted the syscall return codes, which is where the answer was sitting the whole time.
(1b) **A percentage is not a rate.** I read "17%" as evidence for a hypothesis I already held and
published a causal claim on it, without checking whether the absolute count moved. Every number was
`[measured]`; the conclusion drawn from them was `[assumed]` and I failed to tag it.
(2) **Reach for `strace` earlier** when a driver "sees nothing" but the device answers by hand.
(3) A negative result from a *low-rate* manual probe does not rule out a fault that only appears
under *sustained multi-device* traffic -- match the instrument's duty cycle to the real one.
(4) Retract loudly: the handoff is amended in place, not quietly patched.

## Fact — the bench GNSS: u-blox M10 on ttyAMA0, 230400 baud, UBX-only (2026-09-11)

`[measured]` on the Pi 5 (machine-id `49cc4b68da3b4dfd9d10cc78207fe9eb`). Working: **3D fix, 18
satellites, 0.41 m horizontal accuracy**, 5 Hz NAV-PVT, all checksums OK.

| | |
|---|---|
| port | `/dev/ttyAMA0` (`dtoverlay=uart0-pi5`, GPIO14 TX / GPIO15 RX) — **not** `/dev/serial0`, which is the console |
| baud | **230400** |
| protocol | **UBX binary ONLY — emits no NMEA at all** |
| messages | NAV-PVT, NAV-DOP (30 each per 6 s), NAV-TIMEGPS, MON-HW, MON-IO |
| MON-VER | `ROM SPG 5.10`, hwVersion `000A0000`, **PROTVER 34.10** = u-blox **M10** generation |
| constellations | GPS, GLONASS, Galileo, BeiDou + SBAS, QZSS |

**The bench part is an M10 (probably the `SAM-M10Q-00B` in `~/aerosense/`), NOT the DAN-F10N the
AeroNode design specifies.** F10 is L1/L5 dual-band; M10 is L1 only. Do not validate an F10
assumption on this bench.

## Scar — I tested for one protocol and reported its absence as absence of data (2026-09-11)

Three stacked instrument faults cost an hour on "can you read gps":

1. **`timeout 3 head -c 4096 $PORT` discards what it read.** `head` buffers and is killed before
   flushing, so a live port reports **0 bytes**. Use `timeout N cat $PORT > file` -- `cat` writes
   through.
2. **I grepped only for NMEA (`$G`).** After the TX/RX swap my sweep captured **1962 bytes at
   230400** and I dismissed the line because `nmea=0`. The fix data was in that buffer. This module
   emits **no NMEA at all**; at the correct baud my test still said "nothing".
3. **A pull-down test cannot distinguish an actively driven line from a module-side pull-up**
   (10k beats the Pi's ~50k). I twice claimed "something is driving it" when the honest statement
   was "something on the module side is holding it high".

**What actually worked, and should have been first:** the kernel's own UART counters,
`/proc/tty/driver/ttyAMA` -> `rx: fe: brk:`. **Framing errors per byte identify the baud rate
directly** -- fe/rx was 0.3-0.6 at every wrong rate and exactly **0.000 at 230400**. Ask the driver
what it is seeing before writing a parser for what you expect to see.


## SCAR — the IMU was never broken, and I spent two sessions proving it was (2026-09-11)

**`MPU: temp reset IMU[0] <n> 0` is ONE line, printed ONCE at startup.** The complete console
output of a 45-second run is two lines. It is not a loop and ArduPilot does not halt.

`[measured]` on the stock `--board=pi5` build via MAVLink: `acc=(0,-43,-981)` — **accel Z is
-9.81 m/s2, gravity, stable sample after sample**; gyro ~0 with +/-1 jitter; VIBRATION 0.02 with
zero clipping; `SYS_STATUS` gyro/accel/mag/baro all **healthy**; ATTITUDE produced. The IMU works
and always did.

**The cause of the one message:** the first 56-byte FIFO burst after init has a corrupt tail --
sample 2 duplicates sample 1's accel with every other field zeroed, so its temperature reads 0 and
trips the driver's corruption canary. That is exactly what the driver's own comment documents, and
it **resets and recovers as designed**. Every later read is clean.

**How I got it wrong, five runs across two sessions:** I never once connected a GCS and asked the
running system whether it was healthy. Every time I read `head -5` of stdout, saw "reset", and
stopped. **ArduPilot on Linux does not print "Ready" to stdout -- it reports over MAVLink.**

Worse: on 2026-09-04 I ruled out bus contention, speed and intermittency *by measurement*. Those
measurements were correct. They were clean **because nothing was wrong** -- and I read a set of
clean results as a deepening mystery instead of as the answer.

**False conclusions this produced, each published and then retracted:** dead hardware -> go to the
bench; marginal 400 kHz signalling; FIFO overflow from 1 kHz sampling; the AK8963 is the culprit;
ArduPilot needs an IMU stub to run. All wrong.

**The instrument that settled it in one capture:** kernel i2c tracepoints,
`/sys/kernel/debug/tracing/events/i2c/`. Address, length, result **and the reply bytes** of every
transfer. It showed the MPU's own address ran **12727 transfers with 6 failures (0.0%)** -- the
~408/s EREMOTEIO I had chased for hours was ArduPilot **probing absent devices on i2c-1**, routine
and harmless.

**Rules.** (1) **Ask the running system what it thinks its own state is before theorising about why
it is broken.** Console output is not health. (2) A stream of clean "ruled out" results is evidence
there is nothing to find, not evidence the fault is exotic. (3) Reach for the kernel's own
tracepoints early -- they answer "what is actually on the wire" in one capture.

## Scar — a PDF text search is BLIND to a vector-drawn schematic (2026-09-21)

Peter asked whether the ADAU1372 was needed in the DVNC rig. He then told me **three times** that the
ADAU1860 evaluation board can run 3.3 V. I contradicted him twice, the second time calling my search
"exhaustive": a full-text regex for `3.3|3V3` across all 26 pages of UG-2017, the complete jumper
table, and the BOM. It returned the FTDI's LDO and nothing else, so I reported the 3.3 V option did
not exist.

**My instrument could not see the schematics.** `[measured]` pages 15–22 of UG-2017 carry **~140
characters of text each against 1,800–9,100 vector paths** — the schematic labels are drawn as glyph
outlines, so `get_text()` returns the page header and the figure caption and *nothing else*. I
searched nine schematic sheets, found nothing, and read that as confirmation. **A text search over a
schematic PDF is not a search; it is a blank page that answers every question with "no".**

He was right. `[fetched]` UG-2017 Figure 14 — the control ports have a **PCA9517DP** I2C buffer and
**six FXLP34P5X uni-directional translators** between a `3.3V` rail and `IOVDD`. The board does 3.3 V.
What it does not do is 3.3 V on the **serial audio** headers (P2/P3), which p.12 states are 1.8 V and
which have no translators — and that is the port the shared BCLK/FSYNC would use.

The generalisable rules:

- **Check whether the page has a text layer before trusting a text search of it.** `len(get_text())`
  against `len(get_drawings())` per page takes one line and would have caught this immediately. A
  sheet with 140 chars and 9,000 paths is a drawing, and a drawing must be **rendered and looked at**.
- **Third time is the instrument, not the human.** §3 says suspect your instrument when a result is
  surprising; the amendment is that a *person repeating themselves* is itself the surprising result.
  Peter was the more reliable instrument and I over-rode him twice with a broken one.
- **It failed toward the answer I expected**, exactly as §3 warns — I already believed the 1860 was
  1.8 V-only, and the blank pages agreed with me. The one that agrees too neatly is the one to doubt.
- Same session, a *second* correction of the same kind: I claimed the 1860's ADC2 was free from my own
  `status.md` summary rather than from the build spec, which allocates it to a third differential mic.
  **A summary of a source is not the source.** Clone the company repo and read the spec.

Detail: `docs/rig-logic-levels.md`. Vendor PDFs restore via `scripts/fetch-datasheets.sh`.
Related: [[rp1-i2s-clock-direction]], and the 2026-09-04 punctuation-parsing scar — this makes three
broken instruments in this lane.

## 2026-09-21 — An eval board's jumper list is not the device's limit

Checking whether the ICM-45686 could run at 1.8 V, the first figure I found was
"VDDIO selectable between 1.2 V, 1.8 V and 3.0 V." It is real and correctly quoted —
`[fetched]` AN-000484 Rev. 1.1 p.3 — but it is **the eval board's jumper options**.
The device's actual range is `[fetched]` DS-000489 Rev. 1.1 Table 3 p.20:
**VDDIO 1.08 / 1.8 / 3.6 V**.

Had I stopped at the first figure I would have told Peter 3.0 V was a ceiling and that
his 3V3 ruling on `kicad/imu-board/` was out of spec. Confident, traceable to a real
vendor PDF, and wrong.

**This is the same error I had just made in the other direction** on the ADAU1860: the
EVB's fixed `ADP1715ARMZ-1.8` is a board artifact, while the 1.2–1.8 V IOVDD ceiling
**is** silicon. One board fact read as a device limit; one device limit nearly read as a
board fact.

**Rule: an eval board tells you what its designers expected, never what the part permits.
Device limits come from the datasheet's electrical-characteristics and absolute-maximum
tables, and nothing else.** When a number arrives from a user guide, an app note, a
distributor page or a search summary, go and find it in those two tables before it enters
a decision. Related: [[verify-at-the-point-of-use]].

Second, smaller: the ICM-45686 datasheet's own page footers read **DS-000489**, while every
index and distributor calls it **DS-000577**. Cite what the document says about itself and
flag the mismatch — do not silently adopt the catalogue number.

## 2026-09-21 — "The datasheet doesn't have it" meant "I didn't grep for it"

I carried `[gap] the ADAU1860's IOVDD absolute maximum is not established` across **three**
documents, and told Peter twice I could not say whether 3.3 V on an 1860 pin degrades or
destroys. It is in **Table 10, p.16 of the abridged datasheet** — the file I had already
downloaded, extracted and grepped for *other* things in the same session:

> Power Supply (AVDD, **IOVDD**, HPVDD, HPVDD_L): **−0.3 V to +1.98 V**
> Digital Input Voltage (Signal Pins): −0.3 V to **IOVDD + 0.3 V**

At IOVDD 1.8 V that is **2.1 V max on any digital pin**; 3.3 V is 1.2 V over and kills the part.
That is not a footnote — it is the number the whole level-shifter decision rests on, and it
would have changed the urgency of every message I wrote about the 3.3 V-into-`SDATAI` hazard.

**What actually went wrong:** I searched the HRM for "absolute maximum", got zero hits, and
generalised one document's absence into "not established" — without running the same grep against
the datasheet sitting in the same directory. **A negative result from one document is a fact about
that document, never about the question.**

**Rule: before writing `[gap]`, grep every artefact already on disk for the term, and say which
documents you checked.** A `[gap]` that names its search is honest; one that doesn't is a guess
wearing a tag. Related: [[eval-board-jumper-list-is-not-the-device-limit]] — both are the same
failure, trusting the first document to hand instead of the right one.

**Second lesson, same day: "unreachable" also meant "I tried three URLs."** I declared UG-2257
unmirrored after three guesses at one mirror. Peter said try again. A search found the canonical
ADI URL; curl and WebFetch both fail on analog.com, **but the browser pane fetched it fine** — the
site serves a save dialog rather than a page, which my own notes had already recorded for the 1372
datasheet and I did not connect. **Exhaust your instruments before reporting a blocker: curl,
WebFetch, the browser, and the possibility that the file is already on disk.**

---

## Scar — a `cc:` line is a claim, not a delivery. Verify per RECIPIENT, not per push. (2026-09-22)

Peter asked whether the level-shifter ruling had *reached the team*. I had pushed three memos and
verified each push at full length, as the protocol demands. **All three reached only one of their two
named recipients.**

Every one carried `cc: chris/INDIA` in its frontmatter and every one was copied into `inbox/john/`
only. **`inbox/chris/` never received them.** `[measured]` on a fresh clone of the remote.

**Why the push check cannot catch this, which is the whole lesson.** The commit landed perfectly. The
SHA matched all forty characters. The file was exactly where I put it — *in one of the two places it
belonged.* **A push receipt proves the bytes arrived; it says nothing about whether they arrived
everywhere they were addressed.** I had been treating a verified push as a verified delivery, and
those are different claims about different things.

**The frontmatter is the trap.** Writing `cc: chris/INDIA` *feels* like addressing a message, because
that is what a `cc:` field means in every mail client anyone has used. Here it is a **comment**. The
delivery is a `cp` into a directory, and nothing in the repo reconciles the two — no tool, no hook, no
check. A `to:`/`cc:` line that does not match the inboxes the file actually sits in is not an error,
it is a lie that validates.

**The cost was not cosmetic.** JULIETT's `2026-09-21-003` asked for Decision 1 as a **joint
Chris-and-Peter call**. Peter ruled it, I relayed the ruling to John alone, and **Chris's agent was a
named party to a decision it had never been shown** — while also being the one at the bench, where the
TXS0108E lead-length caution was the operationally useful part.

**And it was not even a habit I lacked.** `inbox/chris/2026-09-10-004` and `2026-09-18-001` were
delivered correctly. I had the habit and dropped it on the three messages that happened to carry a
decision. **A discipline that holds except under load is not a discipline.**

### The rule

**Delivery verification is `ls` on the recipient's inbox, on a fresh clone, once per named
recipient** — one check per name in `to:` *and* `cc:`. Not once per message, and never "my push
landed."

```bash
git clone --depth 1 <sync> /tmp/v
for r in <every name in to: and cc:>; do ls -1 /tmp/v/inbox/$r/ | grep <slug>; done
```

**Generalises past this repo:** whenever a document *names* its recipients and a *separate* action
delivers it, those two can disagree silently, and the one that feels like the delivery is the one that
isn't. Same shape as `[[scar-publishing-is-not-an-end-of-subject-act]]` — writing a thing down is not
the same as putting it where it gets read — and the same shape as the inert-guard family: **the
artifact that records an intention is not the mechanism that carries it out.** Check the mechanism.

## 2026-09-22 — Read page 1 of the manual you are quoting

I spent a day citing UG-2257 — frame-clock modes, slot routing, clock-source selects — and
recommended the ADAU1787 as the product codec on a 42-ball 0.35 mm WLCSP, flagging the package
as a risk I could see no way around. **Peter found the ADAU1861: the same silicon in a 64-lead
side-solderable LFCSP.**

Its existence is on **page 1 of UG-2257**: *"includes ADAU1860 and ADAU1861."* I had that file
open all day and read past the sentence naming the part that solved the problem.

**Two compounding errors, and the second is the instructive one:**

1. I recommended the 1787 for its **DSP** — one turn after establishing that ANC runs in the
   earcups and the board therefore needs no DSP. **I optimised for a requirement my own previous
   answer had deleted.** When a decision changes the requirements, re-derive the choice from the
   new requirements, don't carry the old shortlist forward.
2. I searched UG-2257 for *mechanisms* and never once read its **scope**. A reference manual's
   first page says which parts it covers — that is a menu of alternatives, free, and I skipped it.

**Rule: when a part looks like the only option and its package or price is painful, read the
family scope on page 1 of its reference manual before accepting the constraint.** ADI (and TI,
and everyone) ships the same die in several packages and temperature grades; the manual tells you
so in its first paragraph. Related: [[eval-board-jumper-list-is-not-the-device-limit]] and
[[negative-result-from-one-document]] — all three are the same failure, trusting the document I
happened to open over the one that answers the question.

Bonus the same page paid for: the 1861's PLL takes 30 kHz–36 MHz and so locks to a 48 kHz FSYNC
directly, closing an MCLK-distribution item the 1372's 8–27 MHz PLL had forced.

## 2026-10-21 · A distributor's one-line description is not a pinout
DigiKey lists the Triad SP-74 as "80 CT / 8 ohm". Triad's own drawing shows **no centre tap**. I
reasoned about "the CT option" for a whole turn and drew a 7-pin centre-tap symbol on the strength
of that listing. Before drawing a symbol, or arguing from a winding's topology, read the
manufacturer's drawing. Distributor text counts as `[fetched]` only for price, stock and lead
time. And Triad pinouts are drawn, not text: render the page and read it as an image.

## 2026-10-23 · Konnect footprint + KiCad-on-macOS scars (audio board layout)
- **`create_footprint` reads `body_height` as the body's Y size, not its Z height,** and sizes the courtyard from
  the pad envelope. Result: fab outlines like a 12x0.85 mm bar under a 12x12 part, and courtyards smaller than
  the body wherever the body overhangs the pads (transformers, the mic). Fix with `set_footprint_graphics`
  replace on F.Fab and F.CrtYd, and render with `kicad-cli fp export svg` + `qlmanage -t` to look before trusting.
- **"Operation not permitted" from KiCad on files in ~/Documents is TCC, not file perms.** The tell `[measured]`:
  files carrying `com.apple.macl` (ones the user opened by hand) open; siblings without it are refused. Fix is the
  user's: Privacy & Security -> Files and Folders -> KiCad -> Documents. Never launch KiCad from the agent shell.
- **`add_board_outline` and other file-mode tools refuse while the project manager runs** (GetOpenDocuments ->
  AS_UNHANDLED) even with no PCB editor open. Quit KiCad (osascript quit can hang on a dialog; it did exit).
- **Konnect is a project `.mcp.json` server**, so the agent can't re-dial it (`reconnect_session_connector` only
  covers claude.ai connectors). When it drops, the user restarts the session.
- **Konnect's `update_pcb_from_schematic` drops every footprint `(model …)` block** `[measured]` 2026-10-26: 0 of 120
  audio-board and 0 of 102 cup-board footprints had 3D models after sync, though the stock libraries carry them.
  Restore with `kicad/lib/3d/restore_models.py` (KiCad closed, KiCad's bundled Python) after every sync.
  The `lib_footprint_mismatch` warnings are NOT caused by this (they stayed at 116 after the restore) — cause unknown.
- **Konnect IPC refuses non-90° rotation** of footprints with rounded-rect pads. For angled placement (ring boards),
  quit KiCad and set orientation with pcbnew (`kicad/cup-board/doc/apply_placement.py`).
- **Stock KiCad 10 footprints can reference 3D files KiCad 10 doesn't ship** `[measured]` 2026-10-26: QFN-32 5x5 EP3.6
  and Oscillator SiT PQFN 3.2x2.5 -> bare pads in renders. Check every `(model` path resolves, not just that one exists.
  pcbnew gotcha: `f.Models()` iteration yields copies; edit = clone fields into new FP_3DMODEL, clear, push_back.
- **Freerouting needs plane fanout done first, and plane layers kept as planes** `[measured]` 2026-10-26: fanout script
  took audio unconnected 64 -> 19. A routable plane layer gets split by tracks; a net whose class width exceeds its
  fine-pitch pin widths gets zero routes (silently). Autorouted spaghetti still fails switch-loop / analog hand-checks.
- **Freerouting plateaus (~18 left) on dense boards and is deterministic — re-runs don't help** `[measured]` 2026-10-26.
  Finish with the A* finisher `kicad/audio-board/doc/route/maze.py` (DRC report in, routes out). When a pin is boxed in,
  move the blocking decap rather than fighting the router. SES import re-adds protected wiring: always de-dupe (2 µm tol).
- **Rip-up router traps** `[measured]` 2026-10-27 (cup board): (1) one rip-up per pass that exits before re-routing the
  victims ping-pongs forever (VIN_CUP <-> A2B_VOUT2, 40 passes, 11 -> 39 unconnected) — route everything first, then rip
  once, and weight repeat victims (RIP_HIST); (2) line-of-sight smoothing must check soft copper too, or straightened
  segments short unripped nets; (3) cascading dangling-stub strip eats whole branches — remove only the flagged vias.
  Cause of the thrash was placement (decaps parked on U6's pin face, VIN cap 32 mm away) — check that before tuning.
- **Maze finisher "no path" can be a lie, and plane-net tracks become walls** `[measured]` 2026-10-27 (cup 72/38):
  (1) A* had a fixed 3 M-cell search budget that silently returned "no path" — a 60 mm run round a ring on 3 layers
  needs ~15 M (`MAZE_BUDGET=15e6`, ~2 min, 0.7 GB); it now prints when the budget is hit. (2) When a plane pad's fanout is
  ripped, maze routes that pad to the plane as an ordinary track (one went 50 mm round the edge on B.Cu) — plane copper
  is hard to rip-up, so it walls off the corridor. Re-seat plane pads with `fanout.py FANOUT_PADS=REF.PAD` and feed maze a
  report filtered to the signal nets. (3) Signal tracks on the plane layer enclose pockets the zone filler drops as
  islands (DRC shows Zone<->Zone unconnected) — keep inner-layer cost high (LAYER_COST=3).
  (4) When one area won't close, rip every net near the stuck pins and route the critical nets FIRST (MAZE_FIRST).
- **Maze needs the board's FULL aircraft net list, and rip-up can wreck routes you wanted kept** `[measured]` 2026-10-29
  (audio J3/J4 change): passing a partial AIRCRAFT_NETS routed SPK_L_B at 0.13 mm next to Aircraft-class copper -> 14
  clearance errors. Read the list from `.kicad_pro` (netclass_patterns, class Aircraft) every time. When a rip-up
  displaces a good route, restore it with `kicad/lib/route/copynet.py <old.kicad_pcb> <board> NET` instead of letting
  maze re-invent it (maze stair-stepped ELEC_LO 118 mm through the T2/T3 area). For interleaved pin pairs on stacked
  connectors (LO above HI at both ends) one crossing is forced — hand-route it on two layers, then lock it.

## Fact — AeroNode rev 0.0.2 driver coverage, and my two patches still unlanded (2026-11-05)

`[measured]` against `ArduPilot/ardupilot` **master on 2026-11-05**, read from the driver source.
Full matrix + run order: `linux/aeronode-cm5-image/README.md`.

**Everything EKF3 needs is already supported** — this was the question that decided whether the
native-CM5 image was a weekend or a month. It is a weekend.

| Part | Driver | Note |
|---|---|---|
| ICM-45686 | `AP_InertialSensor_Invensensev3` | 0xE9, 20-bit HiRes, SPI-gated |
| MMC5983MA | `AP_Compass_MMC5xx3` | ID 0x30; `AP_Compass.cpp:1248`'s own comment names MMC5983MA |
| BMP581 | `AP_Baro_BMP581` | I2C 0x46/0x47 |
| **BMP390** | **`AP_Baro_BMP388`** | the 388 driver knows `BMP390_ID 0x60` beside `BMP388_ID 0x50` (`AP_Baro_BMP388.cpp:28-29`). Do not go looking for an `AP_Baro_BMP390` — there isn't one |
| DAN-F10N | `AP_GPS_UBLOX` | generic UBX fine. Driver has an **F9** branch, **no F10** one, so F10-specific config isn't applied |
| LSM6DSV320X | — | **not covered**, see the amended LSM6DSV section above |
| BME690 | — | absent entirely; read it from Linux |

**Both September patches are STILL REQUIRED** `[measured 2026-11-05]`: master still has
`strncmp(entry->d_name, "soc", 4)` at `Util_RPI.cpp:62`, and `hwdef/` still has **no `pi5` board**
(26 dirs, listed). So the soc-node fix remains a *prerequisite*, not a nicety — a BCM2712 kernel
names the node `soc@107c000000`, detection falls to `UNKNOWN_BOARD`, and `GPIO_RPI::init()` panics.
Carried as `linux/aeronode-cm5-image/patches/000{1,2}`. **Still unfiled upstream** — filing them is
owed work, and the longer it waits the more re-rolling it needs.

**`[correction]` to our own record:** `docs/aeronode-cm5-software-rev1.md` (2026-09-10) says the CM5
AeroNode is **RM3100 + BMP581**, read from the unversioned `~/aerosense/aeronode/aerosense/` tree.
The rev 0.0.2 **vendor schematic** is **MMC5983MA + BMP390 + BMP581**. Follow the schematic. This is
the second time that unversioned tree has given a stale answer — it is still the standing risk.

**`[measured]` 2026-11-17, the first real Blackbox board (HW 0.0.2 rev 1, BB1 seated on it):** the
barometer fitted is a **BMP581 at I2C-1 0x46** — CHIP_ID (reg 0x01) reads **0x50**, REV_ID 0x32. Nothing
answers at **0x76**, where ALFA's `bb_check.py` expects a BMP390 (it takes 0x76 from the schematic's sheet-7
I2C map). Peter ruled it the same day: "the bmp390 is a bmp581". So a schematic listing *both* parts is
not proof both are fitted — read the chip IDs on the real board. The schematic (page 7, U9) draws ONE
footprint "BMP390, pin compatible with BMP581" and lists both addresses (0x76 / 0x46): a checker must
accept either. Same run: unknown 0x34 answers (J9 audio expansion? the sheet says "address unknown").

**`[measured]` 2026-11-17, magnetometer:** Peter ruled the fitted part **is the MMC5983MA** (U10). It does not
answer at **0x30** (5 retries of Product ID reg 0x2F → EREMOTEIO); a read-only scan of I2C-1 shows only
0x2D 0x34 0x46 0x48 0x6B 0x77, so the bus and the 3.3 V feeding its neighbours are fine. The schematic is
right `[repo: Downloads/Schematic for Aeronode HW ver 0.0.2 rev 1.PDF p.7, rendered and read]`: pin 4 CS/mode
is tied to Vdd_IO ("this selects I2C"), VDD (2) and VDDIO (13) on 3.3 V filtered through Cp3, CAP C51 10 µF —
matching the datasheet `[fetched: MEMSIC MMC5983MA Rev A p.9: CS "Tie to VDDIO for I²C", address 0110000]`.
So the fault is physical and CANNOT-MEASURE-FROM-A-DESK: fitted? orientation (pin-1 dot)? LGA solder? 3.3 V at
C50? CS high at pin 4? Route to Peter's bench.

**`[measured]` 2026-11-17, flexes connected (AeroImu J11, AeroVault J12):** both alive on the first try.
ICM-45686 on SPI0: |a| 1.005 g (z +1.001, board flat), gyro −1.3/−1.3/−0.1 dps, 25.9 °C. AeroVault on SPI3:
JEDEC **EF AA 21 = Winbond W25N01GV** (1 Gbit SPI NAND) — the footprint-compatible part, NOT the drawn
Foresee/Lexar F35SQ (MID 0xCD). Anything that writes the flash must use the W25N command set. bb_check
then: 14 pass, 2 warn, 2 fail — the fails are the baro-address script issue and the silent MMC5983MA.

**AeroMic on the Blackbox board — overlay hazard** `[repo: schematic p.3, rendered]`: J9 I2S is the standard
map, GPIO18 SCLK / 19 WS / 20 SDI0 / 21 SDO0. But **GPIO16 = GPIO_RLY_SPKR, GPIO17 = GPIO_RLY_MIC (relays)**.
`googlevoicehat-soundcard` (the usual "I2S MEMS mic on a Pi" overlay) drives GPIO16 as an output
(`sdmode-gpios`, `[measured]` by dtc on BB1) — **never use it here**. `adau7002-simple` claims no GPIOs, targets
`i2s_clk_producer` with the CM5 as clock master, format i2s — the clean choice for the DMM-4026 I2S mic.
As of 2026-11-17 BB1 has no capture card (only snd-aloop) and GPIO18-21 unconfigured, so the mic is invisible.

**`[measured]` 2026-11-17, AeroMic ALIVE on BB1** (Peter's go-ahead): appended under `[all]` in
`/boot/firmware/config.txt` (outside the aeronode-managed block; backup `config.txt.pre-aeromic`):
`dtoverlay=adau7002-simple,card-name=aeromic`. After reboot: card 0 `aeromic`, GPIO18-21 = I2S0_SCLK/WS/SDI0/
SDO0, GPIO16/17 untouched. `arecord -D hw:CARD=aeromic,DEV=0 -c 2 -f S32_LE -r 48000`: **left (ch0) carries
the mic** (24-bit left-justified, low byte 0), right is constant 0x1. Start-up offset settles in ~0.75 s;
then room noise −47…−55 dBFS RMS (DC-blocked), peaks −36…−46. Not yet done: a positive control (speech/tap)
and a sensitivity check against the DMM-4026 data sheet.
**Positive control done, same day:** 5 s clip while Peter made sound. Full-band (DC-blocked) it rose only
+2…+8 dB — sub-200 Hz drift masks it; **judge this mic above ~200 Hz.** There the quiet baseline is steady
(−60.6…−63.0 dBFS per 0.25 s) and the sound clip rises +5…+18 dB in a syllable-like on/off pattern, falling
back in the gaps; zero-crossing frequency 10.6 kHz → 6.0 kHz. PASS: the mic hears. Sensitivity vs data sheet
still unchecked. WAVs in `scratch-aeromic/` (untracked, not committed).

**SCAR — the thermal-island heater is violent** `[measured]` 2026-11-17 on BB1 (Peter asked: IMU board to 35 C).
heater_control = GPIO12 → J11.5 → heater on the AeroImu thermal island, fed from Vcm5, NO hardware cut-off.
Run 1 at 60 % max duty: ~1.8 s of heater-on took the ICM-45686 from **26.2 to 38.3 C in 5 s**, and it kept
rising to **40.75 C after the heater was off** — the 40 C software hard cut fired (guard proven live). Island
≈ 0.6–0.8 J/K, cools with τ ≈ 20–30 s. Holding +9 C needs only **~3 % duty**. Run 2 (`scripts/heat_imu.py`:
max 10 %, KP 0.02, KI 0.0005 within ±3 C, 0.5 s window, rate guard 1 C/s) reached 34.9 C in 58 s with no
overshoot and held **34.8–35.2 C at ~3 % duty**. Run it only as a transient unit with
`-p RuntimeMaxSec=… -p "ExecStopPost=/usr/bin/pinctrl set 12 op dl"` (off-path proven: ExecStopPost fires
on a RuntimeMaxSec kill). **Any heater code: duty cap ≤ 10 %, hard cut on the IMU temp, never a long pulse.**

**Blackbox board charger + USB-C (J1)** `[measured]` regs on BB1 2026-11-17 + `[repo]` schematic p.1 + `[fetched]`
TI SLUSDV2C (Jun 2026). BQ25798 strapped 2S (PROG R13 6k04, 1.5 MHz), ILIM_HIZ 100k/100k ≈ 1.8 A input limit.
Nothing on BB1 writes it, so it sits in **default mode, watchdog expired**: VSYSMIN 7.0 V, VREG 8.40 V, ICHG 1.0 A,
EN_CHG 1, EN_OTG 0, ADC off, no faults, TS in range, VBATOTG_LOW 0. **VSYS needs no setup.** J1 is
**host** (dwc2 dr_mode=host — Peter: keep it host) and its VBUS connects ONLY to the charger, so 5 V out of J1 =
charger OTG: `WATCHDOG`=0 (REG10 0x85→0x80) then `EN_OTG`=1 (REG12 bit 6); VOTG 5.00 V / IOTG 0x4B ≈ 3 A at
default. EN_OTG is reset by watchdog expiry, REG_RST and POR → a boot service must re-apply it. **Hazard:** J1's
CC1/CC2 go only via R3/R5 0R to the CM5's CC pins — no Rp, no CC/DRP controller, so it advertises as a power
SINK. With OTG on, plugging a USB-C charger/laptop into J1 back-drives VBUS against the OTG output (the BQ only
blocks OTG start when VBUS is already present; OTG_OVP won't trip at ~5 V). Next rev: a DRP CC controller.
**OTG proven live** 2026-11-17 (Peter plugged a USB-serial converter into J1): wrote REG10=0x80 (watchdog off),
REG0D=0x0D (IOTG 520 mA), REG12=0x40 (EN_OTG), REG2E bit7 (ADC on). VBUS_STAT 7 (OTG), VBUS 4948 mV, IBUS
−26 mA, no faults. Converter = **CH340 1a86:7522** on bus 1 (dwc2, `1000480000.usb`) → `/dev/ttyUSB0`
(`/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`). Not persistent: no boot service — a power cycle drops it.

**CO channel** `[repo: schematic p.6, rendered]` `[measured]` 2026-11-17: TGS5141-P00 (S6, ~2 nA/ppm) between Gnd
and the − input of TLV8811 U7; + input grounded; R36 1 MΩ ∥ C44 1 µF (τ 1 s); single 3.3 V supply → ADS1115
AIN0 (0x48). So **≈2 mV/ppm and clean air sits AT the 0 V rail** — wrong-direction current or negative offset
also reads exactly 0 V; "0 V" cannot tell clean air from dead. Two early bb_check runs read 0.0000 V; 11 min
after a later boot both bb_check and a ±0.256 V single-shot read read +6.4…+9.4 mV, drifting down (settling?).
Next rev: lift the + input a few tens of mV so 0 ppm sits off the rail. **Sensor polarity not proven** —
needs a CO stimulus (a blown-out match) and a live read.
Live watch 2026-11-17 (`scripts/co_watch.py`, auto-ranging, logs /tmp/co_watch.log): ~2 min of clean data at
6–11 mV, ±3 mV of baseline, no stimulus captured. Peter paused it to bring "a real fire" — CO response still
UNPROVEN.
**`[measured]` 2026-11-19 ~07:2xZ — CO RESPONSE PROVEN, polarity correct.** `co_watch.py 300` on BB1, Peter held a
blown-out match near the TGS5141 outdoors: baseline (0–120 s) 4.0–5.7 mV, sd 1.6 mV; at 120–135 s mean 17.2 mV,
**peak 32.66 mV at 128 s (+27.7 mV ≈ 17× noise)**, back to +0.1 mV by 138.8 s (~10 s recovery). Nominal 2 mV/ppm ->
~16 ppm peak, but uncalibrated and TGS5141 sensitivity spreads ~2:1, so ~11–27 ppm. Cross-sensitive to H2/ethanol:
proves the chain responds to combustion gas in the right sense, NOT a calibrated CO number. The rail issue stays
(0 ppm sits ~5 mV above 0 V here, but a negative offset would still clip at 0 V): next rev lift the + input.

**After the MMC5983MA rework** `[measured]` 2026-11-17 (Peter: "we reworked the magnetometer"): I2C-1 answers
ONLY 0x48 (ADS1115) and 0x77 (BME690), 5/5 scans. Still silent: 0x30 MMC5983MA. Newly silent: 0x46 BMP581,
0x2D LP5815, 0x6B BQ25798, 0x34 (unknown). SDA/SCL idle high (pulled up); IMU, flash, GNSS, CM5 5 V 5.01 V all
PASS; IMU z −0.994 g (board upside down). Charger silent ⇒ either the board is now fed without J2/VBUS, or
something on the bus branch/rails changed. U9 (BMP581) and U10 sit on the same sheet, each on Vcm3.3 via its
own ferrite (Cp2 / Cp3) — check rework collateral there. OPEN: how the board is powered now.
Retry after a fresh boot (up 3 min), same day: identical — only 0x48 0x77, 0x30 EREMOTEIO. A reboot doesn't change it.
Next boot (Peter changed something between): 0x2D 0x34 0x46 0x48 0x6B 0x77 back (3/3 scans), charger no faults →
the 4-device loss was power/setup, NOT rework damage. **MMC5983MA still silent after rework** (5× EREMOTEIO);
bb_check 14 pass, 2 warn, 2 fail (baro-address script issue + MMC).

**LP5815 LED driver (U8, 0x2D) driven** `[measured]` 2026-11-17, `[fetched]` TI SNVSCP2B (Sep 2026) §8.2.3.2:
one RGB LED, LED3 IN-S126TBSRGB — out0 red, out1 green, out2 blue `[repo: schematic p.6]`. Sequence: 00h←03h
(CHIP_EN + INSTABLINK_DIS), 01h←00h (25.5 mA range), 14h-16h←50h (~8 mA), 02h←07h, 04h←00h (manual), 0Fh←55h
(UPDATE_CMD, required), PWM in 18h-1Ah. All readbacks correct; FLAG 40h = 01h = POR only (normal). Ran R/G/B ×3 +
white ×3, left in standby (CHIP_EN 0). `scripts/led_test.py`. **Peter: red and green light, BLUE DOES NOT.**
LED3 is common-anode on **Vcm3.3** `[repo]`; Vf ≈ 2 V R / 3 V G / 3 V B at 20 mA `[fetched: DigiKey, Dasenic
listings — not the Inolux PDF]`; LP5815 headroom ≤ 275 mV `[fetched]`. Green works at a similar Vf, so headroom
alone is unlikely. Ran blue-only at 1.6 / 8 / 20 mA (4 s each) to separate headroom (would glow at low
current) from open die/joint/trace (dark at all currents) — result: see Peter's report. Schematic note: this
side-view LED "is easily damaged when it sticks past edge" of the board.

**Battery reading** `[measured]` 2026-11-18 via BQ25798 one-shot ADC (REG2E←C0h; VBAT 3Bh 1 mV, IBAT 33h signed
1 mA, VSYS 3Dh, VBUS 35h, TS 3Fh ×0.0977 %, TDIE 41h ×0.5 °C — `[fetched]` SLUSDV2C): **VBAT 5.72–5.74 V = 2.87
V/cell, effectively empty for a 2S Li-ion.** VBUS 4.55 V present, PG 1, **VINDPM_STAT 1** (the USB-C source sags
to the 4.5 V VINDPM limit — it is weak). CHG_STAT 2 = pre-charge at IPRECHG 120 mA until VBAT > VBAT_LOWV
(code 3 = 71.4 % of 8.4 V ≈ 6.0 V). IBAT reads 0 because EN_IBAT (REG14 b5) = 0. TS 58.6 % → NTC ≈ 9.8 kΩ ≈ 25 °C
(R9 5k23 / R11 30k1, β assumed). VSYS 5.69 V. A near-empty pack + weak USB source may explain the earlier
"devices vanish / unexplained reboots" — not proven.
Better USB-C charger (same day): VBUS 5.19–5.20 V, IBUS 0.70–0.82 A, no VINDPM/IINDPM limiting, **VSYS 7.35 V
(now regulated above VSYSMIN — the board runs off USB, not the pack)**, die 41 °C, no faults. Still pre-charge
(120 mA); VBAT 5.68 V — not yet seen rising (−40 mV vs the weak-source reading). Recheck that VBAT climbs.

**SCAR — two remote-process mistakes in one hour (2026-11-17):**
1. **A live readout that prints to an `ssh -t` terminal can freeze the measurement**: when the terminal tab
   stopped draining, `print()` blocked and sampling stopped at 14 s while the user was making smoke. Run the
   sampler detached (`setsid nohup … </dev/null >/dev/null 2>&1 &`), write only to a log, and let the viewer
   `tail -f` the log — a stalled viewer then cannot stall the instrument.
2. **`pkill -f NAME` / `pgrep -f NAME` sent over ssh match their own `bash -c '…NAME…'` command line**: pkill
   killed its own shell (exit 255, nothing restarted); an `until ! pgrep -f …` wait never ended. Use a bracket
   pattern (`pgrep -f "[c]o_watch.py"`) or a pidfile.

**Carry only patches, never whole bundles.** `upstream-pr/pi5-board-with-sensors.patch` is TWO
commits, and the second declares the dev rig's MPU-9250/AK8963/LPS22HB. Copying that bundle into a
new board's image would re-import the exact scar the hwdef is written to avoid. I carried the
standalone `0002` and grepped it for sensor lines before committing.

## Fact — what "EKF data out of ArduPilot" actually means (2026-11-05)

`[repo]` There is **no dump-the-EKF MAVLink message.** EKF3 state leaves as `ATTITUDE`,
`GLOBAL_POSITION_INT`, `LOCAL_POSITION_NED`, `EKF_STATUS_REPORT` (health flags + variances) and
`VFR_HUD`. Bridge + tests: `linux/aeronode-cm5-image/aerosync/`.

- **The EKF fusion horizon is NOT attitude lag** — the counter-intuitive one. `calcOutputStates()`
  runs **outside** the `runUpdates` block (`AP_NavEKF3_core.cpp:714-717`) and winds the delayed
  solution forward to now **every main loop**. Real attitude age is one loop period, and
  `SCHEDULER_DEFAULT_LOOP_RATE` is **50 Hz for plane** → **~20 ms**, before any link latency.
- `EKF_STATUS_REPORT.flags` bit **10 = `uninitialized`**. An uninitialised EKF still publishes
  plausible attitude numbers, so that bit must invalidate the frame — not be averaged into it. This
  is the same failure class as F01's DSMA EKF being only 1.0% valid; **EKF3 is a different
  estimator and that 1.0% figure does not transfer to it.**
- **ArduPilot has no MAVLink IMU *input*.** A companion computer can only consume a finished
  attitude, never feed samples in. Kills any "let the Pi do the fusion and tell ArduPilot" design.

**`[gap]` AeroSync's transport is recorded NOWHERE in this repo** — grepped every tracked file for
`aerosync` beside BLE/GATT/UDP/WebSocket: zero hits. Memory says App V1 does BLE 5.2, which MAVLink
does not speak. The bridge therefore emits JSON to stdout or UDP and is meant to be re-pointed.
**Ask Peter before building a BLE writer against a guessed GATT profile.**

## Fact — how to reach BB1, and three transfer scars (2026-11-18)

`[measured]` BB1 = `Raspberry Pi Compute Module 5 Rev 1.0`, hostname `bb1`, machine-id
`ad0a0fbd3b064476a100b652968a1ed0`, Debian 13 trixie, kernel 6.18.50+rpt-rpi-2712, user `node`
(passwordless sudo). It sits on a **direct Ethernet cable** to Peter's Mac (USB adapter `en8`,
Realtek 00:e0:4c:36:0a:34, 100baseTX). eth0 holds static 192.168.144.1 and .2, and **the Mac has no
IPv4 on that subnet**, so none of the old bench addresses work. Reach it over IPv6:
- **Stable:** `node@fdbf:e1d0:e7be:74bc:57ab:fcc9:dc7b:e2e6` (ULA from the Mac's RA, no scope id).
- Link-local `fe80::57c4:fc51:3c24:b692%<if>` — but **the interface name moves**: mid-session `en8`
  was pulled into the Mac's Internet Sharing bridge and lost its own addresses, so `%en8` died with
  "No route to host" and only `%bridge100` answered. Find it with `ping6 -I <if> ff02::1`.
- **BB1 has NO internet** (`Network is unreachable`). Stage source/wheels on the Mac and push.
- **BB1's clock is ~84 days slow** (reads late Aug; no RTC sync offline). Extract with `tar -m` or
  rsync **without** `-t`, or every file lands "in the future".

**SCAR — macOS `/usr/bin/rsync` is openrsync and mis-parses `user@[ipv6%if]:path` as a LOCAL path.**
It "succeeded" in 11 s and wrote three dirs named `node@[fe80…]rdupilot` etc. into the lima repo root.
Use an ssh alias instead (`ssh -F conf` with `Host bb1`/`HostName <ula>`; `rsync -e "ssh -F conf" … bb1:`).
Then check the repo root for strays. **In zsh, `$E bb1` with E="ssh -F conf" does not word-split** —
spell the command out.

**`[measured]` 2026-11-18 — BB1 on Wi-Fi: `ssh node@bb1.local` / `node@192.168.0.118` (DHCP on Peter's home
`moleculex`, internet works).** Three things in the way, each a scar:
- **`flash_cm5.sh` writes `dtparam=ant2` (EXTERNAL U.FL antenna) into `/boot/firmware/config.txt`.** BB1 has no
  external antenna, so scans heard *nothing*. Now `dtparam=ant1` (onboard PCB antenna; backup
  `config.txt.bak-ant2`). Needs a reboot. On ant1 moleculex is −62…−67 dBm, but ~1 scan in 4 still hears nothing.
  Any other CM5 flashed by that script without an antenna has the same silent fault.
- **`devkit-wifi-keeper.service` races an interactive join.** Every ~60 s down it `con up`s any known profile in
  the air — including a just-created one with no PSK, which kills an `nmcli --ask` prompt mid-typing. Create the
  profile WITH the PSK in one step (`nmcli con add … wifi-sec.psk`), prompt read with `read -s` on BB1, never
  through chat. First `con up` then failed `ASSOC-REJECT status_code=16` (pre-handshake, not a wrong key); the
  keeper's next retry joined fine. So a one-off assoc reject on this radio is not proof of a bad password.
- **`192.168.0.118` was in the Mac's known_hosts for another device** (DHCP reuse). Verified BB1's ed25519
  `SHA256:B60POIg6…+Lms` over the Ethernet ULA first, then replaced the entry. Don't blindly `ssh-keygen -R`.
**`[measured]` Unplugging Ethernet KILLED native ArduPlane -> collector** — even though both run on BB1: both
ends used `192.168.144.1:14550`, an address on `fc-eth` (eth0), which NM drops with the cable. **Now both ends use
`127.0.0.1:14550`** (Peter's call): `/etc/systemd/system/arduplane.service` `--serial0 udp:127.0.0.1:14550` (repo
copy `linux/aeronode-cm5-image/service/arduplane.service`) and `AERONODE_MAVLINK_CONNECTION=udpin:127.0.0.1:14550`
in `/home/node/aeronode/.env` (backups `*.bak-20261118`). Verified with eth0 fully down: 100 Hz topics, disarmed,
no recording. The interim NM `ignore-carrier` stopgap was removed again. **Restarting the collector on the mavlink
source does not start a recording** (collector.py ~5544), so it does not arm the FC. `fc-eth` was left
`nmcli con down` — `[assumed]` it autoconnects when the cable returns; check on the next plug-in.
**Wi-Fi drop 13:25 (BB1 clock) was DHCP, not RF:** moleculex hands out **600 s leases**; the first lease's renewals
failed silently and it expired -> NM `ip-config-unavailable` -> ~40 s off-air, keeper rejoined. Next renewal
(13:31:15) succeeded `[measured]`. One clean renewal ≠ fixed: if drops recur every ~10 min, ask Peter for a router
DHCP reservation for 2C:CF:67:D4:8C:FF. **BB1's clock fixed itself once online**
`[measured]`: by 12:59Z it matched the Mac to 1 s, chrony synced to teraco.co.za. (I wrongly predicted
`makestep 1 3` would refuse the 84-day step — it counts the first 3 *clock updates*, not the first 3 polls.)
Offline BB1 will drift again. **Its MQTT is visible from the Mac:** `brew install mosquitto`, then
`mosquitto_sub -h bb1.local -t 'aeronode/#' -v` (anonymous, 1883; websockets 9001; web UI :8000). ~1300 msg/s
total; Mac got 997 vs BB1 1001 imu msgs in 10 s — full rate over Wi-Fi.
**`[measured]` A flat battery looks like a clean cut, not a brownout:** BB1 on the patio died 13:18:37Z with
`logs/power.csv` (`/home/node/aeronode/logs/`) at a steady 5.02 V, throttled 0x0, 49 °C to the last row, then
nothing; journal -b -1 ends mid-line. Peter: "battery died". The monitor gives NO warning of an emptying pack —
ask about power before suspecting the board. Every such cut = GNSS cold start again (no V_BCKP).

**`[fetched]` GNSS assistance, 2026-11-18 — the old route is gone.** ArduPilot can't help via settings:
`GPS_RATE_MS` is clamped to ≤200 ms (`AP_GPS.cpp:1796 get_rate_ms`, MIN(rate, GPS_MAX_RATE_MS)) and the driver
re-forces it; airborne model 8 is right for a plane. The lever is A-GNSS. **u-blox AssistNow Online/Offline
(token + GetOnlineData.ashx) is End of Support from 2026-05-31** (Thingstream guide). The replacement is
`https://assistnow.services.u-blox.com/GetAssistNowData.ashx?chipcode=…&data=ualm,uporb_N,ulorb_l1,utime,ukion,usvht
&gnss=gps,gal,glo,bds,qzss[&filteronpos&lat&lon&pacc]` (assistnowapi.services.u-blox.com). The chipcode is per
receiver: poll UBX-SEC-UNIQID (B5 62 27 03 00 00 2A A5) + UBX-MON-VER (B5 62 0A 04 00 00 0E 34), POST them with a
**ZTP token** from a Thingstream domain/ZTP device profile, and get a `chipcode` back. The registration docs are
behind a Thingstream login (support.thingstream.io gives 403 to fetchers). iNav users say Predictive Orbits is free.
`[assumed]` DAN-F10N is supported — not confirmed. Injection path: MAVLink GPS_INJECT_DATA/GPS_RTCM_DATA ->
`AP_GPS::inject_data` -> raw bytes to the receiver's UART (`AP_GPS.cpp:1265-1377`), via the 14552 link.
**`[measured]` 2026-11-18 13:43Z — AssistNow WORKS for BB1's DAN-F10N.** Thingstream domain `aerosense`
(AssistNow ZTP already enabled), ZTP device profile `bb1` (type AssistNow, module OTHER, Predictive+Live,
**Evaluation**). Endpoint `https://api.thingstream.io/ztp/assistnow/credentials`, body
`{"token":…, "messages":{"UBX-SEC-UNIQID":HEX,"UBX-MON-VER":HEX}}` (full frames, uppercase hex) -> HTTP 200
`{chipcode(28), serviceUrl, allowedData}`; allowedData = ualm, uporb_1/3/7/14, ulorb_l1, utime, ukion, usvht.
Secrets on BB1 only: `~/.config/aeronode/assistnow/{ztp_token,ztp_credentials.json}` (600). Receiver reports
`MOD=DAN-F10N`, `SPGL1L5 6.00`, PROTVER 40.00, uniqueId 6 B. **First `ulorb_l1` (Live) request -> 403002
"usage limit has been reached for your device"**; `uporb_1` (Predictive) -> 12028 B / 190 frames, and with
CFG-NAVSPG-ACKAIDING on in RAM **all 190 MGA-ACK (type 1, infoCode 0) = accepted**. Tools:
`linux/aeronode-cm5-image/scripts/assistnow_{set_token.sh,bootstrap.py}`. Breaking ArduPlane is avoided by
wrapping in systemd-run with a trap that always restarts it. **ArduPilot's inject path silently drops a whole
packet when UART txspace is short** (`GPS_Backend.cpp:117`) — send one whole UBX frame per GPS_INJECT_DATA
(every MGA frame is <=96 B) and pace it. Peter pasted the token twice once (72 chars): the length check caught it.
**`[measured]` Position aid matters, and it works THROUGH ArduPlane.** After orbits alone the receiver listed
18 SVs (1 GPS) and tracked 2. `assistnow_inject.py --pos-only` (fresh MGA-INI-TIME from chrony + MGA-INI-POS_LLH
= centre of ZA ±1000 km, deliberately coarse) sent via MAVLink GPS_INJECT_DATA with ArduPlane RUNNING: 21 s later
gps_raw h_acc went 4294967 m -> 817 km (receiver took it) and NAV-SAT listed 34 SVs (10 GPS/9 GAL/11 BDS/4 SBAS).
**Still only 3 tracked (30/27/20 dB-Hz) -> no fix: reception-limited, not data-limited.** Peter moved BB1 to
open sky -> 8 tracked -> 3D fix 13:52:34Z, 11 SV, hAcc 46 m; ArduPlane 3D 7-9 SV, EKF3 1024 -> 167 at 13:52:53Z
(bit 128 const-pos-mode: hAcc ~28 m still too poor for the GPS checks). **TTFF NOT attributable** (moved mid-trial,
3 ArduPlane pauses): a clean A/B (power-cycle, inject at boot, same spot) is still owed. ArduPlane does not reset the
receiver unless GPS_AUTO_CONFIG=3 (`AP_GPS_UBLOX_CFGv2.cpp:1173`, mask 0x0000 anyway).
Peek tool: `/home/node/gnss_peek_run.sh` (stops ArduPlane 12 s, ubx_pvt.py --poll-sat, trap restarts it).
**`[measured]` BOOT-TIME AssistNow on BB1 — what finally works (2026-11-18 14:35Z):**
`assistnow-preload.service` (oneshot, RemainAfterExit, Before=arduplane, WantedBy=arduplane, TimeoutStartSec 90)
runs `/home/node/aeronode-scripts/assistnow_inject.py --serial`: finds the receiver by polling MON-VER at
230400/38400/115200/9600 (**after a power cycle it answers at 38400 — ArduPilot's GPS_SAVE_CFG does NOT keep the
baud**; reboot of BB1 = GNSS power cycle), sends MGA-INI-TIME + coarse POS + Live orbits (with **utime**), ACKs on,
resends "no time" rejects once -> **182/182 accepted, then ArduPlane starts.** `assistnow-savepos.service` (after
ArduPlane) refreshes time+pos via GPS_INJECT_DATA and saves a 0.1 deg position after a fix with hAcc < 50 m.
**Scars:** (1) GPS_INJECT_DATA bulk (178 frames) is LOST — only the 2 small INI frames are proven through
ArduPlane; (2) AP drops injections until it has detected the GPS (`drivers[i]==nullptr`); (3) without `utime`,
or on a just-cold receiver, ~105/182 frames come back infoCode 1 "no time" although INI-TIME was ACKed — resend;
(4) my cold-reset "test" at 13:58 threw away a working 9-SV fix and cost Peter ~35 min: reacquisition needs more
signal than tracking on this antenna. **Reception still decides TTFF**: 2 strong SVs heard near the house vs a
fix ~4 min after moving to open sky. Peter's rough position: entered by him via hidden prompt
(`scripts/assistnow_set_pos.sh`), rounded 0.1 deg, ±20 km, on BB1 only. macOS CoreLocationCLI was denied even
after he allowed Claude — CLI tools don't inherit it; don't retry that route.
**`[measured]` First assisted BOOT TTFF: 211 s** (reboot = GNSS power cycle, open-sky spot, preload 182/182 at
14:35:38Z -> ArduPlane 3D 4 SV at 14:39:09Z). n=1, not an A/B: unassisted cold starts earlier today were 443 s
(factory cfg) and 679 s / >20 min (ArduPilot cfg) in other spots/sky. Assistance helps; signal still sets the floor.
**`[measured]` 2nd assisted boot (Peter's reboot 14:44:56Z): preload 182/182 at +28 s (38400 baud, fresh Live
orbits), ArduPlane detected GPS at +40 s, 3D fix at +319 s (5 SV), EKF3 1024->167; at +341 s 8 SV, HDOP 1.38,
hAcc 69 m.** Two assisted boots: 211 s and ~291 s after injection. Minutes, not seconds — reception-bound.
savepos **verified**: wrote coarse_pos at 14:40:13Z when hAcc fell below 50 m (5 min after boot), then exited. It used ±50 km, looser than Peter's ±20 km entry — now ±20 km (0.1 deg rounding <= ~8 km).
**`[measured]` 2026-11-19 — BB1 logging + 3D track viewer.** No ArduPilot log had EVER existed (never armed;
LOG_DISARMED was 0). Set **LOG_DISARMED=1** via param_set.py on 14552 (stop assistnow-savepos first — it holds
the port): `/var/lib/ardupilot/logs/00000001.BIN` started at once, **41 KB/s ≈ 145 MB/h** (LOG_BITMASK 65535,
SCHED 400), 20 GB free ≈ 140 h; new file per boot. `scripts/track3d.py LOG.BIN [out.html]` -> offline 3D viewer:
EKF track (XKF1 core 0 PN/PE/PD) + GPS 3D fixes as ENU metres about ORGN (or first fix); **no coordinates in the
HTML**; tested on a real BB1 log (no fix -> clean "no trajectory" page) and a labelled synthetic loop. Keep
outputs local (shape of the walk). **Gap seen at the 05:48Z boot: preload sent position ONLY** — Wi-Fi/clock not
up when it ran (no RTC), so no time and no orbits. Needs a network/clock wait (cost: later ArduPlane start).
Note: ArduPlane's terrain dir names a 1x1 deg tile — don't quote it.
**`[measured]` 2026-11-19 06:08Z: manual full load (`preload_now.sh`) after a position-only boot -> 182/182
accepted (receiver at 230400 since ArduPlane had configured it), 3D fix 6 SV in 63 s.** Fastest yet: the receiver
had been powered and searching outdoors 19 min, and this time got time + 20 km position + Live orbits together.
**`[measured]` First real BB1 walk track (2026-11-19, 06:08–06:35Z, log 00000002.BIN):** 4771 GPS 3D fixes (96.9 %),
median hAcc 10.2 m (vs ~30 m in yesterday's patio spot), GPS horizontal extent 226 m — a clean out-and-back of
~190 m with the return a few m off the outward leg. **EKF extent 0 m: CONST_POS the whole walk, never fused GPS**
(hAcc never under Plane's 7.5 m). Page built ON BB1 (`track3d.py` with the venv python, ~40 s) — pulling a 72 MB
live .BIN over this Wi-Fi crawled and `scp` of a file ArduPlane is still writing never ends: **snapshot with cp
first, build on BB1, copy back the ~0.5 MB HTML.** Output kept in the scratchpad only (it traces the walk).
Viewer note: with no EKF origin the EKF dot is not aligned to the GPS track.
**`[measured]` SCAR 2026-11-19 — "logs always on" was FALSE past one boot; Peter's test drive was LOST.** The AeroNode
collector OWNS `LOG_DISARMED` (`config.collector.log_disarmed_follows_record=True`): 1 on record START, 0 on STOP,
and at startup while idle it resets a 1 to 0 (`collector.py` ~2952, "[startup] LOG_DISARMED=1 on the FC while
idle ... setting it back to 0"). My param_set write survived until the drive boot itself: journal 11:17:38 SAST, 6 s after
ArduPlane started, "[startup] ... (a stop that never finished) — setting it back to 0" (the 11:06 boot was too
short to get there). The drive boot (11:17–12:41, no network, clock unsynced) wrote no .BIN, and with no session recorded `device_health.db`
sensor_data/flights are empty too (events.jsonl = health only). Log 2 (walk + 80 min after) = 250 m extent, no drive.
**I set a control and never checked it across a reboot — verify-at-point-of-use failed.** Correct way to log a
drive/flight: **start a recording in the AeroSync app / dashboard** (sets LOG_DISARMED=1 AND records sensors).
Truly always-on needs `log_disarmed_follows_record=false` — a design change to AeroNode, Peter's call (the config
comment explains why it exists: a 29 GB eMMC once filled with bench data).
**`[measured]` FIXED same day (Peter: "make logging always on as well as mic record"):**
(1) BB1 `~/aeronode/config.toml` [collector] gets `log_disarmed_follows_record = false` (box-local — the AeroNode
tree on BB1 is not a git checkout and this repo doesn't ship config.toml; backup `config.toml.bak-20261119`; an
AeroNode redeploy would undo it — re-check after any). LOG_DISARMED=1 set again. Positive control: collector restart
then a full REBOOT -> no "[startup] ... setting it back to 0" line, LOG_DISARMED reads 1, new 00000004.BIN growing
~42 KB/s. (2) Always-on onboard-mic recorder: `aeromic-record.service` (arecord hw:CARD=aeromic -> ffmpeg, left
channel, 24-bit mono FLAC, 60 s files, UTC names, `~/aeronode/logs/aeromic/`) + `aeromic-prune.timer` (10 min; cap
8 GB, floor 2 GB free, oldest first, never the newest; controls tested in a temp dir). ~138 MB/h quiet room. Resumed
after the reboot. ffmpeg's own alsa input xran 7x/14 s — use arecord's buffer. aeronode-audio-capture.service is
UMIK-2-only and its capture.py isn't even deployed on BB1 — irrelevant to the aeromic. Retention: ArduPilot .BIN
pruned only by LOG_FILE_MB_FREE=500 at each new log; at ~145 MB/h one very long boot could still eat the disk.

**`[measured]` 2026-11-18, BB1's DAN-F10N (u-blox F10) GNSS:** on `/dev/ttyAMA0`. Factory state was NMEA at
38400. **Since ArduPlane ran it (Peter's go-ahead), it is UBX-only at 230400, saved to the receiver's flash**
(`GPS_AUTO_CONFIG=1`, `GPS_SAVE_CFG=2`). Anything that wants NMEA from it must reconfigure the receiver
or go through ArduPilot. Read-only tools: `linux/aeronode-cm5-image/scripts/gnss_sniff.py` (finds the baud)
and `ubx_pvt.py` (NAV-PVT/NAV-SAT/MON-RF). **Never print or commit its position**: both tools leave it out
on purpose. A plane's EKF3 needs a 3D fix to initialise at all (`AP_NavEKF3_core.cpp:457`).

**`[measured]` 2026-11-18, native ArduPlane on BB1 feeds the aeronode collector.** `arduplane.service`
(installed, **not** enabled at boot) sends `--serial0 udp:192.168.144.1:14550`, the collector's udpin. **The
collector's 50–100 Hz stream requests need `SCHED_LOOP_RATE=400`**: at Plane's default 50 ArduPilot DENIES any
interval faster than 40 Hz and those streams sit at 1 Hz with no error on the FC side (`GCS_Common.cpp:278`).
It's a parameter in `/var/lib/ardupilot/ArduPlane.stg`, so a fresh state directory reverts it silently. Set or
read params over `--serial1 udp:127.0.0.1:14552` with `linux/aeronode-cm5-image/scripts/param_set.py`, which
leaves the collector's link alone. **Starting a collector recording auto-arms the FC.**

**`[repo]`+`[measured]` 2026-11-18, Blackbox board GNSS has NO backup domain.** Schematic sheet 9: DAN-F10N pin 55
`V_back` = **nc**. `Vgps` = U11 TPS7A2033, En = `GPS_Power` = CM5 pin 82 = **GPIO38/SDA0** (1k8 pull-up to CM5 3.3 V,
R37 100k to Vcm5, the designer marked it with a red "?"). `GPS_AntSel` = GPIO34 (low = internal antenna, how BB1
runs), `GPS_nRes` = GPIO35, TimePulse = GPIO42. **A reboot power-cycles the GNSS** (NAV-STATUS msss ≈ Linux uptime,
`scripts/ubx_uptime.py`); a service restart does not. With no V_BCKP every boot is a cold start, which needs
−145 dBm where hot start needs −156 and tracking −164 (DAN-F10N DS R04 Table 2). **`[correction]` "never
re-acquires" was an overclaim:** the previous boot was also cold (same circuit), and by the time I first sniffed, it
had a fix with 8 SVs and HDOP 1.37 on the onboard antenna (Peter: "we should get fix with onboard antenna"). So a cold
start here is SLOW or uncertain, not impossible. Second candidate: ArduPilot's config (saved to flash) changed which
GNSS/signals it searches; the earlier cold start used the factory config. Not yet separated. EKF3 waits for a fix. Fix = V_BCKP from an
always-on rail (31 µA). Which rail drops on reset: scope TP15 Vgps.

**SCAR — never open a serial port a watcher already holds (2026-11-18).** I sniffed `/dev/ttyAMA0` while
`nmea_watch.py` was reading it; the watcher died with "multiple access on port", and the job that was meant to
start ArduPlane on the first fix waited on a dead log while Peter stood outside with a fix. **One reader per
tty.** To peek, read the watcher's log, or stop it first. And any wait-for-X loop must also exit on its
worker dying (`pgrep` it), not just on the success string.

**`[measured]` 2026-11-18, BB1 GNSS cold start:** factory config, indoors: 9.5 min once, >13 min once.
ArduPilot config (CFGv2: 5 Hz rate, airborne dynmodel, min-elev, L5 health override, RAWX): >20 min twice, so
suspect, culprit not isolated. Outdoors on the **onboard antenna**: still only 27–29 dB-Hz at high elevation
(~15 dB low), fixed after a few minutes. **Working recipe when it won't fix:** stop arduplane →
`scripts/gnss_factory.py` → wait for fix (`nmea_watch.py`) → start arduplane; ArduPilot keeps the fix and EKF3
initialises in ~11 s.

**SCAR — BB1 is shared with other Claude sessions on the same Mac (2026-11-18).** A reboot that killed my GNSS
recovery came from session "BB1 WiFi connection" (switched `dtparam=ant2`→`ant1` in config.txt, then `systemctl
reboot`), not from power or my code. Its SSH source address is the Mac's own, the same as mine, so the journal
can't tell us apart; only the commands can. **Before long or stateful work on BB1, run `ListAgents` and look for
peer sessions touching the board. When BB1 reboots unexpectedly, read `journalctl -b -1` for `sudo ... reboot`
before blaming power.** Every reboot = GNSS cold start (no V_BCKP), so uncoordinated reboots cost ~10 min of EKF.
