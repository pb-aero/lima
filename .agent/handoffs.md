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
