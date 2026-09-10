# AeroNode — sensor/telemetry data model

**Status:** derived from the schematic and `ARCHITECTURE.md`, 2026-08-26. No firmware exists in this
repo yet — this is the hardware-imposed shape of the data AeroNode can produce, meant as the starting
point for a driver/telemetry layer, not a description of code that exists.

Provenance: `[repo]` = read directly off the schematic/architecture doc · `[fetched]` = datasheet fact
already cited in `ARCHITECTURE.md` or `imu-board-notes.md` · **`[gap]`** = a value a firmware author will
need (ODR, full-scale range, register map) that is **not sourced anywhere in this repo** and must not be
assumed — go to the part's datasheet before writing a driver.

---

## 1. Bus map

| Bus | CC93 pads | Devices | Addresses |
|---|---|---|---|
| **I2C2** | V1 (SCL), W1 (SDA) | U3 BQ25798 charger | fixed, per datasheet (not itself listed in `ARCHITECTURE.md`) |
| **I2C4** | E29 (SCL), F28 (SDA) | U6 BME690, U9 MMC5983MA, U10 BMP390, **A2B control (planned)** | 0x76, 0x30, 0x77, ~0x68 |
| **LPSPI8** (dedicated) | D17 SCK, E18 MOSI, E22 MISO, E19 CS0 | U1 ICM-45686 (imu-board) | — |
| **LPSPI3** (UART7 pads) | N29 SCK, M29 MOSI, R1 MISO (shared), P1 ACC_CS, C24 GYR_CS | U2 BMI088 (imu-board) | — |
| **LPUART5** | AK24 (TXD), AK25 (RXD) | U7 DAN-F10N GNSS | UART protocol, not I2C |
| **SAI3** (TDM) | E23 BCLK, C19 FS, E20/E21 TX/RX data, B24 MCLK | A2B main node (planned, not yet placed) | — |

Two GPIOs carry sensor-adjacent status rather than a bus: `GNSS_PPS` (U29) and the charger's
`CHG_INT_N` / `PD_FAULT` / `PG_5V` (§4).

**I2C4 address map** `[repo]` (ARCHITECTURE.md, "Address clash avoided deliberately"):

| Address | Device |
|---|---|
| 0x30 | MMC5983MA magnetometer |
| 0x76 | BME690 environmental |
| 0x77 | BMP390 barometer |
| ~0x68 | A2B (AD242x class) — planned, verify against the chosen transceiver |

---

## 2. Inertial — two independent IMUs, no shared bus

Deliberate design choice (`imu-board-notes.md`): the two IMUs do **not** share a bus, so a fault on one
die cannot block readback from the other. A firmware data model should keep them as two independent
sensor objects, not one fused "IMU" service, at the driver layer.

### 2.1 U1 — TDK/InvenSense ICM-45686 (LPSPI8)

| Field | Value |
|---|---|
| Axes | 3-axis accel + 3-axis gyro (6DoF) `[repo]` |
| Interface | SPI, dedicated bus, CS = E19, INT1 = E28, INT2 = E27 `[repo]` |
| Full-scale ranges, ODR, register map | **`[gap]`** — DS-000577 could not be retrieved (blocked behind a
  TDK redirect); nothing in this repo sources these values. Do not assume ICM-42688-class figures — this
  part has no REGOUT pin, so it is not a drop-in electrical match either. |
| Temperature output | Typical for this class of IMU but **not confirmed in this repo** — `[gap]` |

### 2.2 U2 — Bosch BMI088 (LPSPI3, two chip selects on one bus)

| Field | Value |
|---|---|
| Axes | 3-axis accel (separate die, CS = P1/ACC_CS, data = R1) + 3-axis gyro (separate die, CS = C24/GYR_CS, data = shared R1) `[repo]` |
| Interrupts | `BMI_ACC_INT` = AA1, `BMI_GYR_INT` = Y1 `[repo]` |
| Accel/gyro data-ready | Via each die's own INT pin — poll or IRQ-driven, firmware's choice |
| Full-scale ranges, ODR, register map | **`[gap]`** — not sourced in this repo; go to
  BST-BMI088-DS000-19 §register map before writing the driver |
| **Firmware-mandatory bring-up sequence** `[fetched]`, from `imu-board-notes.md` | 1) Accel die powers up in **I2C mode regardless of PS** — must be moved to SPI with a dummy read of `ACC_CHIP_ID` before any real access. 2) Gyro honours PS directly (already strapped to GND = SPI). 3) **Accel SPI reads return a leading dummy byte** the driver must discard; the gyro does not. |
| Open question, not yet resolved | Whether SDO1/SDO2 genuinely tri-state when their CS is deasserted is **unconfirmed from extractable datasheet text** (only shown in an image figure). AeroNode wires them to the *same* net (`R1`), so if this turns out false, the two dies cannot be read as designed — see `ARCHITECTURE.md` "J1 pins 14 and 15" and `imu-board-notes.md` open item 2. |

---

## 3. Environmental / positioning sensors (I2C4)

| Sensor | Part | Data produced | Resolution/accuracy `[fetched]` | Update mechanism | Firmware note |
|---|---|---|---|---|---|
| Gas/temp/humidity/pressure | U6 BME690 | gas resistance, temperature, relative humidity, pressure | not sourced in this repo — `[gap]` | **Polled only** — 8-pin package has no INT line `[repo]` | `CSB` hard-wired to +3V3 at power-on to force I2C mode; do not rely on a GPIO for this |
| 3-axis magnetic field | U9 MMC5983MA | mag X/Y/Z | 18-bit `[repo]` | Polled — `INT` pin left open, no GPIO available `[repo]` | Driver **must** periodically trigger a SET/RESET cycle (the offset-cancellation the datasheet requires) — this is what C18's 10 uF cap exists for. Omitting it doesn't fail loudly, it just degrades accuracy over temperature. |
| Barometric pressure + temperature | U10 BMP390 | pressure, temperature (altitude is a derived quantity, not raw output) | ±3 Pa relative accuracy (~0.25 m) `[repo]` | Polled — `INT` left open, no GPIO available `[repo]` | — |

