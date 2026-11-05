# AeroNode rev 0.0.2 — ArduPilot-native image, EKF out to AeroSync

**Date:** 2026-11-05 · **Agent:** LIMA · **Target:** AeroNode HW ver 0.0.2 rev 1, a Raspberry Pi
CM5108064B carrier, running **ArduPilot natively on the CM5** (aarch64, no HAT, no cross-compile).

Provenance: `[measured]` I ran it · `[repo]` it is in the code, cited · `[fetched]` from a source
I retrieved · `[derived]` reasoned, reasoning shown · **`[gap]`** not established.

---

## 1. What this is, and what it is not

This directory is the **complete board-specific definition** of the image: the ArduPilot board
target, the two mandatory upstream patches, the boot configuration, the service unit, the
bus-discovery tooling, and the EKF→AeroSync bridge with its tests.

**It is not a `.img` file.** Baking one needs a Linux host with loop devices or the board itself —
this workstation has no container runtime, no `qemu`, and no Linux builder `[measured]`, and the
bench did not answer on any of its four known addresses today `[measured]`. The bake is ~15 minutes
of mechanical work (`scripts/bake-image.sh`); the board-specific engineering is what was missing,
and that is what is here.

Two stages, in order:

| Stage | Script | Where it runs |
|---|---|---|
| 1 — make it work | `scripts/build-on-board.sh` | on the AeroNode CM5 |
| 2 — bake the card | `scripts/bake-image.sh` | Linux host, or the board |

---

## 2. The sensor set is rev 0.0.2's, and it is not what our own notes said

`[correction]` `docs/aeronode-cm5-software-rev1.md` (2026-09-10) describes the CM5 AeroNode as
**RM3100** compass + **BMP581** baro, read from the unversioned `~/aerosense/aeronode/aerosense/`
tree. The **vendor schematic** *Schematic for AeroNode HW ver 0.0.2 rev 1* carries **MMC5983MA**,
**BMP390 and BMP581**, plus BME690 `[repo: docs/aeronode-power-budget.md]`. The hwdef here follows
the schematic. The older doc is superseded on this point.

### Driver coverage — the thing that decided the effort

Checked against ArduPilot `master`, 2026-11-05 `[measured]`, by reading the drivers, not the docs:

| Part | Where it sits | ArduPilot driver | Verdict |
|---|---|---|---|
| **ICM-45686** | AeroImu island | `AP_InertialSensor_Invensensev3`, enum `ICM45686`, `WHO_AM_I` **0xE9**, 20-bit HiRes path (16384 LSB/g) | **Supported** |
| **MMC5983MA** | AeroNode, I2C | `AP_Compass_MMC5xx3`, product ID **0x30**; `AP_Compass.cpp:1248` — the source comment names MMC5983MA explicitly | **Supported** |
| **BMP581** | AeroNode, I2C | `AP_Baro_BMP581`, I2C 0x46/0x47 | **Supported** |
| **BMP390** | AeroNode, I2C | `AP_Baro_BMP388` — that driver knows **`BMP390_ID 0x60`** beside `BMP388_ID 0x50` (`AP_Baro_BMP388.cpp:28-29`) | **Supported** |
| **DAN-F10N** | AeroNode, UART0 | `AP_GPS_UBLOX`, generic UBX | **Supported** for position/velocity. `[gap]` The driver has explicit `F9` generation handling; **no F10 branch**, so F10-specific config (e.g. L5 band) is not applied. Basic solution is unaffected. |
| **ADS1115** | CO chain | `AnalogIn_ADS1115` (Linux HAL) | Supported, not a flight sensor |
| **LSM6DSV320X** | AeroImu island | — | **NOT supported.** See §5 |
| **BME690** | AeroNode | — | **Absent entirely.** Environmental sensing is never ArduPilot's job; read it from Linux instead |

**Everything EKF3 needs is covered.** That is the headline: this is a weekend of integration, not a
month of driver writing.

---

## 3. Two upstream patches are MANDATORY, and both are still unlanded

`[measured 2026-11-05]` against `ArduPilot/ardupilot` master:

