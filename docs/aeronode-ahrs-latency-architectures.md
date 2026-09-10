# AHRS response time on AeroNode — three architectures, from the source

**Written:** 2026-09-10 by LIMA. **Question asked:** the theory of sensor-fusion response times of
each architecture, for an accurate AHRS. No hardware run was needed or attempted.

Every number below is read out of the ArduPilot tree at `fa7ffbd0a1` on the Pi 5 at
`192.168.10.34`, path and line given, or is marked `[gap]`. Nothing is quoted from memory.

---

## 0 · The headline, before the detail

Three things, and the first two surprise people:

1. **The EKF's fusion delay is not attitude lag.** EKF3 deliberately fuses at a *delayed horizon* —
   60 ms behind now at best, 250 ms with GPS — and then winds the answer forward to now with a
   separate output predictor. The controller never sees the horizon delay. What the delay costs is
   **correction bandwidth**, not latency.
2. **Attitude response time is set by the loop rate you choose, not by the silicon.** The output
   predictor runs once per main loop. At ArduPlane's default `SCHED_LOOP_RATE` of **50 Hz** the
   attitude is up to **20 ms** old on *any* of these architectures, including a Cortex-M7. Fix the
   rate and you fix the latency, on either platform.
3. **Where the architectures genuinely differ is jitter, and jitter costs you samples, not
   milliseconds.** The failure is not "the CM5 is 3 ms slower". It is that a userspace thread on a
   non-realtime kernel can miss the FIFO drain deadline, and a lost delta-angle sample is a
   permanent hole in an integral. That is a correctness difference, not a performance one.

---

## 1 · The chain, stage by stage

This is one code path. Both platforms run the *same* `AP_InertialSensor_Invensensev3` driver and the
*same* `AP_NavEKF3`. Only stages 2 and 5 differ.

### Stage 1 — inside the ICM-45686

Anti-alias filter group delay and the ODR notch. **`[gap]`** — not encoded in the driver; it needs
TDK **DS-000563 rev 1.0**, which is the datasheet the driver itself cites
(`AP_InertialSensor_Invensensev3.cpp`). Typically sub-millisecond for this class, but do not carry a
typical figure into a budget: fetch it.

What *is* in the driver, and is architecturally decisive:

| Feature | Condition in the source | Consequence |
|---|---|---|
| Base backend rate | `backend_rate_hz = 1000` for the 456xy class | 1 kHz floor |
| Fast sampling ×2…×8 | `fast_sampling = dev->bus_type() == BUS_TYPE_SPI` | **SPI only.** On I2C you are stuck at 1 kHz |
| 20-bit HiRes | `highres_sampling = dev->bus_type() == BUS_TYPE_SPI` | **SPI only**, *and* needs `HAL_INS_HIGHRES_SAMPLE` set in the hwdef |
| FIFO depth | driver comment: 2 KB ÷ 20 B = **105 HiRes samples** | this sets the real-time deadline, §3 |

**`HAL_INS_HIGHRES_SAMPLE` defaults to `0`** (`AP_InertialSensor_Backend.h:33`) and every board that
turns it on is a **ChibiOS** board — no Linux hwdef in the tree sets it `[measured]`. It is not
platform-locked, it is simply never been switched on for Linux. The AeroNode target does not set it
either; that is a one-line addition, not a port.

**`AP_INERTIALSENSOR_FAST_SAMPLE_WINDOW_ENABLED` requires `APM_BUILD_ArduCopter`**
(`AP_InertialSensor_rate_config.h:8`). On a **plane** build the FIFO read burst is 8 samples instead
of 24 — a vehicle-type difference, not a platform one, but it narrows the drain margin in §3.

### Stage 2 — sample to FIFO read · **this is where the platforms diverge**

`register_periodic_callback(backend_period_us, read_fifo)` — `AP_InertialSensor_Invensensev3.cpp:465`.
Steady-state latency is well under one backend period, because the driver re-phases itself:
`dev->adjust_periodic_callback(periodic_handle, backend_period_us)` on every read with data.

