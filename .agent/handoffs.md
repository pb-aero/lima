# handoffs — Agent LIMA

## 2026-09-04 · ArduPilot on scopenode — handoff

**If you are booting cold into this:** everything is in `lima:linux/ardupilot-pi5/` — `NOTES.md`
(upstream analysis), `RESULTS-2026-09-04.md` (three parts, what actually happened), and
`upstream-pr/` (patches + PR body). The published report is
`Aerosense-Dev-Team-Sync:reports/peter/LIMA_ardupilot_pi5.html`.

**The half-made decision I would want to know about:** the IMU FIFO stall is *not* mine. I ruled out
every software change I made — `defaults.parm` by rebuild-and-test, `ROTATION_ROLL_180` by reading
the driver (the temp check fails at line 601, before rotation is applied at 613). The same hardware
on the same bus worked earlier the same day. **Do not start by re-reading my hwdef; start at the
bench** — power-cycle the sensor rail and check the physical I2C wiring. If it comes back, the EKF3
configuration is already correct and just needs one run to verify.

**Do not conclude "I2C IMUs don't work with ArduPilot."** `bebop`, `blue` and `disco` all ship
`IMU Invensense I2C:2:0x68`. Moving to SPI is the right *durable* answer (every Invensense hwdef
upstream uses `SPI:mpu9250`, and SPI0 is free here), but it is not a diagnosis of this fault.

**Two things Peter must do, not you:** accelerometer and compass calibration (physical rotation),
and ruling on the ~15 deg residual mounting angle.

