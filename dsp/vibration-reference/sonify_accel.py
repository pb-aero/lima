#!/usr/bin/env python3
"""Make the accelerometer audible through the ADAU1860's headphone output.

    python3 sonify_accel.py --mode live  --seconds 30 | \
      aplay -D hw:0,0 -f S32_LE -c 4 -r 48000 -t raw
    python3 sonify_accel.py --mode pitch --capture 20 --play 8 | \
      aplay -D hw:0,0 -f S32_LE -c 4 -r 48000 -t raw

**Why a shift is not optional.** The vibration band on this rig is 3-25 Hz with
the dominant line at 8.30 Hz (`README_FIR.md`, measured 2026-09-03). Human
hearing starts around 20 Hz and a headphone driver does nothing useful below
about 50 Hz, so playing accelerometer samples straight out is silence. Both
modes below move the content up; they differ in what they preserve.

  pitch  Capture at fs, emit the samples at 48 kHz. Speed-up = 48000/fs (48x at
         fs=1000), so 8.3 Hz lands at ~398 Hz. The spectrum is preserved
         exactly, just scaled -- ratios between peaks survive, so two lines an
         octave apart still sound an octave apart. Not real time: 20 s of
         vibration becomes 0.42 s of audio, so it is looped.

  live   Real time. High-pass, upsample to 48 kHz, then multiply by a carrier
         (DSB). 8.3 Hz becomes 1000 +/- 8.3 Hz. Tap the bench and you hear it
         immediately. The spectrum is preserved but mirrored about the carrier,
         so it is a monitor, not an analysis tool.

Output is raw S32_LE, 4 channels, 48 kHz -- audio in slot 0 (the slot the
ADAU1860's DAC_ROUTE0 reads), zeros elsewhere. Requires the codec to be
configured and unmuted; see RESULTS-2026-09-07.md.
"""
import argparse, struct, sys, time
import numpy as np
from smbus2 import SMBus

A = 0x68
PWR_MGMT_1, SMPLRT_DIV, CONFIG, ACCEL_CONFIG, ACCEL_CONFIG2 = 0x6B, 0x19, 0x1A, 0x1C, 0x1D
FIFO_EN, USER_CTRL, INT_STATUS, FIFO_COUNTH, FIFO_R_W = 0x23, 0x6A, 0x3A, 0x72, 0x74
OUT_RATE, SLOTS = 48000, 4


def setup(bus, rate, fs_g):
    """Same register sequence as capture_mpu.py -- see its comments for why."""
    div = max(0, round(1000 / rate) - 1)
    fs = 1000.0 / (1 + div)
    afs = {2: 0, 4: 1, 8: 2, 16: 3}[fs_g]
    lsb = {2: 16384.0, 4: 8192.0, 8: 4096.0, 16: 2048.0}[fs_g]
    bus.write_byte_data(A, PWR_MGMT_1, 0x80); time.sleep(0.1)
    bus.write_byte_data(A, PWR_MGMT_1, 0x01); time.sleep(0.05)
    bus.write_byte_data(A, CONFIG, 0x03)              # DLPF 41 Hz -> internal 1 kHz
    bus.write_byte_data(A, ACCEL_CONFIG, afs << 3)
    # A_DLPF_CFG 7 returns corrupt data on this part -- 0x00 is the widest usable.
    bus.write_byte_data(A, ACCEL_CONFIG2, 0x00 if fs >= 500 else (0x02 if fs >= 250 else 0x03))
    bus.write_byte_data(A, SMPLRT_DIV, div); time.sleep(0.05)
    bus.write_byte_data(A, USER_CTRL, 0x04); time.sleep(0.05)   # FIFO reset
    bus.write_byte_data(A, FIFO_EN, 0x08)                       # accel only
    bus.write_byte_data(A, USER_CTRL, 0x40)                     # FIFO enable
    return fs, lsb


