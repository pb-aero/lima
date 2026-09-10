# AeroNode software revision 1 — the ArduPilot-on-CM5 part

**Written:** 2026-09-10 by LIMA. **Status:** scope proposal. Nothing here is built yet except the
Raspberry Pi 5 groundwork noted in §2, which is on hardware and measured.

Provenance tags used throughout: `[measured]` I ran it · `[repo]` read off a schematic or source
tree, path given · `[fetched]` from a cited document · `[assumed]` a guess, flagged · `[gap]` a fact
a rev-1 author needs that is **not sourced anywhere** and must not be invented.

---

## 0 · First, which AeroNode

There are two boards called AeroNode in reach of this repo, and they are not the same computer.
Getting this wrong invalidates everything downstream, so it is stated first.

| | Compute | Where the design lives |
|---|---|---|
| **AeroNode (CC93)** | Digi ConnectCore 93, NXP i.MX93 | `kicad/aeronode/` in this repo `[repo]` |
| **AeroNode (CM5)** — *this document* | Raspberry Pi **CM5108064B** (CM5, 8 GB RAM / 64 GB eMMC) | `~/aerosense/aeronode/aerosense/` on Peter's Mac, **not under git** `[repo]` |
| AeroNode Lite | same CM5, audio-interface variant | `~/aerosense/aeronode/aerosense/aeronode-lite/`, mirrored read-only at `kicad/aeronode-lite-audio/` `[repo]` |

This document is **only** about the CM5 one. `kicad/aeronode/doc/TELEMETRY_DATA_MODEL.md` in this
repo describes the *CC93* sensor set (BMI088, MMC5983MA, BMP390, I2C4, LPSPI8) — it does **not**
apply here, and the two sensor sets differ in every barometer and magnetometer part.

---

## 1 · What the CM5 board actually presents to software

`[repo]` from `~/aerosense/aeronode/aerosense/cm5.kicad_sch` — the net labels on the CM5 module
symbol are the complete list of what software can reach:

| Interface | Nets | Intended use |
|---|---|---|
| **SPI3** | `SPI3_SCLK/MOSI/MISO/CS` | sensor bus (one chip select) |
| **SPI4** | `SPI4_SCLK/MOSI/MISO/CS` | sensor bus (one chip select) |
| **I2C1** | `I2C1_SCL/SDA` | sensor bus |
| **UART0** | `UART0_TX/RX` | GNSS |
| **I2S1** | `SCLK`, `WS`, `SDI[0..3]`, `SDO[0..3]` | audio — 4 lanes in, 4 lanes out |
| **PWM0[0]** | `PWM0[0]_HEATER` | IMU heater |
| **GPIO ×2** | `GPIO_RLY_SPKR`, `GPIO_RLY_MIC` | headset mute relays |

`[repo]` from the `AERONODE` block diagram in
`~/aerosense/aeronode/aerosense/aeronode-lite/aeronode-lite.kicad_sch`, the parts that hang off
those buses:

- **IMU1** — TDK **ICM45686**, on SPI (`IMU1_CS/SCLK/MOSI/MISO`), on a heated flex sub-PCB driven by `PWM0[0]`
- **Barometer** — Bosch **BMP581**
- **Compass** — PNI **RM3100**
- **Environmental** — Bosch **BME690**
- **CO** — Figaro **TGS5141-P00**, analogue, via **ADS1115** ADC + **TLV8811** opamp
- **GPS** — **DAN-F10N** on UART0
- **NPU** — **Hailo 8L** on the PCIe M.2 slot, its own TPS564252 rail
- **Storage** — F35SQB004G / W25N01GVZEIG SLC NAND
- **Power** — BQ25798 charger, 2S LiFePO4 6.4 V 5000 mAh (32 Wh)
- **Audio** — A2B main node on I2S1, plus the transformer/relay mute block already drawn

### The gap that matters most

**`[gap]` Which sensor sits on SPI3, which on SPI4, and which on I2C1 is not recorded anywhere.**
The block diagram names the parts, `cm5.kicad_sch` names the buses, and nothing joins the two:
`FMU.kicad_sch` is an empty sheet (25 kB, zero symbols `[measured]`) and no CM5 sensor sheet exists.
A board target cannot be written without this — see §4. It is one afternoon of schematic work, or
one sentence from Peter.

**`[gap]` DAN-F10N protocol.** It is on UART0 and the whole GPS path assumes it speaks UBX. I have
not sourced that from u-blox, and `DAN-F10N` appears nowhere in the ArduPilot tree `[measured]`.
Confirm from the datasheet before assuming `AP_GPS_UBLOX` drives it; some u-blox parts ship
NMEA-only by default, which ArduPilot can read but with less than half the useful fields.

