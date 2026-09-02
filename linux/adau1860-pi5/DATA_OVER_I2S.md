# Pushing accelerometer data over I2S — what bites

**Date:** 2026-09-02 · **Agent:** LIMA · companion to [NOTES.md](NOTES.md)

**Direction confirmed 2026-09-02: Pi -> ADAU1860, samples going into the DSP for processing.**
Use `adau1860-pi5-tx-overlay.dts`. Read §7 first — it carries hard limits that constrain the
design, and §8, which is about what your integers *mean* once they are inside an audio DSP.

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

## 7. Hard limits the Linux side imposes — measured, not guessed

These come from reading `sound/soc/dwc/dwc-i2s.c` and `include/sound/designware_i2s.h` at
`rpi-6.12.y`. They are not negotiable from device tree and they will bite at `hw_params` time.

**Channel count must be 2, 4, 6 or 8. Nothing else.** `[measured]`

```c
switch (config->chan_nr) {
case EIGHT_CHANNEL_SUPPORT:  /* 8 */
case SIX_CHANNEL_SUPPORT:    /* 6 */
case FOUR_CHANNEL_SUPPORT:   /* 4 */
case TWO_CHANNEL_SUPPORT:    /* 2 */
        break;
default:
        dev_err(dev->dev, "channel count %d not supported\n", config->chan_nr);
        return -EINVAL;
}
```

**So you cannot ask for 3 channels.** X/Y/Z alone is rejected outright. This is not a limitation to
work around — it is the argument for the TDM4 layout in §2 arriving for free: three axes plus a
sequence/magic word is exactly 4. Take the fourth slot and use it.

Note also the ceiling is **8, not 16**. The ADAU1860 supports TDM16 `[fetched]`, but the RP1 driver
will not go past 8 slots. Plan the frame around 8 channels maximum.

**Setting any TDM slot count forces 32-bit slots.** `[measured]`

```c
if (dev->tdm_slots)
        config->data_width = 32;
```

Whatever `params_format()` said is overridden. Since our overlay sets `dai-tdm-slot-num`, slots are
32 bits wide, full stop — so use **`SNDRV_PCM_FORMAT_S32_LE`** and stop thinking about it. (For the
record the driver accepts only S16_LE, S24_LE and S32_LE; `S20_3LE` is rejected even though the
dummy codec advertises it.)

**In consumer mode the driver never touches the clock — so ALSA's rate is a *declaration*, not a
check.** `[measured]` The entire rate-setting block, `clk_set_rate()` and the CCR frame-length write
included, sits inside `if (dev->capability & DW_I2S_MASTER)`. On `rp1_i2s1` that is false and the
whole block is skipped.

The good part: the 32/48/64-only `frame_length` restriction does not apply to us. The bad part, and
it is the fifth silent failure mode: **if you tell ALSA 32000 and the ADAU1860 is actually clocking
48000, nothing errors.** You get a rate mismatch that surfaces later as inexplicable XRUNs. The
codec's actual fS is the truth; ALSA is only being told a story. **Scope the frame rate.**

## 8. Your integers become fractions inside the DSP

`[derived]` — standard fixed-point DSP reasoning, not stated in the ADAU1860 datasheet, but it
governs every number you get back.

An audio DSP treats a sample as a **fraction in [-1, +1)**, not an integer. A 24-bit word `v` is
the value `v / 2^23`. Your accelerometer counts will be interpreted that way whether you intend it
or not. Two consequences:

**Linear processing does not care.** Biquads, FIR, gains, mixing — all scale-invariant. A filter
designed for audio does exactly the right thing to accelerometer data. You rescale on the way out
and the maths is untouched. This is why the whole idea works.

**Non-linear blocks absolutely do care.** Limiters, compressors, noise gates, soft-clip and the ANC
blocks all have *absolute* thresholds expressed in dBFS. Feed them accelerometer counts and the
thresholds mean something arbitrary. Either keep them out of the path or set them knowing your
scaling.

