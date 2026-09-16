# Can the Pi reach the ADAU1372 through the USBi? — measured 2026-09-16

Peter wired up I2S and asked whether the codec is reachable over the USB board.
**Answer: the USBi works, the I2C bus behind it does not. Nothing on the EVB answered, and
the probe left the USBi wedged — it needs a physical replug.** Host `aeronode.local`,
Pi 5 Model B Rev 1.1, kernel 6.18.39+rpt-rpi-2712.

## What is true

| Fact | Evidence |
|---|---|
| The USBi is plugged into the Pi and enumerates | `lsusb`: `Bus 003 Device 002: ID 0456:7031 Analog Devices, Inc. FX2 SPI/I2C Interface`, `dmesg` Product: `USBi` |
| No kernel driver claims it, so libusb can | `/sys/bus/usb/devices/3-1:1.0` has no `driver` symlink; vendor-specific class, 4 bulk endpoints (EP2/EP4 OUT, EP6/EP8 IN, 512 B) |
| **Its firmware is the operational image and speaks the vendor protocol** | `0xB1` ping returned `00` — a real answer, not a STALL |
| **The ADAU1372 is not on either Pi I2C bus** | `i2cdetect -y 1` -> only `0x67` (the ADAU1860); `-y 2` -> `0x5c`, `0x68`. Nothing at 0x3C-0x3F |
| **Every I2C transaction through the USBi hangs** | `0xB3` set-read-address + `0xB4` read timed out at 0x3C, 0x3D, 0x3E, 0x3F **and at the 0x3A/0x3B negative controls** |
| GPIO18-21 are muxed to I2S1 and idle low | `pinctrl get 18-21`: `I2S1_SCLK / I2S1_WS / I2S1_SDI0 / I2S1_SDO0`, all `lo` |

## What the hang means

A wrong I2C address does not hang — it NAKs, and the USBi reports it as a **status byte 3
("failed")** in a millisecond. What actually happened is the 8051 blocking forever inside its I2C
routine, identically at every address including ones with nothing strapped there. **That is the
signature of an I2C bus that cannot complete a single transaction**, not of a mis-guessed address.

Candidates, cheapest first:

1. **The EVB is not powered** (or its control-port rail is not). The codec's pull-ups and its I2C
   engine are dead without it, and the USBi will wait forever.
2. **The ribbon is not seated on `J1`**, or is on backwards.
3. **The part is in SPI mode.** `[ds]` The ADAU1372 leaves I2C for SPI if `SS` is pulled low three
   times; `usbi_probe.py --spi` re-runs the scan with the bus-format field set to SPI.
4. `[assumed]` A held-low SDA/SCL from something else on the header.

The idle-low I2S pins are **not** extra evidence of a fault — they are expected. The ADAU1372 comes
out of reset as a clock *consumer* with `SAI_MS = 0`, so it drives nothing until registers are
written. No control port, no clocks, no capture. Control access is the gate on everything.

## The scar: a failed I2C transaction bricks the USBi until it is replugged

The firmware has no I2C timeout. After the reads hung, it stopped answering `0xB1`, then stopped
answering the **USB device descriptor** itself:

```
usb 3-1: device descriptor read/64, error -110
usb 3-1: USB disconnect, device number 2
```

`USBDEVFS_RESET` returned `ENODEV`, the sysfs `authorized` toggle had nothing left to toggle, and a
bus rescan found nothing. **Only a physical unplug/replug recovers it.** `usbi_probe.py` now pings
first, scans one address at a time, and bails the moment a transfer hangs — so a bad run costs one
replug, not six.

## The alternative worth taking

The USBi path is an undocumented protocol, wedges hard on error, and gives the kernel nothing —
no ASoC driver, no ALSA controls, and a codec ALSA cannot see. **Wiring the EVB's control port
(SCL/SDA/GND) to the Pi's own I2C-1 instead** makes the part appear in `i2cdetect` at 0x3C-0x3F and
hands it to the mainline `adi,adau1372` driver, which is what `adau1372-pi5-overlay.dts` expects.
The USBi is then only needed if SigmaStudio is wanted. Both cannot own the bus at once.

## Next

1. **Replug the USBi** (only Peter can).
2. Confirm the EVB has power and the ribbon is on `J1`.
3. `sudo -n PYTHONPATH=... python3 ~/adau1372/usbi_probe.py` — ping must answer, then the scan must
   produce a *status byte*, not a timeout. Status 3 everywhere would be good news: the bus works and
   only the address is wrong. Then `--spi`.
4. Preferred: run two wires to Pi I2C-1 and let `i2cdetect` settle it in a second.

## Tools

- `usbi_probe.py` — ping, address scan with a negative control, reset-value check against the
  datasheet (`0x1B=0x19, 0x23=0x40, 0x29=0x3F, 0x2E=0x18, 0x31=0x0F, 0x3E=0x11`). Reading those back
  exactly is the positive control; it cannot happen by accident.
- Needs `pyusb` (installed on `aeronode` for user `node`) and root:
  `sudo -n PYTHONPATH=/home/node/.local/lib/python3.13/site-packages python3 ~/adau1372/usbi_probe.py`
- USBi vendor protocol reference: <https://github.com/wwolandaz/m1-drv-public/blob/HEAD/PROTOCOL.md>
  (recovered by firmware disassembly and confirmed against SigmaStudio's own driver; ADI has never
  published it).
