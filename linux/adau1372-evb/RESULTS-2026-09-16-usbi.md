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

---

# Update — five replugs later, 2026-09-16

**Two of the three suspects are eliminated, and the failure has a sharper name.** Peter confirmed the
EVB is powered and `J15` (`/PD`) carries no jumper, so the part is not held in power-down. What
remains points at the I2C bus itself.

## What the one-shot established `[measured]`

Ordering every test that cannot hang before the one that can paid off:

| Test | Result |
|---|---|
| `0xB1` ping, `0xB9` LED, `0xB8`, `0xB7` | all OK, 0-1 ms — the firmware and its OUT path are healthy |
| **SPI transaction** (`wIndex = 1`) | `0xB3` OK, `0xB4` returned `ff`, `0xB6` **status 1 (success)** |
| **I2C transaction** (`wIndex = 0`) | `0xB3` OK, `0xB4` timed out, `0xB6` **status 4 (error)** |

The SPI result is the load-bearing one. SPI needs no acknowledgement from the target, so its engine
completes whether or not anything is listening — `ff` is a floating MISO, not a device answering.
**It proves the firmware, the USB path and the bus engines are fine, and isolates the fault to I2C.**

## The distinction that matters: status 4, not status 3

A plain address NAK — "nothing strapped here" — should report **status 3 ("failed")**, quickly and
harmlessly. What comes back is **status 4 ("error")**, and the transaction after it hangs forever.
That is not the signature of a wrong address. It is the signature of a **bus-level fault: SCL or SDA
held low, or missing pull-ups** (the datasheet requires 2.0 kOhm on both lines in I2C mode).

A flipped 10-pin ribbon produces exactly this. The USBi header interleaves signal and ground, so
reversing pin 1 lands the bus lines on grounds and holds them down.

## The debug loop is the real problem: one probe per replug

`[measured]` across five runs. A failed I2C transaction does not just stall the engine — it kills the
**whole firmware**. After one, `0xB1` stops answering; after another, the device stops answering its
USB **device descriptor** (`device descriptor read/64, error -110`) and the kernel drops it.
`usbi_clear.py` confirmed nothing short of a physical replug recovers it: `0xB0`, `USBDEVFS_RESET`,
the sysfs `authorized` toggle and a bus rescan all fail.

So the USBi yields **one I2C probe per physical replug**. Four candidate addresses is four replugs;
a full 7-bit sweep is 112. That is not a debugging loop anyone should run.

## What to do instead

1. `[30 seconds, no replug]` **Meter on `J1`**, board powered: DC volts on SCL and SDA. Idle I2C must
   sit at VDD_IO. Either line near 0 V *is* the fault. Check the ribbon's pin-1 orientation while the
   meter is out.
2. **Run SCL/SDA/GND to the Pi's I2C-1.** The Pi's controller has its own pull-ups, real bus-error
   recovery, and `i2cdetect` sweeps 128 addresses in a second with no replug risk — it would have
   answered this question five replugs ago. It is also the configuration
   `adau1372-pi5-overlay.dts` already expects, and the only one that gives ALSA a codec it can see.

`[assumed]` If both lines measure healthy and the Pi's own controller still finds nothing at
0x3C-0x3F, the next suspect is the control port having switched to SPI (`SS` pulled low three
times), which `usbi_probe.py --spi` covers.

## Tools added

- `usbi_oneshot.py` — the ordered diagnostic: non-bus requests, then SPI, then a single I2C attempt.
- `usbi_scan.py` — targeted probe of 0x3C-0x3F plus 0x50-0x57 (EEPROM range) as a bus control.
  Does **not** send `0xB8`/`0xB7`: their `wValue` polarity is undocumented, and the one hint in the
  protocol notes (`0xB9`: "1 = low") suggests `0xB8 = 1` may power the target *down*. Earlier runs
  sent it blindly; that was a mistake worth not repeating.

---

# USBi `J1` pinout and two free diagnostics — from AN-1006, 2026-09-16

