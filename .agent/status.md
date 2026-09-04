# status — Agent LIMA

**Updated:** 2026-08-21

## Where things stand

Onboarding complete per `aero-ssh-bridge/ONBOARD_PROMPT.md`. Phases A, B and C run. INDIA's
welcome message answered and closed.

- **Phase A** — SSH key created and registered (`~/.ssh/id_ed25519`, `pb-aero`); brain template
  v2.0 installed as `CLAUDE.md`; `.agent/` scaffold from `bootstrap-agent.sh`; WHOAMI filled in.
- **Phase B** — read all five STANDING memos, `WORKFLOW.md`, `ACCESS.md`, `reports/README.md`,
  `reports/REPORT_STATUS_BANNER.md`. No bridge needed — Claude Code is terminal-capable.
- **Phase C** — self-test 15 pass / 1 fail / 1 warn (14 in the landed table; the push that lands
  the report cannot count itself). Report at `reports/peter/LIMA_access_check.md`.

## Repo state, verified at full length

- `pb-aero/lima` — `6dcf33520d05b781d3b3e97c5c83b1f32365d36a` `[measured]`
- `Aerosense-Dev-Team-Sync` main — `8ce92910970dad4e3d8e8895abe6130f692714e8` `[measured]`

## Correspondence

- **IN** `inbox/peter/2026-08-20-001` from INDIA — welcome + two asks. **status: answered.**
- **OUT** `peter/outbox/2026-08-20-001_onboarding-findings-macos.md` — six findings from the cold
  macOS read. Delivered as `inbox/chris/2026-08-20-004`.
- **OUT** `peter/outbox/2026-08-20-002_permission-net-verified.md` — guard proven by positive
  control. Delivered as `inbox/chris/2026-08-20-005`.

## Closed this session

- **Permission net installed and PROVEN.** `lima/.claude/settings.json` per INDIA's spec. All three
  positive controls refused: `git commit -am`, `git add -A`, `git push --force`. Negative control
  passed — plain `git push`, `add <path>`, `commit -m`, `status`, `log`, `ls-remote` all work.
  `[measured]` **It took effect mid-session — no restart needed, contrary to the instruction.**
- **Nothing stranded.** Working tree clean, local == remote on both repos.

## Open

1. **No read access to `aerosense-ops`** — `Repository not found`. Duran grants it. INDIA confirms
   it blocks all three team agents (me, KILO, JULIETT). **Do not start work that depends on ops.**
   This is the one self-test failure; check 7 stays a WARN until it clears, and a skipped check is
   not a pass.
2. **Off-switch gap, raised with INDIA, not yet ruled.** The shipped `settings.json` has no
   `Edit(///...settings.json)` deny, so nothing stops an agent rewriting its own guards — which
   `CLAUDE.md` §6 calls the single most important rule. Left unpatched deliberately: a fleet-wide
   rule beats a local variation. Chase if no answer.
3. **Remit is `[assumed]`** in WHOAMI — Peter has not set one. Narrow it and drop the tag.

## Next session

Read `inbox/peter/` and `memos/` first. Then, while ops is still blocked, the useful work is
reading: start at any `MANIFEST.md`, and `git grep -il '<term>' -- reports/ chris/ john/` before
asking anything — re-derivation is the most expensive failure this project has measured.


---

## 2026-08-21 · ConnectCore 93 footprint — 3D model attached

Peter asked whether a 3D model could go on the CC93 footprint. It can, and doing it found a bug.

- **Done.** Digi's STEP is attached to `Digi_ConnectCore93_Castellated` at offset
  `(-20, -22.5, 1.547)`, verified by headless `kicad-cli pcb render`. Renders committed at
  `kicad/lib/doc/`. STEP is gitignored (13 MB); `scripts/fetch-3d-models.sh` restores it with both
  checksums pinned — tested with positive and negative controls. Commit `23727c9`, push verified.
- **Digi's portal is not gated.** No login, no licence click-through; `/dp/path=/support/asset/...`
  returns the zip. Three assets pulled: SoM 3D model, host-PCB footprint drawing, Altium SchLib/PcbLib.

### Closed later the same day — geometry sourced and fixed (commit `bb463d6`)

1. **Pad geometry FIXED and sourced.** `33,56` is the **host PCB cutout width**, not the pad span —
   that one misread is the whole bug. From HRM 90002549 rev 4P p.83, measured by projection profile
   and cross-checked against four of the drawing's own labels: columns now **x = +/-20.000**, rows
   **y = +/-22.500**, body **40 x 45**. All four runs straddle the edge by exactly 1.000 mm, matching
   DETAIL A's `1` — an agreement I did not aim for. 118 pads, 0 overlaps, DRC 0 violations.
   The earlier `[derived]` guess of +/-19.725 was close but wrong; good thing it was not applied.
2. **Keepout MARKED** on `Dwgs.User`: Digi's dimensioned cutout **33.56 x 20.86 centred** (build to
   this), plus the measured protrusion envelope as a thin reference rect.
3. **Digi's Altium `CC93_DVK.PcbLib` does not cover this part** — 474-pad LGA array, different
   variant. Do not retry it. But noted for reuse: **KiCad ships an Altium importer callable from its
   own Python** (`pcbnew.PCB_IO_MGR.FindPlugin(...ALTIUM_DESIGNER)`), so no OLE parsing needed.

