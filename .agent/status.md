# status — Agent LIMA

**Updated:** 2026-08-20

## Where things stand

Onboarding complete per `aero-ssh-bridge/ONBOARD_PROMPT.md`. Phases A, B and C run.

- **Phase A** — SSH key created and registered (`~/.ssh/id_ed25519`, `pb-aero`); brain template
  v2.0 installed as `CLAUDE.md`; `.agent/` scaffold created by `bootstrap-agent.sh`; WHOAMI
  filled in. Boot push verified at `c63d997`. `[measured]`
- **Phase B** — read all five STANDING memos, `WORKFLOW.md`, `ACCESS.md`, `reports/README.md`,
  `reports/REPORT_STATUS_BANNER.md`. `inbox/peter/` is empty (README only). No bridge needed —
  Claude Code is terminal-capable.
- **Phase C** — self-test 15 pass / 1 fail / 1 warn. Report landed at
  `reports/peter/LIMA_access_check.md`, sync main `ef07d74524ae14d5827942b13fe89b694ddb9d1e`.
  `[measured]`

## Open

1. **No read access to `aerosense-ops`** — `git clone` returns `Repository not found`. Duran
   grants it (Read, never write). This is the one self-test failure, and it cascades: check 7
   (must be refused writing ops) was SKIPPED, which is a warning, not a pass. Until this is
   fixed I cannot read company state, tasks or hardware — step 1 of the workflow loop.
2. **This repo is 1 commit ahead of origin.** `745725e` is committed locally but unpushed — the
   Claude Code auto-mode classifier blocks `git push` from a direct shell call. Peter to push it
   by hand or add a Bash permission rule. Boot step 5 (sweep for stranded memory) will catch
   this on the next session if it is still outstanding.
3. **Remit is `[assumed]`** in WHOAMI — Peter has not yet set one. Narrow it and drop the tag.
