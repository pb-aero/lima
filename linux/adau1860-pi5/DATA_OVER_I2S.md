# Pushing accelerometer data over I2S — what bites

**Date:** 2026-09-02 · **Agent:** LIMA · companion to [NOTES.md](NOTES.md)

The goal is not audio. I2S/TDM is being used as a **dumb, fixed-rate, unframed sample pipe** for
accelerometer data. That is a legitimate and fairly common use of the interface, and it removes most
of the work in [NOTES.md](NOTES.md) — no codec driver, no mixer, no mics. What it does *not* remove
is a set of traps that all fail the same way: **the link keeps running and your numbers are quietly
wrong.** Every one of these is worth ruling out before you trust a byte.

Provenance: `[measured]` = read from the source myself · `[fetched]` = ADAU1860 datasheet Rev. 0
(30 pp) · `[derived]` = reasoning shown · **`[gap]`** = not established.

---

## 0. The good news

`[fetched]` The ADAU1860 serial ports run **8 kHz to 768 kHz**, in I2S / left-justified /
right-justified / **up to TDM16** (TDM12 in Turbo), and there are **two** 16-channel ports. It can
be clock master — the datasheet's digital timing table specifies `tTS`, *"BCLK_x falling to FSYNC_x
timing skew (**master mode**)"*, so master is a supported configuration and not something you have
to fight.

That range is unusually helpful here: you can very likely set fS **equal to your accelerometer ODR**
and make one I2S frame mean exactly one sample set. Do that if you can — it makes every trap below
easier.

## 1. ALSA will silently rewrite your data unless you stop it

This is the one that wastes days. ALSA is a *media* stack; it assumes it may resample, dither, mix
and scale, and it will.

- Open **`hw:<card>,0` only. Never `plughw:`.** `plughw` exists precisely to convert, and it will
  happily resample your accelerometer stream to 48 kHz and interpolate between samples.
- Set format, rate and channel count **explicitly** and check the values ALSA hands back after
  `snd_pcm_hw_params()` — it returns what it *chose*, which is not always what you asked for.
- Make sure **PipeWire / PulseAudio are not grabbing the card.** A session daemon opening the device
  will insert its own resampler and volume stage.
- No softvol, no dmix, no `.asoundrc` plugin chain in the path.

If any single sample comes back scaled by 0.9998 or interpolated, one of these is why.

## 2. There is no framing on the wire — add your own

I2S/TDM has frame *sync*, but no packet boundary, no sequence number and no CRC. If the link slips
by one slot — an XRUN, a late start, a glitch on FSYNC — **every axis shifts one position and
nothing reports an error.** X becomes Y forever, and the data looks plausible.

Fix it in the payload. The cheapest scheme that works:

| Slot | Contents |
|---|---|
| 0 | accel X |
| 1 | accel Y |
| 2 | accel Z |
| 3 | **sequence counter + magic** — e.g. `0xA5 << 24 \| (seq & 0xFFFFFF)` |

`dtoverlay=adau1860-pi5-tx,slots=4,width=32`. Four 32-bit slots at fS = 32 kHz is a 4.096 MHz BCLK —
undemanding. Now the receiver validates the magic byte every frame and the counter tells you exactly
how many frames you lost, instead of you finding out weeks later.

**`[gap]` I have not established RP1's maximum BCLK.** TDM16 × 32 bit × 48 kHz would be 24.576 MHz,
which is plausible but unverified — measure before designing around a wide TDM frame.

## 3. Assume 24 bits of payload per slot, not 32

`[fetched]` The ADAU1860's converters are **24-bit**, and the datasheet's specification conditions
are stated at *"word width = 24 bits"*. `[derived]` **If your data traverses any internal block, the
bottom 8 bits of a 32-bit slot are not guaranteed to survive.** Keep each payload word ≤ 24 bits,
left-justified in a 32-bit slot, and you sidestep the question entirely.

That is not a hardship: raw accelerometer output is 16 or 20 bits. It only bites if you try to be
clever and pack a 32-bit float or a full 32-bit timestamp into one slot.