def drain(bus, lsb):
    """Return whatever whole samples are in the FIFO, as an (n,3) array in g."""
    if bus.read_byte_data(A, INT_STATUS) & 0x10:
        print("# FIFO OVERFLOW -- samples lost, stream realigning", file=sys.stderr)
        bus.write_byte_data(A, USER_CTRL, 0x04); bus.write_byte_data(A, USER_CTRL, 0x40)
        return np.zeros((0, 3))
    n = struct.unpack(">H", bytes(bus.read_i2c_block_data(A, FIFO_COUNTH, 2)))[0]
    n -= n % 6
    raw = bytearray()
    while n >= 6:
        c = min(n, 30)
        raw += bytes(bus.read_i2c_block_data(A, FIFO_R_W, c)); n -= c
    k = len(raw) // 6
    if not k:
        return np.zeros((0, 3))
    return np.frombuffer(bytes(raw[:k * 6]), dtype=">i2").reshape(-1, 3).astype(np.float64) / lsb


def gate(y, fs, gate_db, win_s, pad_s, peak_db=None):
    """Keep only the stretches that rise gate_db above the noise floor.

    The floor is the MEDIAN window RMS, not the mean: the events are exactly what
    we are looking for, and a mean is dragged upward by them, which raises the
    bar in proportion to how much there was to find.
    """
    w = max(1, int(win_s * fs))
    n = (y.size // w) * w
    if n == 0:
        return np.zeros(0), {"floor": 0, "thresh": 0, "peak": 0, "peak_db": 0,
                             "kept_s": 0, "total_s": y.size / fs, "events": 0}
    blocks = y[:n].reshape(-1, w)
    rms = np.sqrt((blocks ** 2).mean(axis=1))
    floor = float(np.median(rms)) or 1e-9
    peak = float(rms.max())
    if peak_db is not None:
        # Relative to the LOUDEST window, not the floor. Guarantees the biggest
        # events survive whatever the bench happens to be doing -- the floor-
        # relative gate cannot promise that, because it does not know in advance
        # how loud the loudest thing will be.
        thresh = peak * 10 ** (-peak_db / 20.0)
    else:
        thresh = floor * 10 ** (gate_db / 20.0)
    hot = rms > thresh
    pad = max(1, int(round(pad_s / win_s)))
    if hot.any():                                  # widen each event by pad windows
        idx = np.flatnonzero(hot)
        keep = np.zeros_like(hot)
        for i in idx:
            keep[max(0, i - pad):min(hot.size, i + pad + 1)] = True
    else:
        keep = hot
    events = int(np.count_nonzero(np.diff(np.concatenate(([0], keep.view(np.int8)))) > 0))
    out = blocks[keep].reshape(-1) if keep.any() else np.zeros(0)
    return out, {"floor": floor, "thresh": thresh, "peak": peak,
                 "peak_db": 20 * np.log10(peak / floor) if peak > 0 else 0,
                 "kept_s": out.size / fs, "total_s": y.size / fs, "events": events}


def emit(x, peak_state, dbfs):
    """Scale to dbfs against a decaying peak, then write slot 0 of a 4-slot frame."""
    if x.size:
        peak_state[0] = max(peak_state[0] * 0.995, float(np.abs(x).max()), 1e-6)
    g = (10 ** (dbfs / 20.0)) / peak_state[0]
    s = np.clip(x * g, -0.999, 0.999)
    frame = np.zeros((s.size, SLOTS), dtype="<i4")
    frame[:, 0] = (s * (2 ** 31 - 1)).astype("<i4")
    sys.stdout.buffer.write(frame.tobytes())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=("live", "pitch"), default="live")
    p.add_argument("--bus", type=int, default=2)
    p.add_argument("--rate", type=int, default=1000, help="sensor ODR in Hz")
    p.add_argument("--fs-g", type=int, default=2, choices=(2, 4, 8, 16))
    p.add_argument("--axis", default="mag", help="x, y, z, or mag (vector magnitude of the AC part)")
    p.add_argument("--hpf", type=float, default=2.0, help="Hz; strips gravity. Must stay below the band of interest.")
    p.add_argument("--dbfs", type=float, default=-6.0)
    p.add_argument("--seconds", type=float, default=30.0, help="live: how long to run")
    p.add_argument("--capture", type=float, default=20.0, help="pitch: seconds of vibration to record")
    p.add_argument("--play", type=float, default=8.0, help="pitch: seconds of audio to emit, looping")
    p.add_argument("--carrier", type=float, default=1000.0, help="live: carrier in Hz")
    p.add_argument("--gate-db", type=float, default=None,
                   help="pitch: keep only what rises this many dB above the measured noise floor. "
                        "The floor is the MEDIAN short-window RMS, which is robust to the events "
                        "themselves -- a mean would be dragged up by them and raise the bar.")
    p.add_argument("--gate-peak-db", type=float, default=None,
                   help="pitch: keep every window within this many dB of the LOUDEST one. Unlike "
                        "--gate-db this always yields something, because the bar is set by what "
                        "actually happened rather than by a figure chosen in advance.")
    p.add_argument("--loop-gap", type=float, default=0.0,
                   help="pitch: seconds of silence between loop repeats. A gated event is SHORT -- "
                        "0.33 s of vibration is 7 ms at x48 -- and looping it back to back turns "
                        "the loop period itself into an audible pitch (7 ms = 145 Hz), which is an "
                        "artefact of the looping, not the vibration. A gap separates the repeats "
                        "so you hear discrete events instead of a buzz.")
    p.add_argument("--gate-window", type=float, default=0.025, help="pitch: gate window in seconds")
    p.add_argument("--gate-pad", type=float, default=0.100,
                   help="pitch: seconds kept either side of each event, so attacks are not clipped")
    args = p.parse_args()

    with SMBus(args.bus) as bus:
        fs, lsb = setup(bus, args.rate, args.fs_g)
        a = float(np.exp(-2 * np.pi * args.hpf / fs))       # one-pole high-pass coefficient
        print(f"# MPU-9250 @ 0x68 bus {args.bus}, fs={fs:.1f} Hz, +/-{args.fs_g} g, "
              f"HPF {args.hpf} Hz, mode={args.mode}", file=sys.stderr)

        def pick(d):
            if args.axis == "mag":
                return np.linalg.norm(d, axis=1)
            return d[:, "xyz".index(args.axis)]

        if args.mode == "pitch":
            speedup = OUT_RATE / fs
            print(f"# capturing {args.capture:.0f} s, then emitting at {OUT_RATE} Hz "
                  f"-> x{speedup:.0f} speed-up: 8.3 Hz lands at {8.3*speedup:.0f} Hz",
                  file=sys.stderr)
            t0, chunks, last, seen = time.time(), [], 0.0, []
            print("# capturing NOW -- tap the bench. Live level follows:", file=sys.stderr)
            while True:
                el = time.time() - t0
                if el >= args.capture:
                    break
                d = drain(bus, lsb)
                if d.size:
                    chunks.append(d)
                    seen.append(float(np.linalg.norm(d - d.mean(axis=0), axis=1).max()))
                if el - last >= 0.5:                  # a level meter you can tap against
                    last = el
                    now = max(seen[-5:]) if seen else 0.0
                    bars = min(40, int(now * 1000 / 2))
                    print(f"\r#  {el:5.1f}s  peak {now*1000:7.2f} mg  "
                          f"{'#' * bars:<40}", end="", file=sys.stderr, flush=True)
                time.sleep(0.01)
            print(file=sys.stderr)
            d = np.vstack(chunks) if chunks else np.zeros((0, 3))
            if d.shape[0] < fs:
                sys.exit("REFUSING: captured less than a second of samples.")
            x = pick(d)
            y = np.zeros_like(x); prev_x = x[0]; prev_y = 0.0
            for i, xi in enumerate(x):                       # one-pole HPF
                prev_y = a * (prev_y + xi - prev_x); prev_x = xi; y[i] = prev_y
            if args.gate_db is not None or args.gate_peak_db is not None:
                y, kept = gate(y, fs, args.gate_db or 0, args.gate_window, args.gate_pad,
                               args.gate_peak_db)
                if y.size == 0:
                    sys.exit(f"NOTHING ABOVE THE GATE. Floor {kept['floor']*1000:.2f} mg, "
                             f"threshold {kept['thresh']*1000:.2f} mg (+{args.gate_db:.0f} dB), "
                             f"loudest window {kept['peak']*1000:.2f} mg "
                             f"(+{kept['peak_db']:.1f} dB). Nothing was played -- that is a "
                             f"result, not a failure. Tap the bench during the capture, run the "
                             f"machine, or lower --gate-db.")
                label = (f"within {args.gate_peak_db:.0f} dB of peak"
                         if args.gate_peak_db is not None else f"+{args.gate_db:.0f} dB over floor")
                print(f"# gate {label}: floor {kept['floor']*1000:.2f} mg, "
                      f"threshold {kept['thresh']*1000:.2f} mg, loudest {kept['peak']*1000:.2f} mg "
                      f"(+{kept['peak_db']:.1f} dB) -> kept {kept['kept_s']:.2f} s of "
                      f"{kept['total_s']:.1f} s ({100*kept['kept_s']/kept['total_s']:.1f}%) "
                      f"in {kept['events']} event(s)", file=sys.stderr)
            rms = float(np.sqrt((y ** 2).mean()))
            print(f"# {d.shape[0]} samples = {d.shape[0]/fs:.1f} s, AC rms {rms*1000:.2f} mg, "
                  f"peak {np.abs(y).max()*1000:.2f} mg -> {args.play:.0f} s of audio, looped",
                  file=sys.stderr)
            if rms < 1e-5:
                print("# WARNING: the bench is essentially still. Expect near-silence "
                      "-- tap it, or run a machine.", file=sys.stderr)
            peak = [max(float(np.abs(y).max()), 1e-6)]
            gap = np.zeros(int(args.loop_gap * OUT_RATE))
            if args.loop_gap and y.size:
                print(f"# each repeat is {y.size/OUT_RATE*1000:.1f} ms of audio; "
                      f"{args.loop_gap*1000:.0f} ms of silence between repeats, so the loop "
                      f"period is not heard as a pitch", file=sys.stderr)
            need = int(args.play * OUT_RATE)
            while need > 0:
                take = y[:need]
                emit(take, peak, args.dbfs)
                need -= take.size
                if need > 0 and gap.size:
                    g = gap[:need]
                    emit(g, peak, args.dbfs)
                    need -= g.size
        else:
            print(f"# live: DSB about {args.carrier:.0f} Hz. Tap the bench.", file=sys.stderr)
            phase, prev_x, prev_y, carry = 0.0, None, 0.0, None
            peak, t0 = [1e-6], time.time()
            step = 2 * np.pi * args.carrier / OUT_RATE
            up = OUT_RATE / fs
            while time.time() - t0 < args.seconds:
                d = drain(bus, lsb)
                if not d.size:
                    time.sleep(0.005); continue
                x = pick(d)
                if prev_x is None:
                    prev_x = x[0]
                y = np.empty_like(x)
                for i, xi in enumerate(x):                   # one-pole HPF
                    prev_y = a * (prev_y + xi - prev_x); prev_x = xi; y[i] = prev_y
                n_out = int(round(y.size * up))
                if n_out < 2:
                    continue
                src = np.concatenate(([carry if carry is not None else y[0]], y))
                yi = np.interp(np.linspace(0, src.size - 1, n_out), np.arange(src.size), src)
                carry = y[-1]
                ph = phase + step * np.arange(n_out)
                phase = float((ph[-1] + step) % (2 * np.pi))
                emit(yi * np.sin(ph), peak, args.dbfs)
                sys.stdout.buffer.flush()
        bus.write_byte_data(A, FIFO_EN, 0x00)


if __name__ == "__main__":
    main()