```
libraries/AP_HAL_Linux/Util_RPI.cpp:62:   strncmp(entry->d_name, "soc", 4) == 0
hwdef/ directory listing:                 no 'pi5' board
```

* **`patches/0001`** — `strncmp(d_name,"soc",4)` compares 4 bytes including the NUL, so it is an
  exact match for `"soc"`, not the prefix match the surrounding code intends. Every BCM2712 kernel
  names the node `soc@107c000000`, so detection falls through to `UNKNOWN_BOARD` and
  `GPIO_RPI::init()` calls `AP_HAL::panic()` at startup. Fixed by comparing 3 characters.
  `[measured]` on a Pi 5 in September by extracting the scan into a standalone program:
  `"soc",4` → base `0x0` → `UNKNOWN_BOARD`; `"soc",3` → base `0x10` → `RPI_5`.
* **`patches/0002`** — adds `HAL_BOARD_SUBTYPE_LINUX_PI5` and the generic `pi5` board, which this
  hwdef's `CONFIG_HAL_BOARD_SUBTYPE` refers to.

`[derived, not measured]` A CM5 is the same BCM2712, so it should also yield base `0x10` → `RPI_5`.
**The one-command test is in `scripts/discover-buses.sh` step 1** — run it before building.

`scripts/build-on-board.sh patch` refuses to continue if a patch neither applies nor is already
applied, and greps for the fixed line afterwards as a positive control.

---

## 4. The hwdef, and the scar it is built around

`hwdef/aeronode-cm5/hwdef.dat` inherits **`../linux/hwdef.dat`**, deliberately — *not* `../pi5`.

`[measured 2026-09-10]` The hwdef generator **appends** sensor device lines, and `undef` only
touches `define`s. Inheriting the `pi5` board therefore pulled in the dev rig's **MPU-9250** as
`HAL_INS_PROBE1` with the real ICM-45686 appended as PROBE2 — and with `INS_MAX_INSTANCES 1`, **the
real sensor is the one that gets dropped.** `waf configure` printed `finished successfully`
throughout.

So the rule, enforced in `build-on-board.sh verify`: **read `build/aeronode-cm5/hwdef.h`, never the
exit code.** It prints `HAL_INS_PROBE_LIST`, `HAL_MAG_PROBE_LIST`, `HAL_BARO_PROBE_LIST`, and fails
the run if a foreign IMU name appears in the INS probe list.

Two other decisions worth stating:

* **The IMU is on SPI because it has to be.** `[repo]` `fast_sampling` and 20-bit
  `highres_sampling` are both gated on `bus_type() == BUS_TYPE_SPI`. On I2C you silently get 1 kHz,
  16-bit, no oversampling — and no error. The hwdef sets `HAL_INS_HIGHRES_SAMPLE 1`, which **no
  Linux hwdef upstream sets** (ChibiOS boards only, by habit not by gate).
* **The compass stays on I2C.** `[repo]` `AP_Compass_MMC5xx3` retries its product-ID read up to ten
  times with a comment that it *"fails sometimes on SPI"*.

---

## 5. `LSM6DSV320X` — a real gap, and a decision for you

The AeroImu island's second IMU is an **LSM6DSV320X**. ArduPilot's `AP_InertialSensor_LSM6DSV`
`check_whoami()` accepts exactly two values `[measured]`:

```
0x70  -> LSM6DSV16X / LSM6DSV32X   (split by CTRL8 bit2 after reset)
0x75  -> LSM6DSK320X
```

The **LSM6DSV320X reads `0x73`** `[fetched: ST AN6119, WHO_AM_I 0Fh = 0b01110011]`. It therefore
returns `false` and is never used.

And this is **not an upstream typo**: `LSM6DSK320X` and `LSM6DSV320X` are two different, both-active
ST parts `[fetched: ST product pages + Mouser listings for each]`. The driver's DSK320X-specific
`CTRL6` must-be-1 bit at `0x08` is real register knowledge about the other part.

**I have deliberately not shipped a driver patch for it.** Adding `0x73` means asserting the
DSV320X's `FS_XL`/`FS_G` encodings and must-be bits match a sibling I cannot test and whose
datasheet I have not read — exactly the confident-wrong-answer shape to avoid.