`[fetched]` AN-1006 Rev. A (*Using the EVAL-ADUSB2EBZ*), Figure 25 (header schematic), Figure 24
(target power switch) and Table 1 (LEDs). Read off the schematic figure directly; analog.com PDFs
time out from here, this came from the RS mirror `docs.rs-online.com/fcaa/0900766b81403140.pdf`.

## `J1` on the USBi — 14-pin, odd row / even row

| pin | signal | | pin | signal |
|---|---|---|---|---|
| 1 | CLATCH2 | | 2 | CLATCH3 |
| **3** | **SCL** | | 4 | USB_CLK |
| **5** | **SDA** | | 6 | +5 V (`5V0DD_USB`) |
| 7 | COUT (SPI data from target) | | 8 | BRD_RESET |
| 9 | CCLK (SPI clock) | | 10 | CDATA (SPI data to target) |
| 11 | CLATCH1 | | **12** | **GND** |
| 13 | CLATCH4 | | 14 | CLATCH5 |

`[assumed]` The ribbon is labelled "2X5 CUSTOM RIBBON" on a 14-way body, so which ten conductors it
carries is **not** established — do not assume pins 1-10. The signal names above are certain; the
mapping onto the EVB's own header is not, because UG-807 is still unreadable from here.

On the codec itself `[ds]`, the control pins are chip **pin 1 = SDA/MISO, pin 2 = SCL/SCLK**,
pin 3 = ADDR1/MOSI, pin 4 = ADDR0/SS. Both lines need **2.0 kOhm pull-ups** in I2C mode — probing
across those resistors is far easier than probing a 40-lead LFCSP.

## Free diagnostic 1: the USBi's own LEDs (AN-1006 Table 1)

| LED | colour | meaning |
|---|---|---|
| D1 | yellow | **I2C mode is active** |
| D3 | yellow | **SPI mode is active** |
| D4 | red | 5 V being supplied over the USB bus |
| D2 | blue | GPIO LED, firmware debug |

**If D3 is lit and D1 is not, every I2C probe so far was aimed at the wrong bus** and
`usbi_probe.py --spi` is the correct run. This costs a glance and should have been the first thing
checked.

## Free diagnostic 2: SDA and SCL are gated by an analog switch

Figure 25: SCL and SDA do not run straight to `J1`. Each passes through one half of an **ADG721BRMZ
analog switch** (`U2-A`, `U2-B`), and **both halves are controlled by `USB_PWR_ON`** — the same
signal that switches target power in Figure 24. ADI's stated reason: the switch "remains open,
isolating the I2C bus from the target, until the boot process has completed", so the FX2 can boot
from its own EEPROM without the target on the bus.

**Consequence: if `USB_PWR_ON` is not asserted, SDA and SCL are physically disconnected from the
ribbon and no I2C transaction can ever complete** — which is exactly the observed failure.

### Correction to the previous entry

The previous update guessed that `0xB8` with `wValue = 1` might be powering the target *down*, and
removed it from the scripts on that basis. **That was wrong.** Figure 24 states `USB_PWR_ON` "turns
on both transistors when driven high", and AN-1006 says the SigmaStudio default is device power
**on**. So `0xB8 = 1` is almost certainly ON — and because the same signal closes the I2C isolation
switch, asserting it is a prerequisite for talking to the target at all, not a hazard. Sending it
was right; removing it was the mistake.

`[measured, unexplained]` Run 5 sent no `0xB8` and its first I2C transaction still completed (status
4), which suggests the switch is already closed after boot. That does not contradict the above, but
it does mean the switch alone does not explain the fault.

## Also worth knowing

The USBi carries **its own EEPROM at I2C address 0x51** (AN-1006 warns against putting another
EEPROM there). It sits on the FX2 side of the isolation switch, so it is not a valid control for
whether the *target* bus is alive — the 0x50-0x57 sweep in `usbi_scan.py` should be read with that
in mind.