---

## 2 · What is already proven, on a Pi 5, not a CM5

`[measured]` 2026-09-04, on `Raspberry Pi 5 Model B Rev 1.1`, machine-id
`49cc4b68da3b4dfd9d10cc78207fe9eb`, reached at `192.168.10.34` on 2026-09-10, kernel
`6.18.39+rpt-rpi-2712`. Full write-up in `linux/ardupilot-pi5/RESULTS-2026-09-04.md`.

- **ArduPilot builds and runs natively on BCM2712.** `arduplane V4.8.0-dev`, `./waf
  configure --board=linux && ./waf plane`, 4m52s, aarch64 native. No cross-compilation.
- **A Linux board target mechanism exists and I have used it.** `libraries/AP_HAL_Linux/hwdef/`
  takes a `hwdef.dat` in the same declarative language as the ChibiOS boards — `IMU`, `COMPASS`,
  `BARO`, `LINUX_SPIDEV`, `define`, and `include` of another board's file. There are 26 boards in
  there `[measured]`; `pi5` is one of them and it is mine.
- **Two upstream patches, on branch `pi5-board` in `~/ardupilot` on that box.** Patches also at
  `linux/ardupilot-pi5/upstream-pr/`. The first is a one-character correctness fix; the second adds
  the generic `pi5` board.
- **EKF3 as the AHRS is configured**, GPS-free source set baked into ROMFS.

### The prerequisite nobody would guess

`libraries/AP_HAL_Linux/Util_RPI.cpp` detects the board by reading the **peripheral base address**
out of `/proc/device-tree/soc*/ranges`, not by any model string `[repo], read at length`. Base
`0x10` means `RPI_5`; anything else means `UNKNOWN_BOARD`, and on a board with the RPi GPIO backend
enabled that is an `AP_HAL::panic` at startup, not a warning.

To find that file at all it scans `/proc/device-tree` for a directory starting `soc` — and upstream
compares with `strncmp(d_name, "soc", 4)`, an **exact** match against `"soc"` where a prefix match
was meant. Every 2712-class kernel names the node `soc@107c000000`, so upstream detection fails on
this silicon. The fix is `4` → `3`, proven with a matched pair (aborts vs runs) `[measured]`.

**This fix is a prerequisite for the CM5, not just the Pi 5** — same SoC, same device-tree naming.
The patch is written and unfiled: it needs a browser session and a fork at `pb-aero/ardupilot`,
which does not exist yet, and there is no `gh` in this fleet.

### What did not work, and is still open

The dev rig's MPU-9250 **stalls in its FIFO** at startup — `MPU: temp reset IMU[0] <n> 0`, zeros
forever, never reaching `ArduPilot Ready`. Every software cause was ruled out by measurement or by
reading the code path; no software change explains it, and it wants hands on the bench.

**It is very likely moot for AeroNode**, and this is the one piece of good luck in the whole file:
that rig runs an **Invensense IMU over I2C**, and AeroNode runs an **Invensense IMU over SPI**.
Every Invensense hwdef upstream uses SPI. AeroNode's design already avoids the exact configuration
that stalled. That is a prediction, not a result — do not treat the stall as closed until an
AeroNode IMU has produced samples.

---

## 3 · Driver availability, checked against the tree rather than assumed

`[measured]` by `git grep` in `~/ardupilot` at `fa7ffbd0a1` on 2026-09-10. This is the single most
load-bearing table here, because it decides what rev 1 can delegate to ArduPilot and what it must
write itself.