**On the CM5 (Linux HAL)** the callback is serviced by a `PollerThread`, one per SPI bus
(`SPIDevice.cpp:322-335`), started with `AP_LINUX_SENSORS_SCHED_POLICY` = `SCHED_FIFO` and
`AP_LINUX_SENSORS_SCHED_PRIO` = **12** (`Scheduler.h:15-16`). Set that against the rest of the HAL
(`Scheduler.cpp:26-32`):

| Thread | SCHED_FIFO priority |
|---|---|
| max | 20 |
| **timer** (1 kHz) | **15** |
| **UART** | **14** |
| RCIN | 13 |
| **IMU bus poller** | **12** |
| **main flight loop** | **12** |
| IO | 10 |

The IMU reader sits **below the UART and timer threads and level with the flight loop**. Anything
the UART thread does at 100 Hz preempts the sensor read. Two threads at equal priority cannot
preempt each other, so the flight loop and the sensor that feeds it compete for the same slot.

And under it all: the box runs `PREEMPT`, **not `PREEMPT_RT`** — `6.18.39+rpt-rpi-2712 #1 SMP
PREEMPT` `[measured]` — with the `ondemand` governor on 4 cores `[measured]`. `SCHED_FIFO` on a
plain `PREEMPT` kernel does not preempt an interrupt handler or a kernel critical section, and
`ondemand` adds a frequency-ramp on wake. There is no worst-case bound to quote, by construction.

**On the H753 FMU (ChibiOS)** the same callback is driven from a hardware timer with DMA'd SPI, in a
thread above the main loop, with no userspace scheduler and no kernel underneath. Jitter is
microseconds and it is *bounded*.

### Stage 3 — driver accumulation · **jitter-immune, and this is why Linux works at all**

`accumulate_samples()` / `accumulate_highres_samples()` integrate each FIFO sample into a
delta-angle and delta-velocity using **the sensor's own sample interval**, with coning correction
applied per sample. The wall-clock moment the batch was collected does not enter the integral.

**So a late FIFO read does not corrupt attitude.** It delays it and it timestamps it later. This is
the single most important reason ArduPilot on Linux produces a usable AHRS at all, and it is worth
being precise about, because the intuition "a jittery OS means a wrong attitude" is wrong in the
mechanism. Jitter hurts through §3's two specific doors, not through the integral.

### Stage 4 — EKF3 downsample, prediction, and the delayed fusion horizon

`AP_NavEKF3_Measurements.cpp:453-507`. Samples accumulate until
`delAngDT >= EKF_TARGET_DT - dtIMUavg/2`, or are forced out at `2 × EKF_TARGET_DT`.
`EKF_TARGET_DT = 0.012 s` — **12 ms** (`AP_NavEKF3_core.h:55-56`). So:

```
dtEkfAvg = MAX(1 / loop_rate_hz, 0.012)      AP_NavEKF3_core.cpp:35-36
```

**State prediction therefore runs at the loop rate, capped at ~83 Hz** — and at ArduPlane's default
50 Hz loop it is 50 Hz, not 83.

The fusion horizon (`AP_NavEKF3_core.cpp:41-88`):

```
maxTimeDelay_ms   = MAX(EK3_HGT_DELAY, magDelay_ms, [tasDelay_ms], [GPS lag ≤ 250], 12)
imu_buffer_length = maxTimeDelay_ms / 12 + 1
```

with `EK3_HGT_DELAY` defaulting to **60 ms** (`AP_NavEKF3.cpp:262`), `magDelay_ms` a compile-time
**60 ms** and `tasDelay_ms` **100 ms** (`AP_NavEKF3.h:491-492`). Observations are fused against
`imuDataDelayed` — the state as it was `maxTimeDelay_ms` ago. So the filter always runs 60 ms behind
reality at best, 250 ms behind with a laggy GPS, and buffers 6 to 21 IMU frames to do it.

