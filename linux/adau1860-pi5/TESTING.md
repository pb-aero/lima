# Proving samples reach the ADAU1860

**Date:** 2026-09-02 · **Agent:** LIMA

The narrow question: *do the bytes physically arrive at the chip?* Not whether they arrive
unfiltered, not whether the DSP does the right thing — just arrival. That is a much easier test, and
there is a clean way to do it with **no DSP program at all**.

## The one thing that made this easy, and the one that didn't

`[fetched]` UG-2257 Table 190: **`DAC_ROUTE0` (`0x4000C053`) can source a serial port input channel
directly** — its settings list starts *"00 Serial Port 0 Channel 0"* — and **that is already its
reset value**. So the DAC is factory-wired to serial port 0 slot 0. Power it on, send audio, listen.
No FastDSP program, no interpolator, no ASRC in the way.

`[measured]` The reverse is **not** available. I read every source in `SPT0_ROUTE0`'s 6-bit field:
FastDSP 0-15, Tensilica DSP 16-31, Output ASRC 32-35, ADC 36-38, DMIC 39-42 and 55-58, decimator
43-50, EQ0 51, "no output" 63. **There is no serial port input among them.** A pure digital loopback
— data in on SDATAI, straight back out on SDATAO — is therefore impossible without passing through
a DSP core, an ASRC, or the EQ. (`EQ_ROUTE` *can* source a serial port channel and EQ0 *is* a valid
`SPT0_ROUTE` source, so **serial-in → EQ → serial-out is a genuine digital loopback path** if you
ever need one. It needs EQ coefficients loaded, so it is not the zero-effort option.)

Hence: **use the DAC.** It is the shortest path from "arrived" to "observable".

## Test 1 — analog, 60 seconds, needs a scope or headphones

```bash
sudo python3 adau1860_init.py --bus 1 --addr 0x64 --probe      # chip alive, framing right
sudo python3 adau1860_init.py --bus 1 --addr 0x64 --dac-test --apply
```

Then push a 1 kHz tone in. `$CARD` below is the ALSA card id, which is **not** necessarily the `simple-audio-card,name` from the overlay — ALSA derives an id and may strip punctuation. Get the real one from `aplay -l` and set `CARD=$(...)` once:

```bash
aplay -l          # find the adau1860 card, note its [id]
export CARD=<that id>
```

```bash
python3 send_test_pattern.py --seconds 10 \
  | aplay -D hw:$CARD,0 -f S32_LE -c 4 -r 48000 -t raw
```

**A 1 kHz tone at the analog output means the samples arrived.** That is the whole test. If you get
silence, the fault is upstream of the DAC and the order in §3 tells you where.

The pattern sits at **−12 dBFS deliberately**. Full scale means any gain above unity inside the chip
saturates, and saturation looks like a plausible flattened peak rather than an obvious fault.

## Test 2 — digital, if you can capture

If you later add a capture path, `send_test_pattern.py --check` reads frames on stdin and verifies
them. Slot 3 carries `0xA5 << 24 | (seq & 0xFFFFFF)`, so it reports **which slot the magic actually
landed in** (any answer but 3 means the link slipped and your axes are permuted) and **how many
frames were lost**.

`[measured]` Verified with one positive and two negative controls:

| Control | Result |
|---|---|
| clean round trip | `magic found in slot 3 (480/480)`, 0 lost, **PASS** |
| stream offset by one slot | `magic found in slot 2`, **`*** SLIPPED by 1 slots ***`** |
| 50 frames deleted mid-stream | `frames checked: 430, frames lost: 50` |

Note this needs simultaneous TX and RX, which the single-direction dummy codecs cannot express — see
[NOTES.md](NOTES.md) §5. Test 1 needs no such thing.

## 3. If the tone does not appear, check in this order

1. **`--probe` first.** If `VENDOR_ID/DEVICE_ID1/DEVICE_ID2` don't read `0x41/0x60/0x18`, nothing
   else is meaningful — and suspect the 32-bit subaddress framing before the chip
   ([REGISTER_CONFIG.md](REGISTER_CONFIG.md) §1).
2. **Scope BCLK and FSYNC.** The codec is master; if it isn't clocking, the Pi cannot tell you. In
   consumer mode the driver never checks the rate against the wire
   ([DATA_OVER_I2S.md](DATA_OVER_I2S.md) §7). No clocks means no transfer, and it looks identical
   to a driver fault.
3. **`CLK_CTRL1` bit 3 `XTAL_MODE`.** Its reset value says *crystal*. If your board drives MCLKIN
   from an oscillator can, clear it (`0xC0`) — and `PLL_PGA_PWR` bit 1 `XTAL_EN` likewise. This is
   the most likely cause of "no clocks at all" and it is board-dependent, so I have not guessed it
   for you.
4. **`aplay` errors.** `-EINVAL` on open almost always means an illegal channel count: 2, 4, 6, 8
   only ([DATA_OVER_I2S.md](DATA_OVER_I2S.md) §7).
5. **Never `plughw:`.** It will resample and convert silently.

## 4. What this test does and does not prove

**Does:** bytes left the Pi, crossed the wire, were accepted by the serial port, and were moved
internally to another block. That is "the samples reach the ADAU1860", answered.

**Does not:** that they arrive *unaltered*. The DAC path is a converter with an optional 1/4/8 Hz
high-pass on it, so this proves presence, not fidelity. And it says nothing about the interpolator
question on the path into FastDSP ([REGISTER_CONFIG.md](REGISTER_CONFIG.md) §4), which is still the
open item for real processing.
