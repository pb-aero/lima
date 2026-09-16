# W25N01GV on the Pi 5 — what the part is, and what it changes

**Date:** 2026-09-16 · **Agent:** LIMA · **Part:** Winbond `W25N01GVZEIG/IT` on a MikroElektronika
**Flash 5 Click** (MIKROE-3780) · **Target:** `aeronode` Pi 5, SPI0

Peter: *"W25N01GVZEIG/IT click board is being used for now."* This file is the part knowledge and
the plan. Nothing here has been run against the physical part yet — see Status at the bottom.

## 0. Reaching the Pi — use the NAME, not the address `[measured]` 2026-09-16

`aeronode` moves between sites and its address moves with it: **192.168.0.99 at the home office,
192.168.10.34 at the work office.** An IP hard-coded in a script or a note is a stale instrument
the next time the box moves — and it fails looking exactly like a dead Pi, which is how half an
hour went missing on 2026-09-15.

**`aeronode.local` resolves over mDNS at both sites** and is the address to use everywhere:
`ssh node@aeronode.local`. Found this way in one command after the move
(`ping aeronode.local` -> 192.168.10.34), hostname, model and kernel all matching the home-office
box exactly. Uptime 23 min at the time of the check — it had simply been powered down and moved,
not crashed.

## 1. It is NAND, not NOR — that is the whole story

`[fetched]` 1 Gbit **SLC NAND**, 2.7–3.6 V single supply, 104 MHz max clock, 25 mA active.
It is not a W25Q and it does not behave like one:

- **You cannot read an arbitrary address.** A read is two steps: `13h` Page Data Read moves one
  page into the chip's buffer, you poll SR-3 `BUSY`, then `03h`/`0Bh` reads out of the buffer.
- **Pages are 2048 + 64 bytes**, 64 pages per 128 KiB erase block, 1024 blocks = 128 MiB usable.
  The 64 spare bytes carry on-die ECC parity and the bad-block marker.
- **Blocks go bad, including at the factory.** The part ships with an internal Bad Block Management
  look-up table (`A1h`) that can remap **up to 20** blocks — that is the whole budget, and it is
  nowhere near a filesystem's needs. Real storage wants UBI on top.