**Leave headroom.** If you left-justify a full-scale 16-bit reading into the top of a 24-bit word
you are sitting at ±1.0 and any gain above unity clips. Shift left by 6 rather than 8 and you keep
~12 dB of headroom for the DSP to work in. Clipping in a fixed-point audio DSP is saturation, not
wraparound — so it looks like a plausible flattened peak rather than an obvious fault.

## 9. Match the serial port rate to the DSP rate

`[fetched]` The datasheet's own worked example runs **FastDSP at 192 kHz and the Tensilica core at
48 kHz** simultaneously, and Table 6's documented path from the serial input reads
*"SDATAI_x to Interpolator to FastDSP"*. There are 8 interpolators and 8 decimators "with flexible
routing", plus 4 ASRC channels.

`[derived]` Every one of those rate-crossing blocks is a filter. **If the serial port fS differs
from the rate of the DSP core doing your processing, something in that list gets inserted to bridge
the gap, and it will filter your data.** So:

> Set the serial port fS equal to the rate of the DSP core you are processing on, route
> serial-in straight to that core, and confirm no interpolator, decimator or ASRC appears in the
> LARK Studio signal flow.

If your accelerometer ODR can also equal that rate, one I2S frame is one sample set and the whole
chain is rate-coherent end to end. That is the configuration to aim for.

> **CORRECTION, 2026-09-02, from UG-2257.** Earlier I said to set fS equal to your ODR. That is only
> available if the ODR is on a fixed menu. `[fetched]` the ADAU1860 generates LRCLK at **8, 12, 16,
> 24, 48, 96, 192, 384 or 768 kHz only** (Table 278) and BCLK at **3.072, 6.144, 12.288 or
> 24.576 MHz only** (Table 277). With Linux's 2/4/6/8 slot restriction on top, only thirteen
> (fS, slots) pairs exist at 32-bit slots — table in [REGISTER_CONFIG.md](REGISTER_CONFIG.md) §2.
> **Pick the ODR from that list**, or accept that fS and ODR differ and handle it in the framing.
> 44.1 kHz does not exist on this part at all.

## 10. Recommended starting configuration

| Setting | Value | Why |
|---|---|---|
| Overlay | `dtoverlay=adau1860-pi5-tx,slots=4,width=32` | TX; 4 slots is the smallest legal count ≥3 (§7) |
| ALSA device | `hw:$CARD,0` (id from `aplay -l`) — **never `plughw:`** | §1 |
| Format | `S32_LE` | TDM forces 32-bit slots (§7) |
| Channels | 4 | 3 is `-EINVAL` (§7) |
| Rate | = ADAU1860 fS = DSP core rate = accelerometer ODR if possible | §9 |
| Slot 0/1/2 | X / Y / Z, left-justified, ~12 dB headroom | §8 |
| Slot 3 | `0xA5 << 24 \| (seq & 0xFFFFFF)` | slip detection (§2) |
| Payload width | ≤ 24 bits per slot | 24-bit internal path (§3) |

**Register values: see [REGISTER_CONFIG.md](REGISTER_CONFIG.md)** and the runnable
[`adau1860_init.py`](adau1860_init.py). Sourced from UG-2257 (337 pp), **not** captured from working
silicon and not yet run on hardware. The DSP program itself stays `[gap]` and always will from here —
it comes out of LARK Studio, not out of a register manual.

## 11. Worth asking out loud

Confirmed: the samples have to **reach the ADAU1860's DSP**, which is why I2S rather than a ring
buffer in memory. Still open: `kicad/aeronode/doc/ARCHITECTURE.md` commits AeroNode to an A2B main
node on SAI3, and if this bench rig is a prototype of that path then the framing scheme in §2 wants
to survive the A2B hop too, and these notes belong against the aeronode design. **Not confirmed.**

Also open: **do processed results need to come back to the Pi?** If they do, that is simultaneous
TX and RX on one DAI, which the dummy codecs cannot express — it is the trigger for writing a real
ADAU1860 codec driver. If the results leave over A2B or the PDM outputs instead, TX-only is enough
and no driver is needed.

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