| Part | ArduPilot support | Evidence |
|---|---|---|
| **ICM45686** IMU | **Yes.** `AP_InertialSensor_Invensensev3`, enum `ICM45686`, `WHO_AM_I` **0xE9**, HiRes 20-bit path, registers cited to TDK **DS-000563 rev 1.0** in the driver | `libraries/AP_InertialSensor/AP_InertialSensor_Invensensev3.{h,cpp}` |
| **BMP581** baro | **Yes.** Dedicated driver, I2C **0x46**/**0x47**, probes a generic `AP_HAL::Device` so SPI works too | `libraries/AP_Baro/AP_Baro_BMP581.cpp`, registered in `AP_Baro.cpp:815` |
| **RM3100** compass | **Yes.** Dedicated driver, shipping hwdefs use both `I2C:0:0x20` and `SPI:rm3100` forms | `libraries/AP_Compass/AP_Compass_RM3100.cpp` |
| **ADS1115** ADC | **Yes**, and specifically on the **Linux** HAL | `libraries/AP_HAL_Linux/AnalogIn_ADS1115.cpp`, used by `hwdef/pilotpi` |
| **DAN-F10N** GNSS | **Unknown** — see the `[gap]` in §1 | no hits in `libraries/` |
| **BME690** environmental | **No. Not a flight sensor to ArduPilot** — no BME690 *or* BME680 anywhere in the tree | zero hits |
| **TGS5141-P00** CO | **No** — reads as an analogue channel on the ADS1115; the ppm conversion is ours | — |
| **Hailo 8L** NPU | **No, and correctly so** — nothing about it belongs inside ArduPilot | — |

The shape of rev 1 falls straight out of that table: **every flight-critical sensor on this board
already has an upstream driver**, and everything ArduPilot does not know about — CO, environmental,
NPU, audio, the heater, the mute relays, telemetry — is a separate process alongside it.

A useful side effect: the `[gap]` on ICM-45686 ODR/full-scale/register map flagged in
`kicad/aeronode/doc/TELEMETRY_DATA_MODEL.md` is **partly closed by ArduPilot's own driver**, which
encodes the register map and cites DS-000563 — a document reference the KiCAD sessions never found
while chasing DS-000577.

---

## 4 · What revision 1 has to contain

### 4.1 Land the port (blocked only by the `[gap]` in §1)

1. **File the upstream PR** — the `soc` prefix fix. Prerequisite for this silicon, and the only item
   here that helps people outside Aerosense.
2. **Write `libraries/AP_HAL_Linux/hwdef/aeronode/hwdef.dat`.** **DONE this session, built and
   verified** — see `linux/ardupilot-cm5/RESULTS-2026-09-10.md` and the patch beside it. Commit
   `51ea1d87b5` on branch `aeronode-board` in `~/ardupilot` on the Pi 5. `arduplane` builds in
   4m53s; the binary carries 27 `Invensensev3` symbols and **zero** old-`Invensense` symbols.

   **Correction to my own first sketch, which was wrong in a way `configure` called success.** I
   wrote `include ../pi5/hwdef.dat`, because pi5 already has the toolchain, the RP1 GPIO backend
   and the subtype. But **`include` also inherits a board's sensor device lines, and `undef` will
   not remove them** — the generator appends. The AeroNode target came out probing the pi5 dev
   rig's MPU-9250 on `i2c-2:0x68` as `HAL_INS_PROBE1`, with the real ICM45686 appended behind it,
   and with `INS_MAX_INSTANCES 1` the real sensor is the one that gets dropped. `configure` printed
   `finished successfully` throughout. Inherit `../linux/hwdef.dat` and re-add the two pi5 lines by
   hand:

   ```
   include ../linux/hwdef.dat
   define HAL_LINUX_GPIO_RPI_ENABLED 1
   define CONFIG_HAL_BOARD_SUBTYPE HAL_BOARD_SUBTYPE_LINUX_PI5

   undef HAL_INS_DEFAULT
   IMU     Invensensev3 SPI:icm45686 ROTATION_NONE      # rotation TBD, see 4.4
   define INS_MAX_INSTANCES 1

   COMPASS RM3100 SPI:rm3100 false ROTATION_NONE        # or I2C:1:0x20 -- GAP
   BARO    BMP581 I2C:1:0x46                            # or SPI -- GAP
   define AP_COMPASS_PROBING_ENABLED 1
   define HAL_LINUX_I2C_INTERNAL_BUS_MASK 0

   #            NAME       BUS SUBDEV MODE       BPW CS_PIN        LOWSPD HIGHSPD
   LINUX_SPIDEV "icm45686" 3   0      SPI_MODE_0 8   SPI_CS_KERNEL 4*MHZ  10*MHZ
   LINUX_SPIDEV "rm3100"   4   0      SPI_MODE_0 8   SPI_CS_KERNEL 1*MHZ  1*MHZ
   ```

   The `BUS`/`SUBDEV` numbers are **spidev device numbers as Linux enumerates them under the
   carrier's overlay config**, not the SoC's SPI block numbers. They must be read off
   `/dev/spidev*` on the real board, never inferred from `SPI3`/`SPI4` on the schematic. They are
   placeholders and carry no design authority until the `[gap]` in §1 closes.

3. **Prove board detection on the CM5 before trusting anything else.** One command on the bench:

   ```bash
   od -An -tx1 -N16 /proc/device-tree/soc*/ranges
   ```

   Bytes 4–7 must read `00 00 00 10`. If they do, the CM5 detects as `RPI_5` and the whole §2
   groundwork applies unchanged. If they do not, `Util_RPI.cpp` needs a CM5 case and nothing built
   on the RPi GPIO backend will start until it has one. On the Pi 5 the full 16 bytes read
   `00 00 00 00 00 00 00 10 00 00 00 00 80 00 00 00` `[measured]` and the binary prints `RPI 5` at
   startup. `[assumed]` the CM5 matches — same BCM2712 — but this is exactly the kind of
   expectation that a broken instrument confirms too neatly. Measure it.
4. **Build and run**: `./waf configure --board=aeronode && ./waf plane`, then check the sensors
   declare themselves in the startup banner before looking at any attitude output.

### 4.2 Write the part ArduPilot will not

A second process, alongside ArduPilot, owning everything in §3's "No" rows: BME690 environmental,
TGS5141 CO through the ADS1115, the `PWM0[0]` IMU heater loop, the two mute-relay GPIOs with their
readback, A2B/audio on I2S1, Hailo 8L inference, and the telemetry envelope over all of it.
`kicad/aeronode/doc/TELEMETRY_DATA_MODEL.md` is the right starting shape but is written against
the **CC93** part list and needs re-deriving for this board.

Two constraints already measured and worth carrying in:

- **RP1 I2S clock direction is a block-wide choice, and 3 channels is illegal** — from
  `.agent/MEMORY.md` 2026-09-02. The 4-in/4-out lane layout on I2S1 is inside what was brought up
  on RP1; a 3-lane variant is not.
- **The mute relays must be safe with the CM5 down.** The relay block is de-energised
  `COM–NC` closed so the pilot hears audio with the board unpowered, and the 100 kΩ gate pulldown
  is what makes the state defined through a CM5 reboot — `docs/h1-headset-mute-relay.md`. Software
  must not be the thing that guarantees this.

### 4.3 The architecture question — RULED 2026-09-10

**Peter's ruling: ArduPilot runs on the CM5 itself.** The FMU path is not taken; the empty
`FMU.kicad_sch` should stop implying otherwise. §4.1 is therefore the right work, and it is done.
The rest of this section is kept because the trade it names does not go away by being decided.

**`FMU.kicad_sch` exists and is empty.** If the intent is an FMU microcontroller running ArduPilot
on ChibiOS with the CM5 as companion computer, then most of §4.1 is the wrong work and rev 1 is a
MAVLink client, not a flight stack. If the intent is ArduPilot on the CM5 with the FMU sheet dead,
§4.1 is right and the sheet should be deleted so it stops implying otherwise.

What must be carried forward as an accepted consequence of the ruling, not argued again: ArduPilot on Linux is a userspace process on a general-purpose kernel. It uses `SCHED_FIFO`
threads and it works, but it has no hardware watchdog, no independent failsafe, and its worst-case
scheduling latency is a property of whatever else the CM5 is doing — including Hailo inference on
the PCIe bus. An FMU exists in flight controllers for that reason and not for driver support.

### 4.4 Two things only Peter can close

- **Sensor orientation.** Every `ROTATION_` in §4.1's sketch is a placeholder that asserts the
  sensors are mounted level and forward. On the Pi 5 rig the same placeholder hid a **~15°
  residual** after a 180° flip. It is not a software question.
- **Accelerometer and compass calibration** — needs the board physically rotated.

---

## 5 · Honest account of the limits of this document

- **The CM5 was never touched.** `100.64.0.6`, the CM5 that answers to `aeronode-385ba5`, did not
  accept a connection from this Mac today — `Operation timed out` on port 22 `[measured]`. Every
  measurement in §2 and §3 comes from the **Pi 5** at `192.168.10.34` and the ArduPilot source tree
  on it. The CM5 claims in §4.1 step 3 are predictions with a stated test, not results.
- **The bus map in §1 is incomplete by the hardware's own admission**, not by my omission. No CM5
  sensor sheet exists to read.
- **An `aeronode` board target now exists and builds** — that part of §5 is superseded, see §4.1
  and `linux/ardupilot-cm5/RESULTS-2026-09-10.md`. It was built on the **Pi 5**, has never seen a
  CM5, and has never read a sensor: the Pi 5 has only `/dev/spidev0.0` and `/dev/spidev10.0`
  `[measured]`, so nothing answers to `icm45686` or `rm3100` there.
- **My first version of that hwdef was wrong and `configure` called it a success.** The correction
  is in §4.1. I am leaving the wrong version described rather than quietly replacing it, because
  the failure mode — `include` inherits another board's sensors, `undef` does not remove them —
  will catch the next person too.
- **`aerosense.kicad_sch` and its sheets are not under git.** Everything §1 rests on lives in one
  unversioned directory on one Mac. That is a bigger risk to revision 1 than any item above.
