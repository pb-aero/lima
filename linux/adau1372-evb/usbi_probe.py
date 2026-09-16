#!/usr/bin/env python3
"""Probe an ADAU1372 through an ADI USBi (EVAL-ADUSB2EBZ, 0456:7031).

USBi vendor protocol - control transfers on EP0, 64-byte max, 2 of which are the
16-bit register address (which is exactly what the ADAU1372 wants):
  0xB1 IN  ping      0xB2 OUT write (2-byte reg addr + data)
  0xB3 OUT set read address    0xB4 IN read wLength bytes
  0xB5 IN  status of last write     0xB6 IN status of last read
  wValue = 7-bit chip address UNSHIFTED.  wIndex = 0 I2C, 1 SPI.
  status byte: 0 none, 1 success, 2 in progress, 3 failed, 4 error.

*** TWO WAYS THIS BITES, BOTH MEASURED 2026-09-16 ***
1. Direction is load-bearing.  An IN-only request sent as an OUT transfer is
   never answered and the firmware has no timeout.
2. A blocking I2C transaction that never completes wedges the 8051 HARD.  It
   stops answering the ping, then stops answering the USB device descriptor
   (dmesg: "device descriptor read/64, error -110"), and the kernel drops it.
   No ioctl reset, sysfs deauthorize or bus rescan brings it back - it takes a
   PHYSICAL REPLUG.  So: ping first, one address at a time, bail on first hang.
"""
import struct, sys, time, usb.core

VID, PID = 0x0456, 0x7031
IN_, OUT_ = 0xC0, 0x40
I2C, SPI = 0x0000, 0x0001
TMO = 150                     # short on purpose: a hang costs a replug
STATUS = {0: "none", 1: "success", 2: "in progress", 3: "failed", 4: "error"}
# Datasheet reset values - reading these back exactly is the positive control.
EXPECT = {0x1B: 0x19, 0x1C: 0x19, 0x23: 0x40, 0x29: 0x3F,
          0x2E: 0x18, 0x31: 0x0F, 0x3E: 0x11}

bus_fmt = SPI if "--spi" in sys.argv else I2C

dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    sys.exit("no USBi at 0456:7031 - if it was there a moment ago it is wedged: REPLUG IT")
dev.set_configuration()
print(f"USBi: bus {dev.bus} addr {dev.address}  {dev.manufacturer} {dev.product}")


def ping():
    return bytes(dev.ctrl_transfer(IN_, 0xB1, 0, 0, 1, TMO))


def alive(where):
    try:
        ping()
        return True
    except usb.core.USBError:
        print(f"\n*** firmware wedged at: {where} ***")
        print("*** UNPLUG AND REPLUG THE USBi - nothing in software recovers it ***")
        return False


print("\n--- liveness ---")
try:
    print("0xB1 ping ->", ping().hex(), "(firmware alive, vendor protocol answering)")
except usb.core.USBError as e:
    sys.exit(f"ping failed: {e}\nThe USBi is wedged or running non-operational firmware. REPLUG IT.")

# One address at a time, stopping the moment the bus hangs.  0x3A is the
# negative control: nothing is strapped there, so it must fail - but it should
# fail as a NAK (status 3), fast, not as a hang.  A hang on EVERY address means
# the I2C bus itself is not usable: target unpowered, pull-ups dead, ribbon not
# seated on J1, or the part switched to SPI mode.
print(f"\n--- address scan ({'SPI' if bus_fmt else 'I2C'}), register 0x0000 ---")
found = []
for chip in (0x3C, 0x3D, 0x3E, 0x3F, 0x3A):
    tag = "   <- negative control" if chip == 0x3A else ""
    try:
        dev.ctrl_transfer(OUT_, 0xB3, chip, bus_fmt, struct.pack(">H", 0), TMO)
        data = bytes(dev.ctrl_transfer(IN_, 0xB4, chip, bus_fmt, 1, TMO))
        st = bytes(dev.ctrl_transfer(IN_, 0xB6, chip, bus_fmt, 1, TMO))[0]
        print(f"  0x{chip:02X}: data={data.hex()} status={st} ({STATUS.get(st,'?')}){tag}")
        if st == 1 and chip != 0x3A:
            found.append(chip)
    except usb.core.USBError as e:
        print(f"  0x{chip:02X}: {e}{tag}")
        if not alive(f"address 0x{chip:02X}"):
            sys.exit(1)

if not found:
    sys.exit("\nno chip answered. Check: EVB powered? ribbon seated on J1? "
             "control-port pull-ups alive? part in SPI mode (try --spi)?")

print("\n--- reset-value check (positive control) ---")
for chip in found:
    good = 0
    for reg, exp in EXPECT.items():
        dev.ctrl_transfer(OUT_, 0xB3, chip, bus_fmt, struct.pack(">H", reg), TMO)
        v = bytes(dev.ctrl_transfer(IN_, 0xB4, chip, bus_fmt, 1, TMO))
        st = bytes(dev.ctrl_transfer(IN_, 0xB6, chip, bus_fmt, 1, TMO))[0]
        v = v[0] if v else None
        good += (v == exp)
        print(f"  {'OK ' if v == exp else '   '}0x{reg:02X}: read {'--' if v is None else f'{v:02X}'}"
              f"  expect {exp:02X}  status {st}")
    print(f"  chip 0x{chip:02X}: {good}/{len(EXPECT)} match -> "
          f"{'CONFIRMED ADAU1372' if good >= 5 else 'something answers, but it is not an ADAU1372 at reset'}")