Three honest options, yours to pick:

1. **Ignore it.** EKF3 runs fine on the ICM-45686 alone; set `EK3_IMU_MASK = 1`, `INS_MAX_INSTANCES
   1`, as the hwdef already does. **This is what the image does today**, and it costs you IMU
   redundancy and lane voting.
2. **Add the variant.** Read ST's LSM6DSV320X datasheet, extend the enum and the FS tables, test on
   the bench. A day's work, and a good upstream contribution.
3. **Use it outside ArduPilot.** It is a ±320 g high-g part — arguably better suited to impact/crash
   capture from Linux than to EKF attitude anyway.

Confirm the silicon first, on the bench, in one command:
`scripts/whoami-spi.py <spidev> 0x0F` → expect `0x73`.

---

## 6. What is NOT wired up, stated plainly

* **`[gap]` Which sensor is on which bus.** The schematic says SPI3/SPI4/I2C1. Those are **SoC block
  numbers, not spidev enumeration numbers**, and `LINUX_SPIDEV` wants the latter. The Pi 5 rig had
  only `/dev/spidev0.0` and `/dev/spidev10.0` `[measured]`, so the numbers in the hwdef are
  **placeholders carried from that rig and are probably wrong here.** `scripts/discover-buses.sh`
  prints the paste-ready line from the real board. **This is the one thing that blocks a first boot.**
* **`[gap]` IMU orientation.** Every `ROTATION_NONE` in the hwdef is a placeholder asserting the
  island is mounted level and forward. Not checked against the rev 0.0.2 mechanical drawing.
  Attitude output is untrustworthy until it is.
* **`[gap]` The island heater is not under ArduPilot's control.** `PWM0[0]` drives the DMN2053U
  heater FET. The config enables the PWM but nothing closes the loop, so **the island runs unheated**
  and gyro bias will drift with ambient. The thermal island's whole purpose is currently unrealised.
* **`[gap]` Baro address collision.** BMP390 and BME690 can both answer in the 0x76/0x77 pair.
  `discover-buses.sh` step 3 is how you find out which is which.

---

## 7. The one open question: how AeroSync actually receives this

**ArduPilot speaks MAVLink. Nothing in this repo records AeroSync's transport** `[measured]` — I
grepped every tracked file for `aerosync` and for BLE/GATT/UDP/WebSocket alongside it and got
nothing. What I carry from memory is that AeroSync App V1 does **BLE 5.2** sync, which MAVLink does
not speak natively.

So I built the half that is certain and parameterised the half that is not:

`aerosync/ekf_bridge.py` consumes the MAVLink stream and emits the EKF state as JSON, either to
stdout or to a UDP sink. **Point it wherever AeroSync actually listens**, or use it as the data model
for a BLE GATT writer — the extraction and health logic is the reusable part.

**What "EKF data" actually is**, since ArduPilot has no dump-the-EKF message:

| MAVLink message | What it carries |
|---|---|
| `ATTITUDE` | roll/pitch/yaw + body rates |
| `GLOBAL_POSITION_INT` | EKF lat/lon/alt + velocity |
| `LOCAL_POSITION_NED` | EKF NED position + velocity |
| `EKF_STATUS_REPORT` | health flags + variances — the EKF's opinion of itself |
| `VFR_HUD` | airspeed / groundspeed / climb |

One thing worth knowing, because it is counter-intuitive: **the EKF fusion horizon is not attitude
lag.** `[repo]` EKF3 fuses at a delayed horizon (`maxTimeDelay_ms`), but `calcOutputStates()` runs
**outside** the `runUpdates` block (`AP_NavEKF3_core.cpp:714-717`) and winds the answer forward to
now on every main loop. Real attitude age is one main-loop period — and
`SCHEDULER_DEFAULT_LOOP_RATE` is **50 Hz for plane** (`AP_Scheduler.cpp:44-46`), so **~20 ms** before
any link latency. Raise `SCHED_LOOP_RATE` if that is not good enough, but read §10 of
`docs/aeronode-ahrs-latency-architectures.md` first — it tightens the FIFO-overflow and `dtNow`
clipping doors at the same time.