**That is deliberate and it is not lag.** It is how EKF3 fuses measurements at their true time of
validity instead of pretending they are current.

### Stage 5 — output prediction · what the controller actually reads

```c
    }                       // end of  if (runUpdates)
    // Wind output forward from the fusion to output time horizon
    calcOutputStates();
```

`AP_NavEKF3_core.cpp:714-717` — `calcOutputStates()` is **outside** the `runUpdates` block. It runs
on **every** `UpdateFilter()` call, which is every main loop, using the freshest `imuDataNew`, and it
corrects itself with a complementary filter against the delayed EKF state
(`quatErr = stateStruct.quat / outputDataDelayed.quat`, line 930).

**Two decoupled rates, and they are the whole answer:**

| | Rate | Set by |
|---|---|---|
| Fusion + covariance prediction | `min(loop_rate, 83 Hz)` | `EKF_TARGET_DT` = 12 ms |
| **Attitude delivered to the controller** | **the full main loop rate** | `SCHED_LOOP_RATE` |

---

## 2 · The three architectures, budgeted

**Attitude age at the controller** ≈ stage 1 + stage 2 + up to one loop period. Stage 4's horizon
does not appear; stage 5 removes it.

| | **A · ArduPilot on the CM5** | **B · ArduPilot on the H753 FMU** | **C · FMU flies, CM5 consumes attitude** |
|---|---|---|---|
| IMU | ICM-45686, SPI | ICM-42688 **+ BMI088** | as B |
| Backend rate | 1 kHz, ×8 = 8 kHz on SPI | same driver, same rates | same |
| Reader | `PollerThread`, `SCHED_FIFO` **12** | HW timer + DMA, above main | as B |
| Preemptible by | UART(14), timer(15), RCIN(13), any IRQ, kernel section, PCIe/Hailo DMA, `ondemand` ramp | higher-priority ISRs only | as B |
| Jitter bound | **none — `PREEMPT`, not `PREEMPT_RT`** | µs, bounded | as B |
| Stage 2 latency | ~62 µs at 8 kHz + unbounded tail | ~62 µs + µs | as B |
| Loop rate, plane default | **50 Hz → 20 ms** | **50 Hz → 20 ms** | as B |
| Loop rate, tuned | 400 Hz → 2.5 ms, if scheduling allows | 400 Hz → 2.5 ms, routine | as B |
| **Attitude age, plane default** | **~20 ms** | **~20 ms** | **~20 ms + stream interval** |
| **Attitude age, tuned** | **~2.6 ms + jitter tail** | **~2.6 ms** | **~2.6 ms + stream interval** |
| EKF cores / voting | **1 IMU → no lane voting** | 2 IMUs → 2 cores, `EK3_IMU_MASK` | 2 cores on the FMU |

### Architecture C has a hard ceiling that is not a tuning matter

**ArduPilot has no MAVLink IMU input.** There is no path by which the CM5 fuses the FMU's raw
inertial data into its own EKF3 — it can only receive a finished attitude. So in architecture C the
CM5's "AHRS" *is* the FMU's AHRS, resampled at the ATTITUDE stream rate, and its response time is
architecture B's plus one stream interval. At a typical 10–50 Hz stream that stream interval
(20–100 ms) **dominates every other term in this document**.

The FMU sketch has a LAN8742A RMII PHY, so the transport itself is sub-millisecond. The transport is
not the problem; the stream rate is. If architecture C is chosen, the number to argue about is the
ATTITUDE stream rate, and nothing else on this page.

---

## 3 · What actually degrades AHRS accuracy — the two doors jitter comes through

Stage 3 established that a *late* sample is harmless. These are the two paths by which platform
jitter becomes attitude error, and both are cliffs rather than slopes.

### Door 1 — FIFO overflow, i.e. a lost sample

The 45686's FIFO holds **105 HiRes samples** (driver comment,
`AP_InertialSensor_Invensensev3.cpp:198-202`). That is a hard deadline on the reader thread:

