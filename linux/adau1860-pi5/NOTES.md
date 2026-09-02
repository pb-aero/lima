# ADAU1860 on Raspberry Pi 5 — bring-up notes

**Date:** 2026-09-02 · **Agent:** LIMA

Peter's bench rig: ADAU1860 wired to a Pi 5 — **I2C for control, I2S on GPIO 18–21, codec as
clock master.** These are the facts established before any code was written, with sources.

Provenance: `[measured]` = I fetched the file and grepped it myself · `[fetched]` = read from a
vendor document I retrieved · `[derived]` = reasoned from a source, reasoning shown ·
**`[gap]`** = not established, do not assume.

---

## 1. The headline: there is no ADAU1860 driver in Linux

`[measured]` I pulled `sound/soc/codecs/Kconfig` from both kernel trees and grepped for `1860`:

| Tree | Fetch | ADAU parts present | `1860` hits |
|---|---|---|---|
| `torvalds/linux` @ master | HTTP 200, 71209 bytes | 1372, 1373, 1701, 1761, 1781, 1977, 7002, 7118 | **0** |
| `analogdevicesinc/linux` @ main | HTTP 200, 61168 bytes | identical list | **0** |

Instrument check: both files contain 59 and 59 case-insensitive `adau` matches respectively, so
the greps were reading real content, not an empty download.

ADI *does* publish a driver doc URL — `wiki.analog.com/.../sound/adau1860` 301-redirects to
`developer.analog.com/docs/linux/drivers/sound/adau1860.html`, so the page is real — but that host
returns **HTTP 403** to curl and a certificate failure to the other fetcher. Its contents are
**Unknown**. Not "no driver", not "there is a driver". Open this in a browser to close it.

**Consequence:** nothing will bind to the chip. The Pi can be made to clock and stream, but every
register in the ADAU1860 has to be written from userspace over `i2c-dev` until a codec driver exists.

## 2. Codec-as-master IS supported on Pi 5, on those exact pins

This was the real risk and it resolves in our favour. RP1 exposes **three** DesignWare I2S blocks
`[measured]`, `arch/arm64/boot/dts/broadcom/rp1.dtsi`:

```
rp1_i2s0: i2s@a0000   compatible = "snps,designware-i2s"
rp1_i2s1: i2s@a4000   compatible = "snps,designware-i2s"
rp1_i2s2: i2s@a8000   compatible = "snps,designware-i2s"
```

and two pinctrl groups that both land on **GPIO 18, 19, 20, 21** — `rp1_i2s0_18_21` (function
`i2s0`) and `rp1_i2s1_18_21` (function `i2s1`).

`arch/arm64/boot/dts/broadcom/bcm2712-rpi.dtsi` then aliases them by clock role `[measured]`:

```
i2s:              &rp1_i2s0 { };
i2s_clk_producer: &rp1_i2s0 { };   // Pi drives BCLK/LRCLK
i2s_clk_consumer: &rp1_i2s1 { };   // external codec drives BCLK/LRCLK   <-- ours
```
…with `pinctrl-0 = <&rp1_i2s1_18_21>` already attached to the consumer node (line ~451).

**Why two blocks rather than one switchable block.** `sound/soc/dwc/dwc-i2s.c` decides direction
from a hardware synthesis parameter, and it is *exclusive* `[measured]`:

```c
if (COMP1_MODE_EN(comp1)) {
        dev->capability |= DW_I2S_MASTER;
} else {
        dev->capability |= DW_I2S_SLAVE;
}
```

