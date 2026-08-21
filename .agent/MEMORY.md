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