| Backend rate | FIFO full after | The Linux thread must be scheduled within |
|---|---|---|
| 1 kHz (I2C, or SPI with fast sampling off) | 105 ms | comfortable |
| 4 kHz (×4) | 26 ms | tight under load |
| **8 kHz (×8, SPI + HiRes)** | **13 ms** | **this is a real-time deadline on a `PREEMPT` kernel** |

Overflow sets `need_reset` and the driver resets the FIFO. A delta-angle sample lost this way is a
**permanent hole in an integral** — it is not smoothed, interpolated or recovered, and the attitude
error it leaves does not decay until the magnetometer and gravity references pull it back over the
mag fusion timescale.

**Note the perverse incentive:** the faster you sample to improve vibration rejection, the shorter
your scheduling deadline becomes. 8 kHz fast sampling buys the best anti-alias margin *and* the
tightest real-time requirement, at the same time. On architecture B that trade is free. On
architecture A it is the central engineering risk.

This is also the failure family the Pi 5 dev rig already sat in — a FIFO returning zeros and
resetting forever (`linux/ardupilot-pi5/RESULTS-2026-09-04.md`). That instance was never traced to
scheduling and probably was not scheduling; the point is that the symptom of a starved reader and
the symptom of a broken bus are the same line of console output.

### Door 2 — `dtNow` clipping feeds the filter a wrong timestep

`AP_NavEKF3_Measurements.cpp:496`:

```c
ftype dtNow = constrain_ftype(0.5f*(delAngDT + delVelDT), 0.5f*dtEkfAvg, 2.0f*dtEkfAvg);
```

If a downsampled frame arrives with an interval outside **½× to 2×** nominal, the EKF is handed a dt
that is *not* the dt the data was taken over. That is a direct jitter-to-attitude-error path, and it
is silent. At a 50 Hz loop (`dtEkfAvg` = 20 ms) the window is 10–40 ms — wide, forgiving, and one
of the reasons a low loop rate is *more* tolerant of a jittery host. At 400 Hz (`dtEkfAvg` = 12 ms,
floored by `EKF_TARGET_DT`) the window is 6–24 ms.

**So raising `SCHED_LOOP_RATE` on the CM5 to cut latency simultaneously tightens both cliffs.** That
is the honest shape of architecture A: latency and jitter tolerance trade against each other, and
the trade is not present on architecture B.

### The other two, which are not about timing at all

- **Vibration and aliasing.** This is the dominant AHRS error source in real ArduPilot airframes,
  and the defence is fast sampling — which needs **SPI** (§1) and, for 20-bit,
  `HAL_INS_HIGHRES_SAMPLE` in the hwdef. AeroNode has the IMU on SPI, so the defence is available;
  the hwdef does not yet claim it.
- **One IMU means no vote.** The CM5 block diagram carries a single ICM-45686. EKF3's redundancy
  model is multiple cores over multiple IMUs (`EK3_IMU_MASK`) with lane affinity and voting; with
  one IMU there is nothing to vote against and an undetected sensor fault is an undetected attitude
  fault. The FMU sketch carries **ICM-42688 + BMI088** — two parts, two dies, two buses. For
  *integrity* rather than *latency*, that is the strongest argument on this page for architecture B,
  and it is unrelated to which chip runs the maths.

---

## 4 · What this means for AeroNode, concretely

**Latency is not the reason to choose between A and B.** At plane defaults all three architectures
deliver ~20 ms attitude and the difference between them is under 1 ms. Anyone who tunes
`SCHED_LOOP_RATE` to 400 Hz gets ~2.6 ms on either. If someone argues architecture on response time
alone, the number they are actually arguing about is a parameter.

**The real differences, in the order they matter:**

1. **Integrity — one IMU vs two.** No amount of platform tuning fixes a single-sensor AHRS.
2. **Bounded vs unbounded jitter, against a 13 ms deadline at 8 kHz.** Architecture A can be made
   good (see below) but cannot be made *bounded* without a different kernel.