### Open

4. **Digi ships the wrong document** under "ConnectCore 91 and 93 host PCB footprint and cutout" —
   the zip contains ConnectCore **8X** files dated 2022. Worth reporting to Digi.
4. Still outstanding from the earlier session: `NVCC_SD2`/`1V8` typed `bidirectional` should be
   `power_in`; symbol Footprint/Datasheet/Description properties empty.


### Not mine — flagged, untouched

`kicad/imu-board/` and `kicad/lib/TDK.kicad_sym` appeared untracked in the working tree during this
session; they were not there at boot and are not my work. **Left alone, not staged.** Another session
is live in this checkout — check before assuming the tree is yours.

---

## 2026-08-21 · imu-board — two IMUs added (ICM-45686 + BMI088)

Peter asked for an ICM-45686 and a BMI088 on "my kicad schematic". There wasn't one — the only
`.kicad_sch` in the repo was the empty 9-line `_modeltest` stub — so this is a new project.
Peter ruled: new project in lima, SPI with one CS per die, 3V3 for both VDD and VDDIO.

- **Done.** `kicad/imu-board/` created. U1 ICM-45686 (symbol authored at `kicad/lib/TDK.kicad_sym`,
  registered project-scoped), U2 BMI088 (stock `Sensor_Motion:BMI088`), C1-C5 decoupling,
  PWR_FLAGs on both rails. Shared SPI bus, three chip selects, four interrupts brought out to
  labels. Netlist verified per pin — all 30 land correctly. 0 shorts, 0 overlaps.
  Notes at `kicad/imu-board/doc/imu-board-notes.md`.
- **ICM-45686 pinout is solid** — `[fetched]` from two independent TDK documents that agree on
  all 14 pins (EVB guide AN-000484 Figure 2, and the SM-ICM45686 module datasheet's U1 symbol).

### Open — needs Peter's ruling before layout

1. **U1 has no footprint, deliberately.** DS-000577's package drawing could not be retrieved
   (TDK redirects to marketing; LCSC serves a title-only shell; SnapEDA 403s). The stock
   `LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y` is a **trap** — right size and pin count, but a 3x4
   perimeter pattern from an ST part where the ICM-45686 is dual-row 7+7. Best next lead: the
   ICM-45605 sibling datasheet `DS-000576`, same package, reportedly reachable.
2. **SDO1+SDO2 tied to one MISO is `[practice]`, not proven.** ERC flags output-output. Standard
   in every BMI088 design and implied by the datasheet's shared-SDI/separate-CSB architecture,
   but the tri-state sentence lives only in an image (Figure 8, p53). Held open, not rounded to green.
3. **RESV termination unconfirmed** — U1 pins 2,3,7,10,11 are no-connected; some InvenSense parts
   require RESV tied to GND. DS-000577's pin table settles it.

Four of the five ERC errors are just "input pin not driven" on SCLK/CS — the host doesn't exist
on the sheet yet. They clear when a host or connector is added.

## 2026-09-04 · ArduPilot installed on scopenode — DONE

Peter: *"install ardupilot for linux on the pi"*. Delivered and verified on hardware.

- **Built and running.** `arduplane V4.8.0-dev (ff37fde6)`, native aarch64, at
  `node@scopenode.local:~/ardupilot/build/linux/bin/arduplane`. `./waf configure --board=linux`
  + `./waf plane`, 4m52s. `[measured]`
- **Peter's rulings this session:** bare Pi 5 (no HAT) so `--board=linux`; `plane` only;
  **accept kernel 6.18.39** rather than roll back.
- **Kit:** `linux/ardupilot-pi5/` — `install_ardupilot.sh` (preflight/clone/prereqs/build/verify),
  `NOTES.md` (upstream analysis), `RESULTS-2026-09-04.md` (what actually happened).

### Carried forward — needs action before the ADAU1860 work is trusted again

**`scopenode` will boot kernel 6.18.39+rpt-rpi-2712 at the next restart** (was 6.12.47). Pulled in
as an apt dependency of `g++-arm-linux-gnueabihf`, which the ArduPilot prereqs script installs
unconditionally and which this build never uses. Running kernel is still 6.12.47 — the change is
latent, not active.

Everything in `linux/adau1860-pi5/` — the RP1 I2S clock-direction findings, the 4-lane duplex
bring-up, the register work — was measured on 6.12.47. **Re-verify on 6.18.39 after the next
reboot before building on any of it.** Device-tree node names, `dwc-i2s` behaviour and overlay
compatibility all sit on that version.

### Open

1. `[gap]` The 6.18.39 re-verification above. Not started; needs a reboot Peter chooses.
2. Upstream bug found, not reported: `Util_RPI.cpp:62` uses `strncmp(d_name, "soc", 4)`, an exact
   match where a prefix match was intended, so Pi 5 detection fails on kernels that name the node
   `soc@107c000000`. Harmless for `--board=linux` (GPIO_RPI not compiled) but an `AP_HAL::panic`
   at startup for `navio2`/`pilotpi`/`navigator64`. One-character fix. Worth a PR if Peter wants it.
