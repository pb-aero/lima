#!/usr/bin/env python3
"""One replug, maximum information.

Ordered so that every test which CANNOT hang runs before the one that can.
A hung I2C transaction wedges the FX2 until it is physically replugged, so the
I2C probe is deliberately last and single-shot.

  0xB9 GPIO/LED  - OUT request, touches no bus      -> proves OUT works at all
  0xB8 target power on - OUT, touches no bus        -> may BE the fix
  SPI read (wIndex=1) - SPI needs no ACK from the target, so the engine should
        always complete.  If SPI returns and I2C hangs, the firmware is fine and
        the fault is specifically the I2C bus: no pull-ups, no VDD_IO reference
        from the target, or the target unpowered.
"""
import struct, sys, time, usb.core

IN_, OUT_ = 0xC0, 0x40
I2C, SPI = 0x0000, 0x0001
TMO = 200
STATUS = {0: "none", 1: "success", 2: "in progress", 3: "failed", 4: "error"}

dev = usb.core.find(idVendor=0x0456, idProduct=0x7031)
if dev is None:
    sys.exit("no USBi on the bus - replug it")
try:
    dev.set_configuration()
except usb.core.USBError as e:
    sys.exit(f"cannot configure the USBi ({e}) - it is still wedged, REPLUG IT")
print(f"USBi bus {dev.bus} addr {dev.address}")

ping = lambda: bytes(dev.ctrl_transfer(IN_, 0xB1, 0, 0, 1, TMO))


def step(label, fn, fatal=False):
    t = time.time()
    try:
        r = fn()
        ms = (time.time() - t) * 1000
        extra = bytes(r).hex() if isinstance(r, (bytes, bytearray)) or hasattr(r, "__iter__") else str(r)
        print(f"  {label:34s} OK   {ms:6.0f} ms  {extra}")
        return r if r is not None else True
    except usb.core.USBError as e:
        print(f"  {label:34s} FAIL {(time.time()-t)*1000:6.0f} ms  {e}")
        if fatal:
            print("\n*** wedged - UNPLUG AND REPLUG THE USBi ***")
            sys.exit(1)
        return None


print("\n--- 1. liveness ---")
step("0xB1 ping", ping, fatal=True)

print("\n--- 2. requests that touch no bus ---")
step("0xB9 GPIO/LED wValue=1", lambda: dev.ctrl_transfer(OUT_, 0xB9, 1, 0, None, TMO))
step("0xB9 GPIO/LED wValue=0", lambda: dev.ctrl_transfer(OUT_, 0xB9, 0, 0, None, TMO))
step("0xB1 ping", ping, fatal=True)

print("\n--- 3. target power on (0xB8) ---")
step("0xB8 wValue=1", lambda: dev.ctrl_transfer(OUT_, 0xB8, 1, 0, None, TMO))
time.sleep(0.5)
step("0xB1 ping", ping, fatal=True)
step("0xB7 pulse reset line", lambda: dev.ctrl_transfer(OUT_, 0xB7, 0, 0, None, TMO))
time.sleep(0.3)
step("0xB1 ping", ping, fatal=True)

print("\n--- 4. SPI transaction (no ACK needed; engine should always finish) ---")
ok = step("0xB3 set read addr, SPI",
          lambda: dev.ctrl_transfer(OUT_, 0xB3, 0x3C, SPI, struct.pack(">H", 0), TMO))
if ok is not None:
    step("0xB4 read 1 byte, SPI", lambda: dev.ctrl_transfer(IN_, 0xB4, 0x3C, SPI, 1, TMO))
    st = step("0xB6 status", lambda: dev.ctrl_transfer(IN_, 0xB6, 0x3C, SPI, 1, TMO))
    if st is not None:
        print(f"      -> status {bytes(st)[0]} ({STATUS.get(bytes(st)[0], '?')})")
alive = step("0xB1 ping", ping)
if alive is None:
    print("\n*** SPI wedged it too - REPLUG. That points past the I2C bus to the")
    print("*** firmware or the ribbon itself, not to target power.")
    sys.exit(1)

print("\n--- 5. ONE I2C attempt, 0x3C only (this is the one that can wedge) ---")
ok = step("0xB3 set read addr, I2C", lambda: dev.ctrl_transfer(OUT_, 0xB3, 0x3C, I2C,
                                                               struct.pack(">H", 0), TMO))
if ok is None:
    print("\n  I2C hangs at the very first bus access, again.")
    print("  Compare against step 4: if SPI completed and I2C did not, the I2C bus")
    print("  is the fault - unpowered target, no pull-ups, or no VDD_IO reference.")
    print("\n*** REPLUG THE USBi before the next run ***")
    sys.exit(1)
step("0xB4 read 1 byte, I2C", lambda: dev.ctrl_transfer(IN_, 0xB4, 0x3C, I2C, 1, TMO))
st = step("0xB6 status", lambda: dev.ctrl_transfer(IN_, 0xB6, 0x3C, I2C, 1, TMO))
if st is not None:
    print(f"      -> status {bytes(st)[0]} ({STATUS.get(bytes(st)[0], '?')})")
    print("\n  A status byte instead of a timeout means THE I2C BUS IS ALIVE.")
    print("  Re-run usbi_probe.py for the full address scan.")