Also note, for anyone tempted to feed IMU data *in*: **ArduPilot has no MAVLink IMU input.** A
companion computer can only consume a finished attitude.

### The staleness rule, and the test that proves it fires

A feed that keeps rendering its last value when the source dies is lying. So every field in the
bridge's output carries the age of the message it came from, and a field whose source has gone quiet
is emitted as **`null` plus a named fault** — never as its last reading. `never seen` and `stale`
are distinct reasons. An `EKF_STATUS_REPORT` with the `uninitialized` flag set raises
`ekf_not_healthy` and invalidates the frame, because an uninitialised EKF still publishes
plausible-looking attitude numbers.

`[measured]` `aerosync/test_ekf_bridge.py` — **16/16 checks pass**, each with its control:

```
[PASS] (POSITIVE) stale ATTITUDE is NOT the last value  -- emitted null, did not repeat roll=0.5
[PASS] (POSITIVE) stale ATTITUDE raises a 'stale' fault with an age
[PASS] (POSITIVE) never-seen field reports 'no_data', not 'stale'
[PASS] (POSITIVE) EKF 'uninitialized' raises ekf_not_healthy
[PASS] (NEGATIVE) a fully-populated frame is valid (no over-blocking)
...
all checks passed
```

Runs anywhere — it stubs `pymavlink` and never opens a link.

---

## 8. Known failure modes, so they are not rediscovered

* **`Config Error: Baro: unable to initialise driver`** — this is exactly where the September Pi 5
  build stopped `[measured]`, and it is what you will hit if the baro addresses in the hwdef do not
  match the board. It prevents arming. Do **not** paper over it with `Restart=always` in the
  service: a board that reboot-loops looks identical to a board that is running.
* **`ModuleNotFoundError: No module named 'em'`** reads like a missing dependency. It is not. `waf`
  caches the interpreter it saw **at configure time**, so a `configure` run outside the venv poisons
  the build. Activate the venv before `configure`, not just before `build`. `[scar]`
* **Do not pipe into `sudo -S tee -a /boot/firmware/config.txt`.** `sudo -S` eats the first stdin
  line as the password, so the piped text appends the *password* into the file. Stage a file, then
  `sudo cp`. `[scar]` — this one actually corrupted a `config.txt`.

---

## 9. What I could not verify, and will not round up to green

| Claim | Status |
|---|---|
| A CM5 reports peripheral base `0x10` → `RPI_5` | `[derived]` — same BCM2712 as the Pi 5, **not measured on a CM5**. Test is `discover-buses.sh` step 1 |
| The hwdef parses and generates the intended probe lists | **Unknown** — needs the ArduPilot tree; `verify` is written to check it, and has not been run |
| ICM-45686 answers on SPI on this carrier | **Unknown** — needs the board |
| LSM6DSV320X reads `0x73` | `[fetched]` from ST AN6119, **not measured on our silicon** |
| spidev numbers in the hwdef | **Wrong, probably** — placeholders, flagged in the file itself |
| Bridge staleness + EKF-health guards | `[measured]` 16/16, both controls |
| Patches 0001/0002 still needed upstream | `[measured]` today |
| Anything about AeroSync's transport | **`[gap]`** — not recorded anywhere in this repo |

The bench did not answer on `scopenode.local`, `aeronode.local`, `192.168.10.34` or
`192.168.0.99` today `[measured]`, so nothing in §9's "Unknown" rows could be closed.

---

## 10. Run order

```
# on the AeroNode CM5
scripts/discover-buses.sh                  # FIRST. Fix the hwdef's LINUX_SPIDEV line.
scripts/build-on-board.sh preflight
scripts/build-on-board.sh all              # clone, prereqs, patch, hwdef, build, verify
scripts/build-on-board.sh install
# set the MAVLink endpoint in the service, then
sudo systemctl enable --now arduplane
ekf-bridge --in udp:127.0.0.1:14550 --out stdout | head -3

# then, on a Linux host
sudo scripts/bake-image.sh /dev/sdX aeronode-rev002-ardupilot-$(date +%F).img
```

The step that proves the image does its job is the last `ekf-bridge` line showing
`"_healthy":true`. Everything before it only proves the software runs.