`dw_i2s_set_fmt()` then rejects `SND_SOC_DAIFMT_BC_FC` (bit-clock-consumer / frame-consumer) unless
`DW_I2S_SLAVE` is set. So one RP1 block can *never* be talked into slave mode — you have to select
the other one. **Pointing a codec-master card at `&i2s` or `&i2s_clk_producer` will fail**, and it
will fail as an `-EINVAL` from `set_fmt`, not as anything that looks like a wiring problem. This is
almost certainly what the February 2026 CM5 forum report ("I2S1 slave mode, external clock not
detected") ran into from the other direction.

`[derived]` GPIO 18–21 gives BCLK, LRCLK/FS, DIN, DOUT — **there is no MCLK pin in that group**.
That is fine here precisely *because* the codec is master: the ADAU1860 makes its own master clock
(the ADI eval board uses an on-board 24.576 MHz oscillator `[fetched]`, UG-2017 Table 1). If the Pi
were ever made master this becomes a blocker, not an inconvenience.

## 3. I2C address

`[fetched]` EVAL-ADAU1860 user guide UG-2017, Table 3 ("Control Port Jumper and Switch Settings"):

> I2C — S14, default **0x64** (00), **0x65** (01), **0x66** (10), **0x67** (11)

selected by the `ADDR0`/`ADDR1` pins (UG Table: `P1 ADDR1_MOSI/UART_RX`, `P4 ADDR0_SS/IOVDD` — the
same pins are SPI MOSI and SS, so the part picks its control port from how they are strapped).

`[derived]` **These are 7-bit addresses** — four values for two address bits stepping by 1. Had ADI
quoted 8-bit write addresses they would step by 2 (0x64, 0x66, 0x68, 0x6A). So `i2cdetect` should
show one of `0x64`–`0x67` directly. One command confirms it; do not build on the derivation.

Note the eval board ships in **SPI** mode by default and needs S1 up plus four jumpers moved to
pin 2–3 to become an I2C part `[fetched]`. Worth checking what our board actually straps.

## 4. What is in this directory

`adau1860-pi5-overlay.dts` — a device-tree overlay that brings up `rp1_i2s1` on GPIO 18–21 with the
**codec as bitclock and frame master**, using the in-tree `linux,spdif-dit` dummy codec as a stand-in
for the missing driver.

`[measured]` It compiles: `dtc 1.8.1 -@ -I dts -O dtb` exits 0, 1427 bytes, and the resulting
`__fixups__` node references exactly two external labels — `i2s_clk_consumer` and `sound` — both of
which are confirmed present in `bcm2712-rpi.dtsi` (lines 387 and 373). So the overlay will resolve
on a Pi 5. **Compiling is not running**: it has not been loaded on hardware.

## 5. Known limitation — this gets you playback only

`[measured]` `sound/soc/codecs/spdif_transmitter.c` declares `dit_stub_dai` with `.playback` and
**no `.capture` member**. The dummy codec is a sink. The capture-only twin is `linux,spdif-dir`
(`spdif_receiver.c`, `.capture` at line 51), and you cannot hang both on one `simple-audio-card`
DAI link because there is a single cpu DAI.

So the ADAU1860's three analog inputs and eight PDM mic channels are **not reachable through this
overlay**. Getting simultaneous play and capture needs a real codec driver declaring one DAI with
both directions. That is the next piece of work if capture matters.

## 6. Suggested bring-up order

1. `i2cdetect -y 1` → expect a device at `0x64`–`0x67`. If nothing: the part is strapped for SPI or
   UART, not I2C (§3).
2. Read a known register over `i2c-dev` and check it against the reset value. **`[gap]` — I do not
   have the ADAU1860 register map.** ADI's datasheet PDF is blocked to me (analog.com HTTP/2
   `INTERNAL_ERROR`, Mouser's mirror serves a 13 KB HTML block page in place of the PDF). Someone
   needs to fetch `adau1860.pdf` by hand.
3. Program the serial port for master mode and let it free-run BCLK/FS off its 24.576 MHz MCLK.
   Confirm on a scope **before** blaming Linux — a Pi in consumer mode with no incoming clock looks
   exactly like a broken driver.
4. Install the overlay, `dtoverlay=adau1860-pi5`, reboot, `aplay -l`.
5. `speaker-test -D hw:adau1860 -c 2 -r 48000 -F S32_LE`.

## 7. Open questions for Peter

- **Is this the AeroNode audio path?** `kicad/aeronode/doc/ARCHITECTURE.md` commits the board to an
  A2B main node on **SAI3** with I2C3 reserved for its control port. A TDM16-capable codec on a
  bench Pi looks a lot like a prototype of that. If it is, these notes belong against the aeronode
  design and the register work is reusable. If it is a separate experiment, say so and I will keep
  the two apart.
- **Playback only, or do you need the mics?** That is the difference between the overlay above and
  writing an ADAU1860 codec driver.
- **Which I2C bus and what is strapped on ADDR0/ADDR1?**

## Sources

- <https://www.analog.com/en/products/adau1860.html> — part overview (3 in / 1 out, 8 PDM mic in,
  two 16-channel serial ports to TDM16, dual Tensilica HiFi 3z DSP, 106 dB ADC / 110 dB DAC SNR).
- UG-2017, EVAL-ADAU1860 user guide (26 pp) — control port and address straps, on-board 24.576 MHz.
- `raspberrypi/linux` @ `rpi-6.12.y`: `arch/arm64/boot/dts/broadcom/rp1.dtsi`,
  `bcm2712-rpi.dtsi`, `arch/arm/boot/dts/overlays/i2s-master-dac-overlay.dts`,
  `sound/soc/dwc/dwc-i2s.c`, `sound/soc/codecs/spdif_transmitter.c`, `spdif_receiver.c`.
- `torvalds/linux` @ master and `analogdevicesinc/linux` @ main: `sound/soc/codecs/Kconfig`.
