# Feeding the GNSS into ArduPilot — working, with one loud caveat

**Date:** 2026-09-11 · **Agent:** LIMA
**Box:** `Raspberry Pi 5 Model B Rev 1.1`, machine-id `49cc4b68da3b4dfd9d10cc78207fe9eb`, at
192.168.0.99. Native `--board=pi5` build, `AP_HAL_Linux`.

## Result

```
GPS_RAW_INT  fix=3D_FIX(3) sats=21 lat=-34.1966643 lon=24.8361031 alt=3.5m hdop=0.62
GPS_RAW_INT  fix=3D_FIX(3) sats=21 lat=-34.1966625 lon=24.8361032 alt=3.8m hdop=0.62
GPS_RAW_INT  fix=3D_FIX(3) sats=21 lat=-34.1966613 lon=24.8361020 alt=3.9m hdop=0.63
GPS_RAW_INT  fix=3D_FIX(3) sats=20 lat=-34.1966596 lon=24.8360990 alt=4.3m hdop=0.64
```

**ArduPilot detects, configures and reports the u-blox M10 with no GPS-specific work at all.**

| | |
|---|---|
| command line | `--serial3 /dev/ttyAMA0` |
| `SERIAL3_PROTOCOL` | **5** (GPS) — already the default |
| `SERIAL3_BAUD` | **230** (230400) — already correct, no change needed |
| `GPS1_TYPE` | **1** (AUTO) — auto-detected the u-blox |

Note `GPS_TYPE` does not exist on this build; it is **`GPS1_TYPE`**, the same renaming that caught
me with `SR0_EXTRA1` → `MAV1_EXTRA1`.

### An independent cross-check worth having

The position ArduPilot reports agrees with **my own UBX decoder**, written separately and reading
the raw serial stream, to ~1e-5 degrees. Two independent implementations parsing the same NAV-PVT
and landing on the same answer is parity *and* — since the position is a real place with a real
altitude near sea level — a sanity check on correctness, not just agreement.

## The caveat, and it is not small

**This required stubbing out the IMU sanity check.** GPS init runs *after* INS init, so the IMU
FIFO stall (`linux/ardupilot-pi5/IMU-STALL-DIAGNOSIS-2026-09-11.md`) blocks the GPS and every other
subsystem. The stub is saved beside this file as `BENCH-STUB-imu-temp-check.patch`:

```c
if (_dev->bus_type() == AP_HAL::Device::BUS_TYPE_I2C) {
    return true;          // accept corrupt FIFO samples
}
```

- It makes `_check_raw_temp()` always pass **on I2C only** — an SPI IMU is untouched.
- It is applied to the working tree at `~/ardupilot` on the bench and is **NOT committed there**.
- **The inertial data in this build is garbage and any attitude it reports is meaningless.**
  Only non-inertial subsystems — GPS, baro, telemetry — mean anything.
- **Not for upstream. Not for flight.** The comment block in the patch says so at length.

## What this does and does not establish

**Does:** the GNSS hardware, the wiring, the UART, ArduPilot's u-blox driver and the whole serial
path work natively on the Pi. For the "Pi as flight controller" plan, GPS is done — it needed no
configuration beyond pointing `--serial3` at the port.

**Does not:** say anything about navigation or attitude. EKF3 cannot produce a usable solution from
zeroed inertial data no matter how good the GPS is. A GPS fix is not a nav solution.

## Still the one blocker

An IMU. `/dev/spidev0.0` is live (`dtoverlay=spi0-0cs`) and SPI0 is free, so an ICM-42688 or
ICM-45686 breakout drops straight in — and that is AeroNode's architecture anyway, where both fast
sampling and 20-bit HiRes are gated on `bus_type() == BUS_TYPE_SPI`. With an SPI IMU this stub can
be reverted and everything downstream (EKF3, the AHRS data-path comparison, the sched-tail harness)
becomes measurable.
