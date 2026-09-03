#!/usr/bin/env python3
"""Capture accelerometer data from an MPU-9250 using its hardware FIFO.

The FIFO matters: polling from userspace over I2C jitters by hundreds of
microseconds, and jitter smears an FFT. The FIFO timestamps implicitly -- the
device fills it at an exact internal rate, so every sample is uniformly spaced
regardless of when we happen to drain it.
"""
import argparse, struct, sys, time
from smbus2 import SMBus
import numpy as np

A = 0x68
PWR_MGMT_1, SMPLRT_DIV, CONFIG, ACCEL_CONFIG, ACCEL_CONFIG2 = 0x6B, 0x19, 0x1A, 0x1C, 0x1D
FIFO_EN, USER_CTRL, INT_STATUS, FIFO_COUNTH, FIFO_R_W = 0x23, 0x6A, 0x3A, 0x72, 0x74

ap = argparse.ArgumentParser()
ap.add_argument("--bus", type=int, default=2)
ap.add_argument("--seconds", type=float, default=10.0)
ap.add_argument("--rate", type=int, default=1000, help="Hz; internal is 1 kHz / (1+div)")
ap.add_argument("--fs-g", type=int, default=2, choices=(2,4,8,16))
ap.add_argument("--out", default="/tmp/accel.npy")
args = ap.parse_args()

div = max(0, round(1000/args.rate) - 1)
fs  = 1000.0/(1+div)
afs = {2:0,4:1,8:2,16:3}[args.fs_g]
lsb_per_g = {2:16384.0,4:8192.0,8:4096.0,16:2048.0}[args.fs_g]

with SMBus(args.bus) as b:
    b.write_byte_data(A, PWR_MGMT_1, 0x80); time.sleep(0.1)   # reset
    b.write_byte_data(A, PWR_MGMT_1, 0x01); time.sleep(0.05)  # wake, PLL
    # CONFIG DLPF_CFG MUST be 1..6. At 0 or 7 the internal rate is 8 kHz, not
    # 1 kHz, and SMPLRT_DIV then divides 8 kHz -- the FIFO fills 8x faster than
    # requested and overflows no matter how low you set --rate. [measured]
    b.write_byte_data(A, CONFIG,        0x03)                 # DLPF 41 Hz -> internal 1 kHz
    b.write_byte_data(A, ACCEL_CONFIG,  afs << 3)
    # Accel anti-alias filter chosen against the actual sample rate, so the
    # analogue band always sits below Nyquist.
    a_dlpf = 0x00 if fs >= 500 else (0x02 if fs >= 250 else 0x03)   # 218 / 99 / 45 Hz
    a_dlpf_hz = {0x00:218.1, 0x02:99.0, 0x03:44.8}[a_dlpf]
    b.write_byte_data(A, ACCEL_CONFIG2, a_dlpf)
    print(f"# accel DLPF {a_dlpf_hz} Hz vs Nyquist {fs/2:.0f} Hz", file=sys.stderr)
    b.write_byte_data(A, SMPLRT_DIV,    div)
    time.sleep(0.05)

    # Empirical throughput -- measured with 30-byte BURSTS, which is how the FIFO
    # is actually drained (5 samples per transaction). Measuring single 6-byte
    # reads understates capacity badly and is what led me to overrun the FIFO.
    t0=time.time()
    for _ in range(100): b.read_i2c_block_data(A, 0x3B, 6)
    per6 = (time.time()-t0)/100
    t0=time.time()
    for _ in range(100): b.read_i2c_block_data(A, FIFO_R_W, 30)
    per30 = (time.time()-t0)/100
    sps = 5/per30
    print(f"# i2c: {per6*1e6:.0f} us per 6B read; {per30*1e6:.0f} us per 30B burst "
          f"-> ~{sps:.0f} samples/s sustainable", file=sys.stderr)
    if sps < fs*2:
        sys.exit(f"REFUSING: bus sustains ~{sps:.0f} samples/s, which is not 2x the "
                 f"requested {fs:.0f} Hz. Lower --rate or raise the I2C baudrate.")

    b.write_byte_data(A, USER_CTRL, 0x04); time.sleep(0.05)   # FIFO reset
    b.write_byte_data(A, FIFO_EN,   0x08)                     # accel only
    b.write_byte_data(A, USER_CTRL, 0x40)                     # FIFO enable
    t_start=time.time(); raw=bytearray(); overflow=False
    while time.time()-t_start < args.seconds:
        if b.read_byte_data(A, INT_STATUS) & 0x10:
            overflow=True; break          # abort immediately: after an overflow the
                                          # byte stream is misaligned and every later
                                          # sample is fiction. Do not keep going.
        n = struct.unpack(">H", bytes(b.read_i2c_block_data(A, FIFO_COUNTH, 2)))[0]
        n -= n % 6
        while n >= 6:
            c = min(n, 30)
            raw += bytes(b.read_i2c_block_data(A, FIFO_R_W, c)); n -= c
    b.write_byte_data(A, FIFO_EN, 0x00)
    if overflow:
        sys.exit("REFUSING: FIFO overflowed -- samples were lost and the stream is "
                 "misaligned. Any spectrum from this would be fiction. Lower --rate.")

nsamp = len(raw)//6
d = np.frombuffer(bytes(raw[:nsamp*6]), dtype=">i2").reshape(-1,3).astype(np.float64)/lsb_per_g
# Gate on physics before saving: a stationary-ish sensor must read ~1 g.
mag = np.linalg.norm(d.mean(axis=0))
if not (0.90 < mag < 1.10):
    sys.exit(f"REFUSING: mean |a| = {mag:.3f} g, expected ~1.0. The stream is "
             f"misaligned or the scale factor is wrong. Not saving.")
if nsamp < args.seconds*fs*0.9:
    sys.exit(f"REFUSING: got {nsamp} samples, expected ~{args.seconds*fs:.0f}. Samples were dropped.")
np.save(args.out, d)
print(f"# captured {nsamp} samples at {fs:.1f} Hz = {nsamp/fs:.2f} s -> {args.out}", file=sys.stderr)
print(f"# FIFO overflow: {overflow}", file=sys.stderr)
print(f"# mean g: {d.mean(axis=0)}  |a|={np.linalg.norm(d.mean(axis=0)):.4f}", file=sys.stderr)
print(f"# AC rms (mg): {d.std(axis=0)*1000}", file=sys.stderr)
