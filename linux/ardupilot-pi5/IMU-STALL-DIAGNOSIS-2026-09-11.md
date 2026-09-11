# The Pi 5 IMU FIFO stall — diagnosed, and the 2026-09-04 handoff was wrong

**Date:** 2026-09-11 · **Agent:** LIMA
**Box:** `Raspberry Pi 5 Model B Rev 1.1`, machine-id `49cc4b68da3b4dfd9d10cc78207fe9eb`,
reached at **192.168.0.99** (`aeronode.local`, tailnet `100.64.0.1`). Kernel
`6.18.39+rpt-rpi-2712`.

## Retraction first

`.agent/handoffs.md` (2026-09-04) told the next session:

> "**Do not start by re-reading my hwdef; start at the bench** — power-cycle the sensor rail and
> check the physical I2C wiring."

**That was wrong, and it would have cost someone a bench session.** The hardware is fine. It also
recorded "bus speed ruled out by measurement" and "bus contention ruled out" — the evidence below
points squarely at both.

## What the sensor actually does — all `[measured]` 2026-09-11

| Test | Result |
|---|---|
| `i2cdetect -y 2` | `0x0c` (AK8963), `0x5c` (LPS22HB), `0x68` (MPU-9250) all present |
| MPU-9250 `WHO_AM_I` (0x75) | **`0x71`** — correct |
| LPS22HB `WHO_AM_I` (0x0f) | `0xb1` — **positive control**: the scan itself works |
| Direct `TEMP_OUT` register read | `0x07bc` = 1980 — plausible |
| Manual FIFO burst, 28 B | accel Z `0xf830` ≈ **−1 g (gravity)**, temp `0x07c1` = 1985 — **non-zero and matching the register** |
| Burst read length sweep | 14, 28, 56, 112, 126, 140, 168, 224, 252, 256, **504 bytes** — all valid data, no truncation |

So: the chip is alive, identifies correctly, fills its FIFO with physically sensible data, and long
burst reads over I2C work. **Nothing at the bench is broken.**

## What ArduPilot's config looks like — also fine

Dumped from the part while `arduplane` sat in its reset loop:

```
0x19 SMPLRT_DIV  = 0x00   1 kHz
0x1a CONFIG      = 0x41   FIFO_MODE=1, DLPF_CFG=1 (184 Hz)
0x1b GYRO_CONFIG = 0x18   2000 dps
0x1c ACCEL_CONFIG= 0x18   16 g
0x23 FIFO_EN     = 0xf8   TEMP + GYRO(xyz) + ACCEL  -> 14-byte samples
0x6a USER_CTRL   = 0x40   FIFO enabled
0x6b PWR_MGMT_1  = 0x03   PLL, awake
0x75 WHO_AM_I    = 0x71
```

`FIFO_EN = 0xf8` matches `MPU_SAMPLE_SIZE 14` exactly, and `FIFO_COUNTH/L` read `0x000e` — one
sample queued. **ArduPilot programs the part correctly and the FIFO is filling.**

## The actual fault

`strace -e trace=ioctl` on a 12-second run:

```
I2C_RDWR total  : 28979
failed EREMOTEIO:  4902      <- 17%
succeeded       : 24077
```

**Seventeen percent of ArduPilot's I2C transactions fail with `EREMOTEIO` (Remote I/O error).**
That is a real bus-level failure — a NAK or lost arbitration — not a silent no-op and not a
driver bug.

And the canary that reports it: `AP_InertialSensor_Invensense.cpp:595` uses **each FIFO sample's
temperature field as a FIFO-corruption detector** —

```c
int16_t t2 = int16_val(data, 3);        // bytes 6,7 = TEMP_OUT
if (!_check_raw_temp(t2)) { ... debug("temp reset IMU[%u] %d %d", ..., _raw_temp, t2); }
```

so `MPU: temp reset IMU[0] 1939 0` means *the reference temperature register reads 1939, but the
sample pulled from the FIFO carries 0*. Reading `FIFO_R_W` when the FIFO has nothing valid returns
zeros — confirmed below.

## Why my reads succeed and ArduPilot's do not

A sustained single-device read loop of my own, same bus, same 14-byte FIFO reads:

| Rate | Transfers | EREMOTEIO | Zero-temp samples |
|---|---|---|---|
| 50 Hz | 300 | **0 (0.0%)** | 0 |
| 500 Hz | 3000 | **0 (0.0%)** | 24 |
| 1000 Hz | 6001 | **0 (0.0%)** | 24 |

**Zero bus errors at ArduPilot's own sample rate.** The differences that remain:

1. **Traffic volume.** ArduPilot ran ~2 400 transactions/second; my loop ran 1 000.
2. **Device count.** ArduPilot interleaves the MPU-9250 (`0x68`), the LPS22HB baro (`0x5c`) and the
   AK8963 compass (`0x0c`) on the same bus. My loop touched one address.
3. **Bus speed.** `/boot/firmware/config.txt` has `dtoverlay=i2c2-pi5,baudrate=400000` — **400 kHz**.

