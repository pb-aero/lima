# AHRS data paths — UDP/pymavlink vs direct in-process API

**Date:** 2026-09-11 · **Agent:** LIMA · **Asked:** run ArduPilot natively and compare getting AHRS
data via pymavlink over UDP against direct API calls.

**Outcome: the comparison could not be completed, and the reason is worth more than a partial
number would have been.** What follows is what was established, what was refuted, and the one
thing that blocks it.

---

## 1 · Native, not SITL — settled by reading the tree

| | `AP_HAL_Linux` | `AP_HAL_SITL` |
|---|---|---|
| transport backends | `UARTDevice.cpp`, `UDPDevice.cpp`, `TCPServerDevice.cpp` behind `SerialDevice.h`, driven by `UARTDriver.cpp` | one self-contained `UARTDriver.cpp`; **none of those files exist** |

UDP-vs-anything *is* the transport stack, so SITL would measure a code path that does not exist on
AeroNode. The SITL build was abandoned. `[measured]`

## 2 · Plumbing facts, all `[measured]`, all of which cost time to find

- **The stream-rate parameters are `MAVn_*`, not `SRn_*`.** `SR0_EXTRA1` does not exist on this
  build; `MAV1_EXTRA1` does, and its default is **1.0**, which is exactly the 1 Hz ATTITUDE trickle
  that made the first three attempts look broken. 956 parameters were enumerated to find it.
- **`--serial0 udp:host:port` is one-way.** It makes ArduPilot a *sender* to a fixed address;
  replies go to an ephemeral port nothing is listening on, so no parameter can ever be set. Use
  **`udpin:`** on ArduPilot and **`udpout:`** on the client.
- **A `udpout` client must transmit first.** pymavlink's `wait_heartbeat()` only receives, so
  ArduPilot's `udpin` never learns the client address. Send a `heartbeat_send()` first.
- **Parameter writes need `MAV_PARAM_TYPE_REAL32`.** `INT16` is silently ignored.
- **Lua scripting is compiled into the Linux build** (`SCR_ENABLE` exists), so an in-process
  direct-API consumer is available without forking ArduPilot.
- **`SCHED_LOOP_RATE` reads back as 50** — an independent confirmation of the ArduPlane default
  used throughout `docs/aeronode-ahrs-latency-architectures.md`.

## 3 · The blocker: ArduPilot will not run without an IMU

This was the hopeful idea — for a *data path* comparison the attitude values need not be valid, so
the generic `linux` target with `HAL_INS_NONE` should serve. It does not.

```
Config Error: Baro: unable to initialise driver     <- stock linux target
Config Error: INS:  unable to initialise driver     <- after adding a real baro
```

I built a dedicated `ahrsbench` target (`include ../linux/hwdef.dat` + the real LPS22HB at
`i2c-2:0x5c`) to get past the first error. It simply reported the next one. **ArduPilot sits in a
config-error loop, never runs its scheduler and never starts scripting.**

### Retraction of a number I measured earlier the same day

Before finding this, I measured the UDP path and got: 50 Hz requested, **34.2 Hz delivered**,
inter-arrival p50 30 ms / p99 70 ms / max 80 ms, delivery latency p50 5 ms / p99 10 ms.

**Those numbers are withdrawn.** They were taken while ArduPilot was in the config-error loop — it
still services MAVLink there so a GCS can see the error, which is precisely why the measurement
looked plausible. It was timing an error loop, not a flight stack. A number that looks reasonable
from a rig that is not doing the thing you think it is doing is worse than no number.

## 4 · Hypotheses tested and refuted on the IMU stall

The stall is `MPU: temp reset IMU[0] <n> 0` — the driver uses each FIFO sample's temperature field
as a corruption canary (`AP_InertialSensor_Invensense.cpp:595`), so this reads *"the temperature
register is fine but the FIFO sample carries zero"*.

| Hypothesis | Test | Verdict |
|---|---|---|
| Dead sensor / bad wiring (my own 2026-09-04 handoff) | `WHO_AM_I` 0x71; LPS22HB 0xb1 as positive control; manual FIFO burst shows accel Z = −1 g and non-zero temp | **refuted** |
| I2C read length limit | burst sweep 14 → **504 bytes**, all valid | **refuted** |
| Marginal 400 kHz signalling | 100 kHz: failures/second **406 vs 409** — invariant across a 4× clock change | **refuted** |
| FIFO overflow from 1 kHz sampling | patched driver to `SMPLRT_DIV=4` (200 Hz) on I2C; verified live by reading back `0x04`; **`FIFO_COUNT` reads `0x0000` — the FIFO is EMPTY, not overflowing**; error rate still 408/s | **refuted** |
| AK8963 compass on the MPU aux bus | `COMPASS_ENABLE 0` → errors fall 406/s → **69/s (83%)**, but the IMU still stalls; removing the `COMPASS` line from the hwdef entirely — still stalls | **refuted as the cause** (but it *is* 83% of the I2C errors, worth fixing separately) |

**The one invariant:** `EREMOTEIO` failures run at **~408 per second** across every variable
changed — 400 kHz and 100 kHz bus, 1 kHz and 200 Hz sampling, compass present and absent. A rate
that refuses to move is a strong clue and I have not yet explained it.

**Still open.** The FIFO being *empty* while `FIFO_EN=0xf8` and `USER_CTRL=0x40` are correctly
programmed is the thread to pull next: something is stopping the FIFO filling rather than
corrupting what is in it.

## 5 · What I would do next, and what I would not

**Would not:** spend more time on this bench's I2C MPU-9250. Five hypotheses are dead, the fault is
on a bus **AeroNode does not use**, and the driver gates both fast sampling and 20-bit HiRes on
`bus_type() == BUS_TYPE_SPI` anyway.

**Would:** put any SPI IMU on the Pi — an ICM-42688 or ICM-45686 breakout on SPI0, which is free.
That is the AeroNode architecture, it sidesteps the entire fault, and it unblocks the UDP-vs-direct
comparison in one step. The measurement scripts are written and working (`~/ahrs/` on the box:
`sideA_udp.py` for the MAVLink/UDP path, `scripts/ahrs_probe.lua` for the in-process path).

## 6 · State the box was left in

- `~/ardupilot` tree: experimental driver patch **reverted**, `pi5/hwdef.dat` compass line
  **restored**. The only addition is the new `libraries/AP_HAL_Linux/hwdef/ahrsbench/` target.
  (The pre-existing `ROTATION_ROLL_180` edit in `pi5/hwdef.dat` was there before this session and
  is left alone.)
- `/boot/firmware/config.txt`: restored to `baudrate=400000`, byte-identical to the backup.
- No processes left running.
