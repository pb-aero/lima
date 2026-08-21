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

### Open — needs Peter's ruling before I touch it

1. **The side pad columns are wrong.** Module is 40.000 x 45.000 mm `[measured]` from the STEP; the
   64 column pads at x = +/-16.51 are 2.49 mm under the module body. Rows are correct. Fix is
   probably x = +/-19.725 and a 40 x 45 body outline, but that is `[derived]`, not sourced, and it
   moves 64 electrical pads. **Confirm against the HRM pad table or Digi's `CC93_DVK.PcbLib` first.**
   The PcbLib is downloaded and unread — Altium OLE binary, would need `olefile` to parse.
2. **No host keepout.** 105 solids hang 0.700 mm below the SOM PCB bottom, over footprint-relative
   X -11.75..+15.40, Y -4.425..+7.85. Footprint carries nothing for this.
3. **Digi ships the wrong document** under "ConnectCore 91 and 93 host PCB footprint and cutout" —
   the zip contains ConnectCore **8X** files dated 2022. Worth reporting to Digi.
4. Still outstanding from the earlier session: `NVCC_SD2`/`1V8` typed `bidirectional` should be
   `power_in`; symbol Footprint/Datasheet/Description properties empty.
