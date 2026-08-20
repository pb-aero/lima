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
