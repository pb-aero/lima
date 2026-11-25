# `inbox/peter` triage — 2026-11-25

**Agent:** LIMA · **Source:** `Aerosense-Dev-Team-Sync@456d469` (pulled 2026-11-25). There are 23 files marked
`status: open`. For each one, I checked who replied (`peter/outbox/`), which later messages and rulings
reference it, and this repo's history.
Ruling basis: `[repo]` = a file says so · `[reading]` = my interpretation, worth a glance before you close.

**Short answer: not all of them are settled.** 10 can close now. 6 need a decision or a fact that only you
have. 7 are bench work that is still undone.

---

## A · Close now (10)

| Message | What closes it |
|---|---|
| `2026-11-23-002` KILO: STEP files | You closed it 25 Nov, because Stefan found the files. **The file on origin still says `open`**, so the status line needs flipping and pushing. |
| `2026-11-13-001` ALFA: BB1 SSH login test | Answered by `peter/outbox/2026-11-13-002_bb1-ssh-login-works.md` `[repo]` |
| `2026-10-21-002` JULIETT: hub decided | Its header says *"needs: nothing from you"* `[repo]` |
| `2026-10-29-004` JULIETT: correction on the 1861 | Its header says *"needs: nothing"* `[repo]` |
| `2026-10-29-002` JULIETT: 1861 footprint | Superseded by `-29-004`: you ruled the 1861 on 22 Sep `[repo]`. The 9 × 9 mm footprint carries into cup layout. |
| `2026-10-29-003` JULIETT: ICM gap from flight data | Withdrawn by `-30-001`, which says *"Peter sets aside 2026-10-29-003"*; the 2.6 ms residual was a sign error `[repo]` |
| `2026-10-30-001` JULIETT: DVNC report corrections | Your only action was setting aside `-29-003`. The rest is GOLF's `[repo]` |
| `2026-10-29-005` JULIETT: measure S(z) Monday | A heads-up. Its one ask, a known-good mic position in the cup, was *"only if cheap"* and lapsed on 2 Nov. John recorded his own `[repo]` |
| `2026-10-21-006` JULIETT: Huey audio not clipped | Its recommendation was corrected the same day by `-21-007` `[repo]` |
| `2026-10-21-007` JULIETT: ECHO had already found it | Needs only reading. Its test (keyed VHF) is GOLF's and ECHO's `[repo]`. **But read §C below first: it matters for the 1 m I2S work.** |

## B · Needs your decision or answer (6)

| Message | What's being asked | Notes |
|---|---|---|
| `2026-10-21-001` JULIETT: audio board spec | §3, three questions that block *your* layout: **(1)** where the bypass electret goes now that the boom mic is gone; **(2)** one electret or two (identical cups vs one panel mic line); **(3)** whether its return needs isolation | No reply in `peter/outbox/` `[repo]` |
| `2026-10-21-004` JULIETT: same spec as PDF | §8, three questions | `[reading]` These are probably the same three as `-21-001` §3. If so, close it into that one. I didn't compare them line by line. |
| `2026-10-21-005` JULIETT: cabin mic is analogue | §2: **3.3 V direct or a local 2.75 V** for the cabin mic, and a ruling on *"cabin capture is dead until the CM5 has booted"* | Explicitly your choice. No reply `[repo]` |
| `2026-09-10-004` JULIETT: parts to order for the DVNC rig | What was actually ordered (sensor head + 2.75 V LDO) | Only you know. Then close. |
| `2026-09-25-004` JULIETT: size the hub eval | One part number for the ADAU1467 eval | The hub was decided 21 Oct (`-21-002`). Did an eval board get ordered? |
| `2026-09-25-005` JULIETT: cup sensor data path | §2: how cup sensor data reaches the CM5 | `[reading]` Partly overtaken: John ruled on 21 Oct that the production DVNC reference is the ICM-45686 on SPI to the CM5, and *"never enters the audio chain."* The cup board still carries an LSM6DSV16BX on TDM as a DVNC reference. **One of them should change, or the role of the cup IMU should be stated.** |

## C · Bench work still undone (7). Leave these open.

| Message | What | Notes |
|---|---|---|
| `2026-09-17-002` | 1372 → CM5 → 1860 test sheet | Not run. As of 21 Oct it was blocked on tailnet access. |
| `2026-09-18-001` | Accelerometer + one mic on the 1372 | `[reading]` Worth less since the ADXL354 left production (21 Oct, bench reference only). You might close it as overtaken. |
| `2026-09-24-006` | Latency M1/M3/M4/M5 | M5 (A2B node → cup) is still a gap with no number. |
| `2026-09-28-001` | The five tests + HiFi cycles + M7 cancellation | Not run. |
| `2026-09-24-003` | A2B data-pin check against the 1372 | `[reading]` Probably moot: in the 21 Oct architecture the ADAU1467 hub sits between the 1372 and the A2B. Close if you agree. |
| `2026-09-24-004` | Three connection-map conflicts + AD2433 slot/SPI facts | Needs re-reading against the 21 Oct rulings. Most of it is probably overtaken, but I haven't checked. |
| `2026-10-21-006/-007` follow-up | The level-margin fix on DEV-A's 1.8 V → 3.3 V I²S link | Still worth closing, per `-21-007`, but second to shielding. |

### Why `-21-007` matters for the 1 m I2S PoC

`[repo]` On the Huey flights, DEV-A's codec→Pi I2S link took **158,251 corrupted words**, all of them
inside, or within 13 s of, the aircraft's own VHF transmissions. The cause was RF pickup on **unshielded I2S jumper wires**. The SPI IMU
on the same board was untouched. ECHO's fix order is: shielded or twisted-pair cable with ground, then ferrites
at both ends, then a ground-plane carrier board.

That is the failure the 1 m PoC (`docs/i2s-i2c-1m-poc-plan.md`) is meant to catch. The plan doesn't yet
include an RF-immunity row. **It should add a keyed-VHF (or bench RF-injection) run, with the same pass rule:
zero full-scale and zero non-24-bit words.**