**One thing waiting on a browser:** the upstream PR. Commit `2b804ed` on branch `pi5-board` in
`~/ardupilot` on scopenode, PR body at `linux/ardupilot-pi5/upstream-pr/PR_BODY.md`. There is no
fork at `pb-aero/ardupilot` yet and no `gh` in this fleet; pushing works once a fork exists (my Mac
key authenticates as `pb-aero`, and agent forwarding reaches the Pi's clone).


## 2026-09-11 · RETRACTION of the 2026-09-04 IMU handoff

**The advice below in the 2026-09-04 entry was wrong. Do not follow it.**

> "Do not start by re-reading my hwdef; start at the bench -- power-cycle the sensor rail and check
> the physical I2C wiring."

**The hardware is fine** `[measured]` 2026-09-11: MPU-9250 `WHO_AM_I` = 0x71, LPS22HB = 0xb1 as a
positive control, FIFO bursts up to 504 bytes return valid data including accel Z at -1 g and a
non-zero temperature matching the register. A bench session would have found nothing.

I also recorded "bus speed ruled out" and "bus contention ruled out". **Both were wrong.**
`strace` shows **4902 of 28979 I2C transactions failing with EREMOTEIO in 12 s (17%)**, the bus is
at **400 kHz** (`dtoverlay=i2c2-pi5,baudrate=400000`), and my own single-device loop at the same
1 kHz sample rate gets **0% errors** -- so it is the multi-device traffic at 400 kHz, not the part.

Full evidence and the ranked fixes: `linux/ardupilot-pi5/IMU-STALL-DIAGNOSIS-2026-09-11.md`.
Cheapest test is dropping the bus to 100 kHz, which needs Peter's say-so (boot config + reboot).

**And it matters less than it looks:** AeroNode puts the ICM-45686 on **SPI**, so this is a dev-rig
artefact, not a design problem.


## 2026-09-11 (later) · The IMU retraction, in full

Both prior entries about the IMU are wrong. **There was never a stall.** `MPU: temp reset` is one
startup line from one corrupt FIFO burst; the driver recovers as designed and the IMU delivers
gravity correctly for the rest of the run. Verified over MAVLink: `acc=(0,-43,-981)`, VIBRATION
0.02, all sensors healthy.

**The Pi has a working IMU, a working GPS (u-blox M10, 3D fix, 21 sats) and a working baro.** It can
run as a flight controller now. What it still needs from Peter is accel and compass calibration,
which needs the board physically rotated.

Do not spend another minute on the "I2C IMU problem". It does not exist.

## 2026-09-16 · AeroVault SPI NAND — what I would tell myself with no memory

**It works.** `ssh node@aeronode.local`, `/mnt/aerovault` is UBIFS on a W25N01GV. If it is not
mounted, UBI attach does not survive a reboot on its own — run `sudo bash ~/aerovault/ubi-setup.sh`,
or better, make it persistent (`ubi.mtd=0` on the kernel cmdline plus an fstab line). **That
persistence work is not done and is the obvious next task.**

**Do not "clean up" the CS delays in the overlay.** `spi-cs-inactive-delay-ns = <300000>` looks like
a mistake and is the only reason writes land. Read `linux/aerovault-spi/RESULTS-2026-09-16.md`
before touching it. The whole diagnosis is in that file, including four hypotheses of mine that were
wrong.

**The half-made decision:** the rig is flying leads with no ground plane, and the CS delay is
papering over that at a cost of ~68 KiB/s against a part rated for 104 MHz. Whether to tune the
numbers back (open 29) or fix the copper (open 30) is Peter's call and has not been made. Do not
raise the clock without re-running `~/aerovault/write-burst-bisect.sh` — 64 of 64 is the pass mark,
and anything less is silent data loss that looks like success.

**Still unanswered from the start of the session:** what AeroVault is FOR. 128 MiB is a log or a key
vault, not a recorder. Retention, write rate and power-loss behaviour were never specified, so the
UBIFS choice is Peter's stated preference rather than a derived one.

## 2026-09-16 (later) · The tuning attempt, and what it cost

Peter asked me to tune the SPI clock up from the deliberately slow 1 MHz / 300 us. **The answer is
no, and finding that out cost the W25N01GV eight of its eighteen spare blocks.**

25 MHz corrupted a 16 MiB file outright. 10 MHz passed the checksum while the kernel quietly logged
`mark PEB <n> as bad` nine times in a single pass — UBI retried elsewhere, the data came back
correct, and the test went green while the part's spare pool drained. **I should have stopped after
the 25 MHz failure instead of trying 10 MHz on the same wiring.** The bad-block count went 2 -> 10
and does not come back.

**If you are tempted to raise those numbers again: don't, not until the wiring is fixed.** And if
you do, the acceptance test is 16 MiB through `ubi-verify.sh` with `bad_blocks` and
`dmesg | grep "mark PEB"` checked either side — never the 64-page bisect, which passed at every
single setting including both failing ones.

Two process notes worth keeping. The Pi's copy of the overlay and the repo's drifted apart because I
was `sed`-ing the remote file directly — edit the repo file and copy it over, always. And
`timing-sweep.py` had a real instrument bug (erasing only the first block of a multi-block range)
that produced a confident, plausible, completely wrong `128/256`.

## 2026-10-23 (late) · Audio board layout — what I'd tell myself with no memory

**Where it stops:** footprints and board setup are committed (`f4ccdda`, `59a1a09`); the PCB holds only the
outline and 4 holes. Nothing is placed. Two blockers, both Peter's: KiCad TCC access to ~/Documents, and the
Konnect MCP reconnect (session restart). Check `open_project` reports IPC available AND the PCB editor is open
(GetOpenDocuments must not be AS_UNHANDLED) before trying the sync.

**Do NOT launch KiCad from the shell.** I did (`open -a KiCad`), and it is the likely reason it lost Documents
access. Ask Peter to launch it. osascript keystrokes are refused (no Accessibility grant) — don't try again.

**Do not edit board/project files while the KiCad project manager is open** — quit it first; it may write its
in-memory .kicad_pro over netclass edits on close. (It didn't this time; I checked. Still don't risk it.)

**Floorplan I intended (board x 100..170, y 80..130):** host J1/J2 + power (U1/U2/U3/U12, L1/L2/L7) along the
top-left edge; hub U4 centre with Y1, U5 flash and its decouplers; A2B U9 + FL1/L3-L6 + J3 (cup L) and J4 on
the right edge; codec U6 between hub and the aircraft section; aircraft section (T2/T3/T4, U10/U11, J5 panel,
J6 electret) along the bottom edge, kept apart from our ground per ruling 10; U7 bottom-port mic needs its
0.6 mm port clear on the back — no part or pour over it on B.Cu, and somewhere the enclosure exposes.

**Freerouting jar** sha256 `f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7`, 64,599,107 bytes
(matches the GitHub API size). Konnect's `check_freerouting` didn't find it at the default path — pass `jar_path`,
and Java is keg-only, so the autoroute tool may need PATH set or may fail to find java. Check before relying on it.

## 2026-10-23 (late) · Autoroute — two runs, neither imported

Board on disk = `6310987` (placed + In1 GND / In2 +3V3 planes, unrouted). Nothing imported.
Route path that works: KiCad's bundled Python (`/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`, pcbnew 10.0.3) has `ExportSpecctraDSN` / `ImportSpecctraSES`; Konnect's own `autoroute` refuses (no DSN in kicad-cli). Its `check_freerouting` passes `--version`, which opens the Freerouting GUI and hangs — don't call it.
Java: Homebrew `openjdk` (27) symlinked into `~/Library/Java/JavaVirtualMachines/`; openjdk@21 removed (Freerouting 2.5.0 needs Java 25+).
- Run 1 (In1/In2 planes, 0.6/0.8 vias): 75 unrouted, 0 violations.
- Run 2 (In2 routable, 0.5/0.25 + 0.6/0.3 vias, scratch DSN edits only): 64 unrouted, 0 violations; stalled after pass 8. Final unrouted list is dominated by **GND (89 connections), +3V3A (15), VBAT (10)** — i.e. power/ground **fanout to the plane** is failing (fanout escaped only 265/454 SMD pins), not signal congestion.
**Next idea:** pre-place GND/+3V3A stitching vias at the dense parts (hub/codec/A2B decoupling) by hand or loosen the decoupling ring spacing, then rerun; or route power by hand and let Freerouting do signals only. Importing SES must be done with KiCad closed (commit first).

## 2026-10-26 · Audio routing — autoroute plateaus at 19; the placement is the blocker

Board on disk = `c929354`: scripted plane fanout (`doc/route/fanout.py`) + Freerouting run 6, imported. 19 pads
unconnected, 0 clearance/edge/hole errors, 5 neckdowns < 0.127 mm, 10 dangling vias (route stubs).
What worked: fanout before routing (334 -> 205 unconnected, DRC 0); keep In2 a solid plane (making it routable split
+3V3 and orphaned the fanout vias); VBAT/+3V3A at 0.2 mm (at 0.3 mm Freerouting routed ZERO VBAT links: J1/U1/U2/U12
pins are 0.5 mm pitch). DSN edits are scratch-only via `doc/route/dsn_tweak.py`. A continuation pass from the routed
board got WORSE (33) — always route from the fanout commit.
Hand-check `[measured]` says the autoroute is not acceptable for the critical nets, and the cause is placement:
- BOOST_SW (U12.1 -> L7.2/D4.2) is 16 mm: U12 sits ~8 mm from L7/D4. Switch loop must be mm-scale.
- EAR_HI/EAR_RTN 75 mm each on B.Cu, T2/T3 (bottom right) -> J5 (left edge), mostly over our planes.
- A2B I2S U4 pins 59-63 <-> U9 pins 12-14 unroutable: U9's I2S side faces away from the hub.
- DAC_P/N 33 mm split across layers; A2B_LINE_P 15.6 mm/2 vias vs LINE_N 18.1 mm/0 vias.
Isolation itself is designed into the planes: both cut out x<116.8,y>96 and x<129.6,y>117.5 (aircraft corner).
Proposed to Peter: placement revision (T2/T3 near J5, U12 against L7/D4, rotate U9), then hand-route critical nets
first and Freerouting the rest.

## 2026-10-26 (late) · Audio board fully routed — how it was done and what's left

Board = `0bebb9f`: 0 unconnected, 0 DRC errors. Pipeline is scripted in `kicad/audio-board/doc/route/`:
`build.sh` (rev2 placement 4d9bbee -> U10/U11/T4 r180 + U9 cap column -> planecut -> hand-routes.json -> fanout -> DSN),
Freerouting (variant A: In2 solid plane, 0.13 clearance, 0.5/0.25 vias -> 17-18 left), `ses.py` + `dedupe.py`,
then `maze.py <board> <drc.rpt>` (A* finisher; MAZE_W=0.15 for fine-pitch leftovers), `rip.py`/`rmvia.py` for rework.
After build.sh the final state also needed: C33 -> (143.8,116.6) and a DAC/C33 re-rip (not in build.sh yet).
pcbnew 10.0.3 segfault traps: sorted() over SWIG items; Remove() then b.Zones() in the same process; removing items
while re-listing GetTracks(). Collect victims first, remove, save, os._exit(0).
Open for Peter: DAC_P 25.8 vs DAC_N 17.2 mm and A2B_BP 23.8 vs BN 13.4 mm (unmatched; harmless at audio / A2B rates
but not pretty); silkscreen tidy; datasheet fields; lib_footprint_mismatch cause; U7 bottom port still needs an enclosure hole.

## 2026-10-27 · Cup board 72/38 + flex-mic ZIFs ROUTED

Board: 0 unconnected, 0 DRC errors, schematic parity 0 (`kicad-cli pcb drc --refill-zones --schematic-parity`).
Path: Freerouting 23 left -> `doc/route/finish.sh` 7 -> `finish2.sh` 6 -> `finish3.sh` (rip all nets near U1 + ZIFs, mic
pairs first) 2 -> by hand: ripnets --local / fanout FANOUT_PADS for 1V8 pads, re-route TDM/U1_DVDD off In2 (they had
fenced a 1V8 pocket), I2S0_BCLK by rip-up with MAZE_BUDGET=15e6, finish loop -> 0.
Hand-check table in `kicad/cup-board/README.md` (PCB — 72/38 section). Weak spots: MK1 pair split F/B; I2S lines 68-90 mm
with up to 10 vias; SW1V8 7.4 mm. Placement idea NOT done (needs Peter): U1 +90 deg so mic inputs face J9/J10.
Before fab: ZIF pinout vs a real flex kit (placeholder), FH12 LCSC part, silk tidy / REF**, enclosure fit.

## 2026-10-29 · Boom electret pass-through through the cups (Peter)

Schematics `adc610e`: cup J7 6-pin (5/6 ELEC_HI/LO) + J12; audio J3 6-pin (5/6), J4 4-pin (3/4), joined to J6/K1.
Cup PCB `916fef4`: J12 = solder pads at 311 deg (Peter, no room for a GH on the outer band), Aircraft netclass added,
0 unconnected / 0 errors; parity warning J12 exclude-from-BOM (symbol flag needs eeschema — Konnect can't set it).
Audio PCB `cbe49e5`: J3/J4 swapped in place (old pins unchanged), ELEC J3<->J4 links hand-routed on the right edge
(`doc/route/elec-links.json`, locked), ELEC to J6 by maze along the top edge (~110-118 mm, over the planes, 0.5 mm
clearance only — NOT in a plane-free corridor like EAR). 0 unconnected / 0 errors.
Open: tick J12 "In BOM" off in eeschema; ELEC over the planes is RULED fine (Peter 2026-10-29, no corridor);
harness drawings for cup R (J7 3-6 from audio J4 1-4).