3. **Everything else the CM5 is doing.** Hailo 8L inference over PCIe, 8-lane I2S audio, NAND
   writes — all on the same RP1 fabric, all generating interrupt and DMA load, all contending with a
   priority-12 sensor thread. Architecture A puts the flight-critical path and the payload on one
   scheduler; B does not.

**If architecture A is kept — the cheap wins, all in software:**

- `PREEMPT_RT` kernel, or failing that: `performance` governor (not `ondemand`), CPU affinity or
  `isolcpus` for the sensor and main threads, and a hard look at raising `AP_LINUX_SENSORS_SCHED_PRIO`
  above the UART thread's 14 — the current ordering, sensor below UART, is hard to defend for a
  flight controller.
- Add `HAL_INS_HIGHRES_SAMPLE` to the AeroNode hwdef to get the 20-bit path the part supports.
- Keep the IMU on SPI. On I2C the driver silently drops to 1 kHz, 16-bit, no fast sampling — three
  losses from one wiring choice, none of them reported as an error.
- Raise `SCHED_LOOP_RATE` deliberately, knowing it tightens both cliffs in §3, and measure the
  FIFO-reset rate before and after.

## 5 · Limits of this analysis

- **It is a source analysis, not a measurement.** Every latency here is a rate or a deadline read
  out of the code. Real jitter distributions on a CM5 under Hailo load are not derivable from a desk
  and I have not measured them. The measurement that would settle it is a `cyclictest` under
  representative payload load, plus ArduPilot's own `PM` log message (`SCHED_LOOP_RATE` overruns and
  max loop time) with and without inference running.
- **Stage 1 is an unclosed `[gap]`.** The ICM-45686's AAF group delay wants DS-000563.
- **No number here came from a CM5.** The kernel, governor and core count are from the Pi 5 at
  `192.168.10.34`; the CM5 will differ in load, not in mechanism.
- **The ATTITUDE stream rate for architecture C is `[assumed]` at 10–50 Hz** from typical ArduPilot
  practice, not read from a config. If architecture C is on the table, that one number deserves its
  own check, because §2 shows it dominates everything else.

---

## 6 · Appendix, added 2026-09-10 — LSM6DSV as AeroNode's second IMU

Raised by Peter after reading §3's "one IMU means no vote". It closes that gap, and it closes it on
architecture A, which was the architecture the integrity argument counted against.

**All facts below read out of `libraries/AP_InertialSensor/AP_InertialSensor_LSM6DSV.{h,cpp}` at
`179ae0ab03`, confirmed an ancestor of `origin/master` — this is upstream, not a local patch.**

### It fits the CM5 pin map with no new pins

The CM5 sheet already has **SPI3 and SPI4**, each with one chip select. So:

| Bus | Part |
|---|---|
| SPI3 | ICM-45686 — the high-resolution lane (20-bit HiRes, 4000 dps, 32 g) |
| SPI4 | **LSM6DSV16X/32X** — the dissimilar-redundancy lane |
| I2C1 | RM3100 compass at 0x20, BMP581, BME690, ADS1115 |

RM3100 over I2C is a shipping configuration upstream (`COMPASS RM3100 I2C:0:0x20 false ...`
`[measured]`), so moving it off SPI to free SPI4 costs nothing. **This resolves the §1 bus-map gap
and the redundancy gap in the same stroke, on pins that already exist.** It is a proposal, not a
schematic — Peter's call.

Then `INS_MAX_INSTANCES 2` and `EK3_IMU_MASK = 3` gives EKF3 **two cores with lane affinity and
voting** — "a separate instance of EKF3 will be started for each IMU selected" (`AP_NavEKF3.cpp:433`).
Two cores is roughly double the EKF CPU and memory. On four CM5 cores that is cheap; on an H7 it is
the thing that constrains the count.

