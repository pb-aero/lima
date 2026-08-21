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