`[gap]` The serial port's word-width register options are **not in the 30-page datasheet** — that
document is abridged and carries no register map. You need ADI's hardware reference manual, or the
register dump LARK Studio produces, to pin this down.

## 4. The ADAU1860's internal path must be bit-transparent

The chip is a signal processor. Everything it is designed to do is destructive to a data payload.
For the signal flow you load, confirm all of the following are **out of the path**:

- **The 4-channel ASRCs** `[fetched]` — an asynchronous sample rate converter interpolates. On audio
  that is inaudible; on accelerometer data it is fabricated samples. This is the single worst one.
- **The high-pass filter.** `[fetched]` the ADCs and DAC have an *optional* HPF at 1 Hz, 4 Hz or
  8 Hz. Optional means you can turn it off — and you must, if you ever care about DC. An
  accelerometer's DC term is gravity; a 1 Hz HPF deletes static tilt and leaves vibration looking
  fine, so this failure is invisible unless you specifically test for it. **Tilt the board and check
  the DC value moves.**
- Volume / soft-volume, PGA gain, ANC, companding, dither, any FastDSP block with a filter in it.

If the data is only passing *through* — serial port in to serial port out, or into the DSP as
opaque words — route it with zero processing blocks in LARK Studio.

## 5. XRUN means resynchronise, not "carry on"

If the Pi's ALSA buffer underruns (TX) or overruns (RX), the DesignWare block does not stop — it
repeats or zeroes and keeps clocking. Combined with §2, the stream comes back misaligned.

Treat `-EPIPE` as a **framing loss**, not a hiccup: `snd_pcm_prepare()`, then re-acquire lock on
your magic word before trusting data again. Size periods generously and pin the reader thread.

## 6. Sanity checks, in order

1. `i2cdetect -y 1` → device at `0x64`–`0x67` (see [NOTES.md](NOTES.md) §3).
2. Configure the ADAU1860 as clock master; **scope BCLK and FSYNC** and confirm the frame rate is
   what you think it is. A Pi in consumer mode with no incoming clock is indistinguishable from a
   broken driver.
3. Load the overlay, `aplay -l` / `arecord -l`, confirm the card appears.
4. **Loopback a known pattern before you connect the accelerometer.** Send a ramp, or the sequence
   counter alone, and read it back. If a ramp does not come out as a ramp, nothing downstream is
   worth debugging.
5. Only then put real accelerometer samples in, and check DC by tilting (§4).

## 7. Worth asking out loud

If the accelerometer is read by the Pi over SPI anyway, I2S is a longer road than a ring buffer in
memory — so presumably the point is that the samples have to **reach the ADAU1860** (its DSP, or an
A2B backbone beyond it), rather than reach the Pi. `kicad/aeronode/doc/ARCHITECTURE.md` commits
AeroNode to an A2B main node on SAI3, which would make this bench rig a prototype of that path.
If that is right, this file should be read alongside the aeronode architecture doc and the framing
scheme in §2 wants to survive the A2B hop too. **Not yet confirmed with Peter.**

## Which overlay

| File | Direction | Dummy codec | Use when |
|---|---|---|---|
| `adau1860-pi5-tx-overlay.dts` | Pi **transmits** (GPIO21 SDOUT) | `linux,spdif-dit` | Pi reads the accelerometer and pushes samples to the ADAU1860 |
| `adau1860-pi5-rx-overlay.dts` | Pi **receives** (GPIO20 SDIN) | `linux,spdif-dir` | Accelerometer is analog into an ADAU1860 ADC, or digital into its DSP, and the Pi reads it back |

`[measured]` Both compile: `dtc 1.8.1 -@`, exit 0, 1673 bytes each, `__overrides__` for `slots` and
`width` present in the blob. **Neither has been run on hardware** — I have no route to the Pi.

Both are codec-master and both target `i2s_clk_consumer`. You cannot have both directions at once
from these files: each dummy codec declares only one direction, and a single `simple-audio-card`
link has a single cpu DAI. Simultaneous TX and RX needs a real ADAU1860 codec driver declaring one
DAI with both `.playback` and `.capture` — a few hundred lines, and worth doing if the answer to §7
is that this is the AeroNode path.
