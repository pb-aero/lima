# AHRS data path: pymavlink over UDP vs direct in-process API — measured

**Date:** 2026-09-11 · **Agent:** LIMA
**Rig:** `Raspberry Pi 5 Model B Rev 1.1`, machine-id `49cc4b68da3b4dfd9d10cc78207fe9eb`, at
192.168.0.99. Native `--board=pi5`, `AP_HAL_Linux`, **stock driver — no stub**. Kernel
`6.18.39+rpt-rpi-2712`, `PREEMPT` (not RT), `ondemand` governor.
**Live AHRS:** EKF3 IMU0 initialised, tilt alignment complete, origin set, u-blox M10 3D fix.
`SCHED_LOOP_RATE = 50`.

Both consumers measured **simultaneously against one flight stack**, so the comparison is paired —
same AHRS, same instants, differences are the data path alone.

---

## Results

### Side A — pymavlink over UDP loopback (ATTITUDE)

Stream rates verified set, not assumed: all six `MAV1_*` groups acked at 50.

| | |
|---|---|
| delivered | **40.04 Hz** (n = 1600 over 40.0 s) |
| inter-arrival | p50 **20.00 ms** · p90 **40.01 ms** · p99 40.05 · max 40.07 |
| delivery latency | p50 **0.05 ms** · p90 0.07 · p99 0.14 · **max 0.28 ms** |

### Side B — direct in-process API (Lua `ahrs:get_roll_rad()` etc.)

| | |
|---|---|
| rate | **49.99 Hz** — every loop, eight consecutive 5 s windows |
| interval | p50 **20.00 ms**, min 19 ms, max 21 ms |
| dropped cycles | **none observed** |

---

## What this actually says, and it is not what I expected

**The UDP transport is effectively free.** 0.05 ms median, **0.28 ms worst case** over 40 seconds.
Serialisation, socket, kernel, and Python parse together cost less than a third of a millisecond.
Anyone choosing an architecture to avoid MAVLink *latency* on loopback is optimising something that
is already three orders of magnitude below the loop period.

**The real cost of the MAVLink path is dropped cycles, not delay.** 40 Hz against the loop's 50 Hz:
the p50 interval is exactly one loop (20 ms), but **p90 is two loops (40 ms)**. Roughly one update
in five is skipped, because GCS_MAVLINK streams are scheduled in the loop's spare time and at
50 Hz-on-a-50 Hz-loop they cannot always fit.

So the penalty is **completeness and jitter**: a consumer on UDP misses ~20% of attitude updates,
and when it does, the data it acts on is 40 ms old rather than 20 ms. The in-process reader gets
every cycle at 20.00 ms ± 1 ms.

**This confirms, by measurement, the claim made from source analysis in
`docs/aeronode-ahrs-latency-architectures.md` §0:** attitude response time is set by
`SCHED_LOOP_RATE`, not by the transport. The transport contributes 0.05 ms; the loop contributes
20 ms; MAVLink's scheduler then throws away one update in five.

## Recommendation for the AeroNode app layer

- **For anything that merely observes** — telemetry, logging, Hailo inference context, the CO/
  environmental layer — **UDP/MAVLink is entirely adequate.** Sub-millisecond transport, and a
  missed frame in five does not matter when the consumer runs slower than 50 Hz anyway.
- **For anything in a control path, or that must not miss a cycle**, use the in-process API. The
  gap is not latency, it is the 20% of cycles MAVLink drops.
- **If you stay on MAVLink and want every cycle**, raise `SCHED_LOOP_RATE` above the stream rate so
  the streams have slack — e.g. loop at 100 Hz for a 50 Hz ATTITUDE stream — rather than requesting
  a stream rate equal to the loop rate. Note §3 of the architecture doc: raising the loop rate
  tightens the FIFO-overflow and `dtNow`-clipping margins, so this is a trade, not a free win.

## Honest limits of this measurement

- **Loopback only.** Both endpoints on one host. A real network link adds its own latency and loss;
  nothing here speaks to that.
- **Latency resolution.** `time_boot_ms` has 1 ms granularity, and the figures are offset-corrected
  against the run minimum. Sub-millisecond medians are therefore **at the resolution floor** — the
  honest reading is "no delay beyond timestamp quantisation was observable", not "the latency is
  exactly 0.05 ms".
- **Idle bench.** No Hailo inference, no 8-lane audio, no storage load. The sched-tail harness in
  `linux/ardupilot-cm5/sched-tail/` exists to characterise exactly that, and has not been run
  against this configuration.
- **Lua measures its own call interval**, which is the rate at which an in-process consumer can
  obtain attitude. It does not include whatever that consumer then does with it.
- **40 seconds.** Long enough to see the 20% drop pattern clearly; not long enough to characterise a
  tail.