The zero-temp column is the second half of the mechanism: **reading the FIFO when it holds nothing
valid returns zeros**, ~0.4% of the time even in my clean loop. Combine that with a 17% transaction
failure rate and the driver's corruption canary fires continuously and never lets the IMU finish
initialising.

**Diagnosis: marginal 400 kHz shared-bus signalling under ArduPilot's multi-device traffic.** Not a
dead sensor, not the rotation, not `defaults.parm`, not the hwdef.

## What to try, cheapest first

1. **Drop the bus to 100 kHz** — `dtoverlay=i2c2-pi5,baudrate=100000` in
   `/boot/firmware/config.txt`, reboot. If the stall clears, the diagnosis is confirmed and the
   dev rig is usable again. **Needs Peter's say-so: it edits boot config and reboots the box.**
2. **Check the pull-ups and wire length** on the i2c-2 run. 400 kHz is unforgiving of bus
   capacitance; this is the physical correlate of the same fault.
3. **Move the IMU to SPI** — which is the durable answer and the one AeroNode already takes.

## Why this matters less than it looks for AeroNode

**AeroNode puts the ICM-45686 on SPI, not I2C.** This entire failure mode is an artefact of the dev
rig's I2C wiring. It blocks *this bench* from running a native flight stack; it does not implicate
the AeroNode design. It is also a reminder of a rule already in `MEMORY.md`: the driver's own
`fast_sampling` and 20-bit `highres_sampling` are both gated on `bus_type() == BUS_TYPE_SPI`, so
I2C was never the right home for a flight IMU here.


---

# CORRECTION, same day — the 400 kHz diagnosis above is WRONG

Peter authorised the 100 kHz test. **It refuted my own conclusion.** Leaving the original text
above intact rather than editing it, because the reasoning error is the useful part.

## What the test showed

Identical 12-second straced runs of `build/pi5/bin/arduplane`, same box, only the bus clock changed:

| Bus clock | I2C transfers | EREMOTEIO | % | **failures/second** |
|---|---|---|---|---|
| 400 kHz | 28 979 | 4 902 | 17.0% | **409** |
| 100 kHz | 14 326 | 4 871 | 34.0% | **406** |

**The absolute failure count barely moved — 4902 vs 4871 — while total transfers halved.** Failures
per *second* are constant at ~405 across a 4x change in bus clock. Marginal signalling would scale
with clock rate; a fixed ~405/s does not. The percentage "getting worse" at 100 kHz is an artefact
of the denominator shrinking, and quoting that percentage as if it meant something would have been
a second error on top of the first.

**So it is not bus speed, and it is not signal integrity.** It is a specific transaction failing at
a fixed rate.

## What it partly is

Running with `--defaults` setting `COMPASS_ENABLE 0`:

| | failures/second |
|---|---|
| compass enabled | 406 |
| **compass disabled** | **69** |

**The AK8963 path accounts for ~83% of the I2C errors.** The pi5 hwdef declares
`COMPASS AK8963:probe_mpu9250 I2C:2:0x0c` — the compass reached through the MPU-9250's auxiliary
I2C master — and that path is failing continuously.

**But the IMU still stalls with the compass off** (`MPU: temp reset IMU[0] 2096 0`), and 69
failures/second remain. So the compass is a large contributor and *not* the root cause.

## Where the evidence actually points now

`SMPLRT_DIV = 0` with DLPF enabled gives a **1 kHz** sample rate at 14 bytes per sample —
**14 kB/s** that must be drained over a bus shared with the baro and compass. One 14-byte FIFO read
plus its register write is ~20 bytes of bus traffic; at 100 kHz that is ~2 ms per read against a
1 ms budget, so the reader **cannot** keep up. The MPU-9250's FIFO is 512 bytes and `CONFIG=0x41`
sets `FIFO_MODE=1` (stop when full).

The driver's own comment at `AP_InertialSensor_Invensense.cpp:738-749` says it already knows about
this, and resets the FIFO on I2C whenever more than 4 samples have accumulated. A reset followed by
a read before fresh data has landed returns **zeros** — and zeros in the temperature field are
exactly the corruption canary that fires. I measured that independently: my own blind read loop saw
zero-temperature samples at ~0.4% even with **0% bus errors**.

**Working hypothesis, explicitly not yet proven:** perpetual FIFO overflow-and-reset because 1 kHz
sampling exceeds what this shared I2C bus can drain — not a signalling fault at all. The test that
would settle it is instrumenting `n_samples` and the reset rate inside `_read_fifo()`, which means
a patched build, not another strace.

## State the box was left in

**Restored to `baudrate=400000` and rebooted** — byte-identical to the pre-change backup
`/boot/firmware/config.txt.bak-LIMA-20260911-101431`, verified by `diff`. 400 kHz was measurably the
better of the two, and it is how I found it.

## The lesson worth keeping

I published a causal claim — "marginal 400 kHz shared-bus signalling" — on the strength of a
**correlation between a percentage and a hypothesis I already held**, without checking whether the
absolute rate moved. The first table in this section took ten minutes and killed it. `[measured]`
was honest about each number; the *conclusion* drawn from them was not measured at all, and I
should have tagged it `[assumed]`.