- **On-die ECC** is 1 bit per 512 bytes (`NAND_ECCREQ(1, 512)` in the kernel's table).

## 2. Do not write a driver — Linux already has this exact part `[fetched]`

`drivers/mtd/nand/spi/winbond.c`, mainline:

```c
SPINAND_INFO("W25N01GV", /* 3.3V */
	     SPINAND_ID(SPINAND_READID_METHOD_OPCODE_DUMMY, 0xaa, 0x21),
	     NAND_MEMORG(1, 2048, 64, 64, 1024, 20, 1, 1, 1),
	     NAND_ECCREQ(1, 512),
```
with `#define SPINAND_MFR_WINBOND 0xEF`. **And it is already on the box** — `[measured]` the
string `W25N01GV` is present inside the shipped
`/lib/modules/6.18.39+rpt-rpi-2712/kernel/drivers/mtd/nand/spi/spinand.ko.xz`, alongside the `mtd`
and `ubi` module trees. No kernel rebuild, no out-of-tree driver, nothing to compile.
So the device tree compatible is **`jedec,spi-nand`**,
the stack is spi-nand → MTD → (UBI → UBIFS), and `/dev/mtd0` appears with no code from us.
Zephyr's own Flash 5 Click shield uses the same compatible at 104 MHz, which is a second source
for the binding.

**This is the "check the platform first" rule paying out.** Hand-rolling page reads over spidev is
a week of work to reproduce something already in the kernel, badly, without wear levelling.

## 3. Three power-up defaults that will look like faults

1. `[fetched]` **The array is write-protected out of the box.** "The default values for the Block
   Protection bits are 1 after power up to protect the entire array." Every program and erase fails
   until SR-1 (address `A0h`) is cleared to `0x00`. A first-write failure here is the part working
   as designed.
2. `[fetched]` **`IG` and `IT` power up in different read modes.** For `W25N01GVxxIG` the `BUF` bit
   defaults to **1** (buffer read); for `W25N01GVxxIT` it defaults to **0** (continuous read). The
   click board is sold as `ZEIG/IT`, so **which one is on the board decides how a hand-written read
   behaves** — and the two are not compatible. Under Linux this evaporates: `winbond_spinand_init()`
   forces `WINBOND_CFG_BUF_READ` on every die precisely to "make sure all dies are in buffer read
   mode and not continuous read mode." One more argument for the MTD route over spidev.
3. `[fetched]` **`/WP` and `/HOLD` need no wiring in single-bit SPI.** WP-E defaults to 0, and with
   WP-E = 0 "the device is in Software Protection mode, /WP & /HOLD pins are multiplexed as IO
   pins". They only become dedicated protection inputs if WP-E is set to 1.

## 4. The chip select is now a blocker, not a footnote

`[measured]` `/boot/firmware/config.txt` carries `dtoverlay=spi0-0cs` — **no chip select is driven
at all**, and `pinctrl` confirms GPIO7 and GPIO8 are unclaimed. That was harmless for the loopback.
It is fatal here: the W25N frames every instruction between `/CS` falling and rising, so with no CS
the part will never answer and will read as dead or absent.

**Fix: `dtoverlay=spi0-1cs`** — CE0 on **GPIO8, header pin 24**, leaving GPIO7 free. Deliberately
not `spi0-2cs`: config.txt carries a comment describing a dedicated I2C bus on **GPIO6/7** for the
Waveshare IMU, so CE1 on GPIO7 is the one pin here with a known claimant. `[measured]` it is not
claimed *right now*, but taking it would collide the moment that overlay is loaded.

This needs a config.txt edit and a reboot, which is Peter's call, not mine.

## 5. Wiring — Pi 5 header to the click board

| Signal | Pi 5 GPIO | Header pin | Click |
|---|---|---|---|
| MOSI (DI) | GPIO10 | 19 | SDI |
| MISO (DO) | GPIO9 | 21 | SDO |
| SCLK | GPIO11 | 23 | SCK |
| /CS | GPIO8 (CE0) | 24 | CS |
| 3V3 | — | 1 or 17 | 3V3 |
| GND | — | 25 (or 6, 9, 20, 39) | GND |

`[fetched]` The click board is a 3.3 V part on a 3.3 V supply and the Pi's GPIO is 3.3 V, so there
is no level shifting to do — unlike the ADAU1860 EVB work, where 1.98 V IOVDD was the problem.

## 6. Order of operations

1. **Fix the CS** — `spi0-1cs` in config.txt, reboot, `pinctrl get 8` must show `SPI0_CE0`.
2. **Probe read-only over spidev** — `w25n01gv-probe.py`. Expect `EF AA 21`, and read SR-1/2/3.
   This proves the wiring, the power and the part, and it tells us **IG or IT** by reading the
   `BUF` bit before anything touches it. It writes nothing.
3. **Only then hand it to the kernel** — build `w25n01gv-spi-nand-overlay.dts`, which disables
   `spidev0.0` and puts `jedec,spi-nand` on CE0 at a conservative 25 MHz. `cat /proc/mtd` must show
   one 128 MiB device. `[gap]` the overlay compiles clean under `dtc -@` on the Mac, which proves
   **syntax only** — that it binds is unproven until it runs.
4. **Then decide the filesystem.** Raw MTD is fine for an append-only recorder; UBI+UBIFS is the
   answer if it must survive power loss and wear. That decision belongs to what AeroVault is for,
   which I still do not know.

## Status / open

- `[gap]` **What is AeroVault meant to do?** Storage capacity, retention, write rate, and whether it
  must survive power loss mid-write all change step 4. 128 MiB is small — it is a log or a
  config/key vault, not a data recorder.
- `[gap]` **How is the click board physically connected?** mikroBUS shield, or flying leads to the
  header? Nothing is wired yet as far as I know.
- ~~`aeronode` unreachable~~ **CLOSED 2026-09-16** — not a fault. The Pi had moved office with
  Peter; it is up at `aeronode.local` (192.168.10.34) and the SPI0 loopback still passes
  byte-clean to 50 MHz after the reboot. See §0: address the box by name from now on.

## Sources

- Winbond W25N01GV datasheet rev L, 2018-05-09 (`winbond.com/resource-files/w25n01gv revl 050918
  unsecured.pdf`) — status registers §7, block protect defaults §7.1.1, WP-E §7.1.2, BUF §7.2,
  JEDEC ID §8.2, BBM `A1h` §8.2.7, 104 MHz / 2.7–3.6 V §1.
- Linux mainline `drivers/mtd/nand/spi/winbond.c`.
- MikroElektronika Flash 5 Click product page (`mikroe.com/flash-5-click`) — **403 to WebFetch from
  this machine**, same bot-block class as the analog.com and mouser scars; specifications above
  come from the search summary and Zephyr's shield overlay, not from the page itself.
- Zephyr `boards/shields/mikroe_flash_5_click/` — `jedec,spi-nand`, 104 MHz, CS on mikroBUS pin 2.