**Placement caveat that affects data quality, not just hardware:** `ARCHITECTURE.md` flags that U9
(magnetometer) sits near two switching converters and the charger's high-current path, and recommends
moving it to `imu-board` instead. As currently placed, expect a time-varying magnetic offset correlated
with load/charge current that static hard-iron/soft-iron calibration **cannot** remove — a firmware
calibration routine built on the assumption of only static offsets will be wrong on this hardware.

---

## 4. Power/charge telemetry (I2C2 + GPIO)

Not a "sensor" in the inertial/environmental sense, but it is data the flight software needs, and the
hardware imposes hard *ordering* requirements on reading/writing it — these are firmware obligations
created by the hardware, not conventions:

| Signal | Path | Meaning | Firmware obligation `[repo]`/`[fetched]` |
|---|---|---|---|
| `CHG_SCL`/`CHG_SDA` | I2C2 to U3 BQ25798 | full charger register set: VBAT, ICHG, VSYS, fault bits, JEITA thermal state | See ordering rule below — this is not a passive read-only telemetry link |
| `CHG_CE_N` (AN4) | GPIO, host pulls low to enable charging | charge enable | Must be asserted **only after** `VREG` is set to 7.20 V — reversing the order charges the LiFePO4 pack at the Li-ion voltage |
| `CHG_INT_N` (E3) | GPIO, open-drain | charger interrupt/fault | — |
| `PD_FAULT` (P29) | GPIO | USB-PD sink couldn't meet the requested 9 V/3 A | — |
| `PG_5V` (R29) | GPIO | +5V buck power-good | Near-tautological on this topology — if it's bad, the host reading it likely isn't running either |
| `OVP_FLT_N` (T29) | GPIO | VSYS overvoltage-protection trip | The genuinely dangerous fault case; kept even after `PG_5V`'s pad was reallocated to an LED |

**Mandatory firmware sequence, hardware-imposed** (`ARCHITECTURE.md`, Hazard 1 and stage 4):

1. Write `CELLS = 2s`, then `VREG = 7.20 V` (POR default is 8.4 V — wrong chemistry).
2. **Disable the I2C watchdog** (`WATCHDOG = 0`) immediately after. Left running, every expiry silently
   reverts `VREG` to 8.4 V — a runtime hazard, not just a power-on one.
3. Only then pull `CHG_CE_N` low to enable charging.
4. TS thermistor divider (R23/R24) is wired to the datasheet's **Li-ion** JEITA window (0–60 °C), not
   LiFePO4's safe range (~0–45 °C) — until R23/R24 are recomputed for LFP, firmware should tighten
   `TS_COOL`/`TS_WARM` over I2C rather than trust the coarse divider.

A telemetry/data-model layer that exposes `VREG`/`WATCHDOG`/`CHG_CE_N` as an ordinary read/write register
set without encoding this sequence will, on first watchdog expiry, silently overcharge the pack.

---

## 5. GNSS (LPUART5)

| Field | Value |
|---|---|
| Part | u-blox DAN-F10N, L1/L5 dual-band, integrated RHCP patch antenna `[repo]` |
| Interface | **UART only** — no I2C, no SPI `[repo]` |
| Data | Position/velocity/time — protocol (NMEA vs UBX binary) not specified in this repo, `[gap]` |
| Timing | `GNSS_PPS` (TIMEPULSE) on GPIO U29 — pulse-per-second for time sync |
| **Firmware-mandatory GPIO config** `[fetched]` | TIMEPULSE and `SAFEBOOT_N` share one pin internally through a 1 kΩ resistor. If the CC93 drives U29 low at reset (before firmware configures it), the receiver is forced into safeboot on every power-up. **U29 must be configured input/high-Z, and its post-reset state verified**, before any other GNSS handling. |
| Known doc inconsistency | The datasheet's Table 11 and Table 12 disagree on pin numbers for several control pins; the symbol/schematic follow Table 11. Worth confirming against u-blox's integration manual before trusting any pin not already wired here. |

---

## 6. Audio (A2B, planned — not yet placed)

SAI3 (TDM, full duplex) carries audio data; a to-be-selected AD242x-class transceiver's I2C control
interface shares **I2C4** (§1). This is streaming data, not periodic telemetry, so it likely wants a
different transport in the firmware data model (a ring buffer / DMA path) rather than the register-poll
pattern used for the environmental sensors. No part is placed yet, so pin-level detail beyond the SAI3
mapping in `ARCHITECTURE.md` does not exist to record.

---

## 7. What this data model deliberately does not contain

- Register maps, ODR/full-scale tables, or conversion formulas for any part — every `[gap]` above needs
  a datasheet pull before a driver is written; nothing here should be treated as sufficient to start
  register-level code.
- A wire format / serialization schema (e.g. protobuf, a C struct layout) for telemetry — that's a
  software-architecture decision with no hardware constraint dictating it, so it doesn't belong in a
  document derived from the schematic.
- The two host GPIOs (`GNSS_PPS`, and note **AeroNode has no spare 3V3 GPIO of any kind** as of
  2026-08-22) — any additional sensor interrupt will need a 1V8 pad + level shifter, the SD2 pads (cost:
  microSD), or reallocating an existing signal.
