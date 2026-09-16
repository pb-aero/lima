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
