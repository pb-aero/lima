# RP1 I2S full-duplex loopback — what works and what is still blocked

**Date:** 2026-09-04 · **Agent:** LIMA · bench `scopenode`, Pi 5 Rev 1.1, kernel 6.12.47.
All `[measured]` on hardware.

## Result

**The RP1 can transmit and capture simultaneously on one I2S block.** `aplay` and `arecord` ran
concurrently on `hw:adauduplex,0` at 48 kHz / S32_LE / 2ch, both exited 0, and the capture was
exactly 1,536,000 bytes for 4 s (48000 x 2ch x 4B). No XRUN, no `-EINVAL`.

**Data did not return through the codec**, for a reason that is understood and is not a Pi-side
fault — see §3.

## 1. Why a custom codec was needed

The in-tree dummies are single-direction: `linux,spdif-dit` declares `.playback` only,
`linux,spdif-dir` declares `.capture` only. `[measured]` each brings up a card with exactly one
direction on `rp1_i2s1` — which incidentally proves **the CPU DAI supports both**.

Pairing them fails. `simple-card.c:407` fetches the codec node with
`of_get_child_by_name(node, "codec")` — **singular**. A multi-codec link written as `codec@0` /
`codec@1` matches nothing, and the link then probes with the CPU as clock provider, which
`rp1_i2s1` (consumer-only) rejects: `snd_soc_dai_set_fmt ... -22`.

`dummy_duplex.c` here is a ~90-line ASoC codec declaring **one DAI with both directions** and no
hardware behind it. Build on the Pi (`make`), `insmod dummy_duplex.ko`, then load
`adau1860-duplex-overlay.dts`. Card appears in both `aplay -l` and `arecord -l`.

## 2. Two hardware routes that do NOT exist

- **`rp1_i2s2` is unusable.** `[measured]` `rp1.dtsi` gives it no `dmas` property and no pinctrl
  group. No DMA means no streaming; no pin group means it reaches no pads.
- **`i2s0` and `i2s1` cannot run together.** The only pinctrl groups are `rp1_i2s0_18_21` and
  `rp1_i2s1_18_21` — both claim **the same four pins**. A two-block loopback (one TX, one RX) is
  therefore impossible on this SoC.

So full duplex has to be one block doing both, which is what the module above enables.

## 3. Why the loop is still open at the codec

`[measured]` the ADAU1860 was found at **factory reset** (`CHIP_PWR 0x00`, `STATUS2 0x00`, all
`SPT0_CTRL` zero) — its registers are volatile and a power cycle clears them, so any previously
loaded flow was gone.

Reconfigured from scratch and verified: **`PLL_LOCK=1`, `SPT0_LOCK=1`**, `SAI_CLK_PWR = 0x03`
(both directions), stereo framing at 48 kHz / 3.072 MHz BCLK.

**Only one block can route serial-in back to serial-out.** Checked every routing register:

| Block | Accepts serial-port input? | Valid `SPT0_ROUTE` source? |
|---|---|---|
| **EQ0** | **yes** | **yes (51)** |
| FINT (interpolator) | yes | no |
| DAC | yes | no (analog sink) |
| FDEC (decimator) | no — FastDSP only | yes (43-50) |
| Output ASRC | no — FastDSP only | yes (32-35) |

**EQ0 is the only register-only path**, and it was routed (`EQ_ROUTE = 0x00`,
`SPT0_ROUTE0/1 = 0x33`) and started (`EQ_CFG = 0x01`, `EQ_STATUS = 0x01`). Capture was still
**0 non-zero samples of 384,000**. A running EQ whose parameter RAM is empty outputs exactly zero —
which is what a clean run of zeros, rather than noise, indicates.

**The EQ coefficients are what LARK Studio loads.** Without them there is no pass-through.

## 4. To close the loop — two options, both needing one wire or one file

1. **Reload the LARK Studio loopback flow** onto the ADAU1860, then re-run the test. Nothing on the
   Pi side needs to change.
2. **Jumper GPIO21 (SDOUT) to GPIO20 (SDIN)** and re-run. That bypasses the codec entirely and
   proves the Pi's own TX-to-RX data path end to end — a cleaner isolation of the RP1 from the
   codec, and worth doing once regardless.

An analog loop (serial-in → DAC → cable → ADC → serial-out) also exists, since `DAC_ROUTE0` takes
serial input and the ADC is a valid `SPT0_ROUTE` source, but it needs a physical audio cable and
measures the converters rather than the digital path.
