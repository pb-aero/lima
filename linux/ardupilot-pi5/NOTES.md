# ArduPilot on the Pi 5 (`scopenode`) — what is established before anything is installed

**Date:** 2026-09-04 · **Agent:** LIMA · target: `scopenode`, Raspberry Pi 5 Model B Rev 1.1,
Raspberry Pi OS, kernel `6.12.47+rpt-rpi-2712`, aarch64.

Provenance: `[measured]` = I fetched the file/ran the command myself · `[fetched]` = read from a
source I retrieved · `[derived]` = reasoned, reasoning shown · **`[gap]`** = not established.

Upstream read at `ArduPilot/ardupilot` master `ff37fde6f13c02fb5ae32abdd07ff4f4e132cb76`. `[measured]`

---

## 1. Pi 5 is supported. This was the real risk and it resolves in our favour

The Pi 5 replaced the BCM283x peripheral block with **RP1** over PCIe, so every historical
ArduPilot Raspberry Pi backend — which `mmap`s a fixed BCM peripheral base out of `/dev/mem` —
is wrong on this board. That was tracked as
[issue #26386](https://github.com/ArduPilot/ardupilot/issues/26386) (opened 2024-03-04, *"not
compatible with the current software architecture"*), **closed** by PR #27026 *"Add Raspberry Pi 5
support"*. `[fetched]`

Confirmed in the source rather than taken from the issue tracker: `[measured]`

| Evidence | File |
|---|---|
| `case LINUX_BOARD_TYPE::RPI_5: gpioDriver = NEW_NOTHROW GPIO_RPI_RP1();` | `libraries/AP_HAL_Linux/GPIO_RPI.cpp:30` |
| `#include "GPIO_RPI_RP1.h"` — a dedicated RP1 GPIO backend exists | `libraries/AP_HAL_Linux/GPIO_RPI.cpp:8` |
| `_linux_board_version = LINUX_BOARD_TYPE::RPI_5; printf("RPI 5 \r\n");` | `libraries/AP_HAL_Linux/Util_RPI.cpp:99` |

**How it decides it is a Pi 5** `[measured]` — `UtilRPI::_get_board_type_using_peripheral_base()`
reads the first 32 bytes of `/proc/device-tree/soc/ranges`; if that path is absent it scans
`/proc/device-tree` for any entry starting `soc` and uses that one's `ranges` (the Pi 5 names the
node differently). It then switches on the extracted base address:

```
0x10        -> RPI_5              <- ours
0x20000000  -> RPI_ZERO_1
0x3f000000  -> RPI_2_3_ZERO2
0xfe000000  -> RPI_4  (etc.)
0x0         -> UNKNOWN_BOARD, prints "Cannot detect board-type"
```

That gives a **free positive control**: the binary prints `RPI 5` on startup. If it prints
`Cannot detect board-type`, the build is running blind and nothing GPIO-related can be trusted.
`install_ardupilot.sh verify` greps for exactly this.

## 2. The board target is `--board=linux`

ArduPilot's Linux boards are hwdef directories under `libraries/AP_HAL_Linux/hwdef/`. The full
list as of the SHA above `[measured]`: `aero bbbmini bebop bhat blue canzero dark disco edge
erleboard erlebrain2 linux navigator navigator64 navio navio2 obal ocpoc_zynq pilotpi pocket
pocket2 pxf pxfmini t3-gem-o1 vnav zynq`.

`hwdef/linux/hwdef.dat` in full `[measured]`:

```
# hwdef for generic Linux configuration option, eg. running on your laptop
env TOOLCHAIN native
define HAL_INS_DEFAULT HAL_INS_NONE
...
```

Two consequences that matter:

- **`TOOLCHAIN native`** — this is why `--board=linux` compiles correctly on the Pi itself and
  produces aarch64 binaries. Every *other* Linux board inherits `LinuxBoard`'s default toolchain
  `arm-linux-gnueabihf` (32-bit cross) unless its hwdef overrides it — `pilotpi` and
  `navigator64` set `aarch64-linux-gnu` for exactly this reason. Picking the wrong target here
  produces a binary that will not run.
- **`HAL_INS_NONE`** — the generic board declares **no IMU, no compass, no baro**. It builds, it
  runs, it talks MAVLink. **It will not arm and it cannot fly anything.** That is correct and
  expected for a bare Pi with no autopilot HAT. If `scopenode` has a HAT, the target changes —
  see §4.

## 3. Prerequisites: the official script works here, but the default invocation is a trap

`Tools/environment_install/install-prereqs-ubuntu.sh` keys off `lsb_release -c -s`. `bookworm`,
`trixie` and `bullseye` are all in its supported list, and Raspberry Pi OS reports one of those,
so the script runs unmodified on the Pi. `[measured]`

It handles Debian's PEP 668 externally-managed-environment correctly: on bookworm/trixie it
`apt install python3-venv` and creates **`$HOME/venv-ardupilot`**, then pip-installs into that.
No `--break-system-packages` hacking required. `[measured]`

**The trap:** by default it also installs the SITL simulation stack — `wxPython`, `opencv-python`,
`matplotlib`, `scipy`, SFML/CSFML — plus coverage tooling and, if you answer the prompt wrongly,
the STM32 cross-toolchain. On ARM several of those have no wheel and build from source; this is
hours of Pi CPU for packages a native Linux-HAL build never links against. `install_ardupilot.sh`
therefore sets `SKIP_AP_GRAPHIC_ENV=1 SKIP_AP_COV_ENV=1 SKIP_AP_EXT_ENV=1 DO_AP_STM_ENV=0`. `[derived]`

## 4. Open questions — do not proceed past these blind

1. ~~Is there an autopilot HAT?~~ **Closed 2026-09-04 — Peter: bare Pi 5, no HAT.**
   Target is `--board=linux`, and `HAL_INS_NONE` above therefore applies: this build cannot arm.
2. ~~Which vehicle?~~ **Closed 2026-09-04 — Peter: `plane` only.** Script default set to match.
3. **`[gap]` Does this collide with the ADAU1860 work?** ArduPilot's Linux HAL probes I2C and SPI
   buses and, on boards that use them, drives GPIO18-21. `scopenode` currently has an ADAU1860
   overlay on **GPIO18-21** (`linux/adau1860-pi5/`). With `--board=linux` and `HAL_INS_NONE`
   nothing should be claimed, but this is asserted, not tested. Check `pinctrl` before and after
   the first run.
4. **`[gap]` Nothing in this document has been run on the hardware.** No SSH access at time of
   writing (see `RESULTS` below when it exists). Every claim above is about upstream source, not
   about `scopenode`.

## 5. Sources

- <https://github.com/ArduPilot/ardupilot/issues/26386> — Pi 5 support request, closed
- <https://ardupilot.org/dev/docs/building-setup-linux.html> — prereqs + waf flow
- `libraries/AP_HAL_Linux/{GPIO_RPI.cpp,Util_RPI.cpp}`, `libraries/AP_HAL_Linux/hwdef/`,
  `Tools/ardupilotwaf/boards.py`, `Tools/environment_install/install-prereqs-ubuntu.sh`
  — all at master `ff37fde6f13c02fb5ae32abdd07ff4f4e132cb76`