### Why a dissimilar pair beats a matched pair

Two Invensense parts share failure modes — the FIFO-returns-zeros mode the Pi 5 dev rig sat in is
one, and a voting scheme cannot detect a fault both lanes have. ST and TDK share nothing: different
die, different register map, different FIFO architecture (LSM6DSV uses **tagged words**, one word
per gyro *or* accel sample, against Invensense's fixed-layout packets). That is genuine common-mode
fault detection rather than the appearance of it.

### What the driver actually gives you

| | ICM-45686 | LSM6DSV16X / 32X |
|---|---|---|
| Base backend rate | 1000 Hz | 1000 Hz (`LSM6DSV_DEFAULT_BACKEND_RATE_HZ`) |
| Fast sampling ceiling | ×8 → 8000 Hz | ×8 → **8000 Hz**, via HAODR mode-1 |
| Fast sampling gate | `bus_type() == BUS_TYPE_SPI` | same gate |
| Resolution | **20-bit** HiRes (SPI + hwdef define) | **16-bit only** — no HiRes path exists |
| Gyro full scale (driver default) | 4000 dps | **2000 dps** (4000 dps is in the register map; the driver picks 2000) |
| Accel full scale (driver default) | 32 g | **16 g** (32 g on the 32X variant only) |
| FIFO drain per callback | unbounded `while (n_samples > 0)` | **capped at 32 words** (`LSM6DSV_FIFO_MAX_DRAIN_WORDS`), burst 16 |

**The bounded drain is a point in LSM6DSV's favour on a jittery host**, and it is the opposite of
what you would guess. `poll_data()` calls `drain_fifo()` once and it removes at most 32 words, so
its worst-case execution time is bounded and the sensor thread cannot monopolise its slot. Recovery
is still quick: at 8 kHz, 2 words arrive per 125 µs callback while 32 leave, a net ~240 words/ms.
The Invensense driver drains everything in one invocation — faster catch-up, unbounded execution
time. For a `SCHED_FIFO` thread at priority 12 the bounded one is the better citizen.

### Three things to get right before ordering

1. **The hwdef keyword is `LSM6DSV`; the silicon must not be.** `check_whoami()` accepts WHO_AM_I
   **0x70** — shared by **LSM6DSV16X** and **LSM6DSV32X**, disambiguated by CTRL8 bit 2 after reset —
   or the **LSM6DSK320X** id. Nothing else returns true. **A plain LSM6DSV is not in the enum.**
   Specify 16X or 32X (or DSK320X) on the BOM.
2. **SPI is not a preference here, it is a type constraint.** `probe()` takes
   `AP_HAL::OwnPtr<AP_HAL::SPIDevice>`, not a generic `Device`, and every one of the six hwdefs that
   use it declares `SPI:`. Unlike the ICM-45686 — where I2C compiles and silently degrades to 1 kHz
   16-bit — I2C here simply cannot be wired.
3. **`[gap]` FIFO depth is not encoded in the driver**, so the overflow deadline computed for the
   45686 in §3 (105 HiRes samples → 13 ms at 8 kHz) has no LSM6DSV counterpart yet. It wants the ST
   datasheet before either lane's real-time budget is signed off.

### One precedent, read carefully

BlueRobotics **navigator** — an `AP_HAL_Linux` hwdef — declares both
`IMU Invensense SPI:icm20602` and `IMU LSM6DSV SPI:lsm6dsv`. That **is** upstream proof that this
driver runs on the Linux HAL over SPI.

It is **not** proof of a working two-IMU Linux setup, and it would be easy to claim that it is. Both
entries point at `LINUX_SPIDEV ... 1 2 ...` — **the same bus and the same subdev** `[measured]`. They
are board-revision alternates that probing disambiguates, not a simultaneous pair. AeroNode's SPI3
and SPI4 are genuinely separate buses with separate chip selects, so AeroNode would be a stronger
configuration than the precedent, not an equal one — and correspondingly less well trodden.
