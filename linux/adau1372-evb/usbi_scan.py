#!/usr/bin/env python3
"""Careful I2C probe through a USBi.  Revised after run 4 wedged.

Two changes from the run that wedged:
  * 0xB8 (target power) and 0xB7 (reset pulse) are NOT sent.  Their wValue
    semantics are undocumented - for 0xB9 the note is "1 = low" - so 0xB8=1 may
    be powering the target DOWN, not up.  The EVB has its own supply; leave it
    alone.
  * The 0xB4 read gets a long timeout.  On run 3 a NAK showed up as a 0xB4
    timeout followed by status 4, with the firmware still alive - so a read
    timeout is a RESULT, not a failure, as long as the ping still answers.

0x50-0x57 is swept as an independent control: most ADI eval boards carry an I2C
EEPROM there.  If the EEPROM ACKs, the bus is proven good and the codec's
silence is real rather than a bus fault.
"""
import struct, sys, time, usb.core

IN_, OUT_, I2C = 0xC0, 0x40, 0x0000
TMO, RTMO = 300, 1500
STATUS = {0: "none", 1: "success", 2: "in progress", 3: "failed", 4: "error"}

dev = usb.core.find(idVendor=0x0456, idProduct=0x7031)
if dev is None:
    sys.exit("no USBi - replug it")
try:
    dev.set_configuration()
except usb.core.USBError as e:
    sys.exit(f"still wedged ({e}) - REPLUG")
ping = lambda: bytes(dev.ctrl_transfer(IN_, 0xB1, 0, 0, 1, TMO))
print(f"USBi bus {dev.bus} addr {dev.address}; ping -> {ping().hex()}")


def probe(chip, reg=0x0000):
    dev.ctrl_transfer(OUT_, 0xB3, chip, I2C, struct.pack(">H", reg), TMO)
    data = None
    try:
        data = bytes(dev.ctrl_transfer(IN_, 0xB4, chip, I2C, 1, RTMO))
    except usb.core.USBError:
        pass                                    # NAK looks like this; status tells us
    st = bytes(dev.ctrl_transfer(IN_, 0xB6, chip, I2C, 1, TMO))[0]
    return st, data


targets = [(c, "ADAU1372 candidate") for c in (0x3C, 0x3D, 0x3E, 0x3F)] + \
          [(c, "EEPROM range - bus control") for c in range(0x50, 0x58)]

print("\n--- targeted probe ---")
hits = []
for chip, why in targets:
    try:
        st, data = probe(chip)
    except usb.core.USBError as e:
        print(f"  0x{chip:02X}: transfer refused ({e})")
        break
    d = data.hex() if data else "--"
    print(f"  0x{chip:02X}: status {st} ({STATUS.get(st,'?'):11s}) data={d:4s} {why}")
    if st == 1:
        hits.append(chip)
    try:
        ping()
    except usb.core.USBError:
        print(f"\n*** firmware wedged after 0x{chip:02X} - REPLUG ***")
        sys.exit(1)

if not hits:
    print("\nNothing ACKed - not the codec, not an EEPROM.")
    print("If the EEPROM is also silent the bus itself is still the suspect:")
    print("  * J15 (/PD) jumper fitted = the ADAU1372 is powered DOWN and will not ACK")
    print("  * ribbon on J1 / pin-1 orientation")
    print("  * control port switched to SPI (SS pulled low three times)")
    sys.exit(0)

print("\n--- reset-value check (positive control) ---")
EXPECT = {0x1B: 0x19, 0x1C: 0x19, 0x23: 0x40, 0x29: 0x3F,
          0x2E: 0x18, 0x31: 0x0F, 0x3E: 0x11}
for chip in hits:
    good = 0
    for reg, exp in EXPECT.items():
        st, data = probe(chip, reg)
        v = data[0] if data else None
        good += (v == exp)
        print(f"  {'OK ' if v == exp else '   '}0x{chip:02X} reg 0x{reg:02X}: "
              f"read {'--' if v is None else f'{v:02X}'}  expect {exp:02X}  status {st}")
    print(f"  => 0x{chip:02X}: {good}/{len(EXPECT)} "
          f"{'CONFIRMED ADAU1372' if good >= 5 else 'answers, but not an ADAU1372 at reset'}")
