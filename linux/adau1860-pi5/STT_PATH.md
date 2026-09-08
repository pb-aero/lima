# Speech-to-text through the ADAU1860 — what the capture path needs

**Date:** 2026-09-08 · **Agent:** LIMA · Peter: *"speech to text ... as close to real-time as
possible"*, and *"this is all using the pi and adau1860"* — so the mic goes into the **codec**, not
a USB device. That constraint is what this document is scoped to.

## Piper cannot do this — it is a one-way engine

`[fetched]` Piper is **text -> audio only**. There is no transcription mode, no `--stt` flag, no
encoder to run backwards. The name covers one direction. Speech-to-text is a **separate program
with a separate model**, and the pairing in Home Assistant's own stack (Piper for TTS, Whisper for
STT) is two independent services, not one.

So `piper_say.sh` is not the starting point for any of this. Nothing below reuses it except the
ALSA device and the slot discipline.

## The route the microphone takes is REGISTER-DIRECT — this is the good news

`[measured]` from ADI's own bitfield enum (`adi_lark.h`, `adi_lark_sap_out_route_from_e`, the Lark
SDK payload extracted 2026-09-07), the valid **SPT0 output sources** include the microphone front
ends directly:

| Source | `SPT0_ROUTEn` value |
|---|---|
| `ADC0` / `ADC1` / `ADC2` (analog mic in) | **36 / 37 / 38** |
| `DMIC0-3` (PDM digital mic) | **39-42** |
| `DMIC4-7` | 55-58 |
| `ASRCO0-3` | 32-35 |
| `FDEC0-7` | 43-50 |
| `EQ` | 51 |

**Cross-check, and it is the reason to trust the first two rows:** the last three rows reproduce
`duplex/README.md`'s independently-derived table exactly (ASRCO 32-35, FDEC 43-50, EQ 51). Three
agreements on values that document never guessed at makes the ADC/DMIC values credible.

`ADC0_EN`/`ADC1_EN`/`ADC2_EN` are bits 0/1/2 of `0x4000C004` — **the same register as `PB0_EN`**
(bit 4) that the DAC bring-up already writes. `[measured]`

### Why this matters more than it looks

`duplex/README.md` §3 concluded that **only EQ0** can route serial-in back to serial-out, and the
2026-09-04 loopback died there. It is easy to read that as "capture through this codec is hard".

**It does not apply to a microphone.** That failure was a *loopback* topology — serial IN back to
serial OUT — which is an unusual thing to ask a codec for. A mic is `ADC -> SPT0`, the part's
**primary designed use case**, and it has a direct route value. The blocker that stopped the
loopback is not in the mic path at all.

### The one trap on these values

`91b0e9e` recorded that `DAC_ROUTE0` encodes **differently** between the ADAU1860 and the
ADAU1860-1, and that the ID registers do not distinguish them `[gap]`. The same split exists here:
the header's `#ifdef LARK_SDK` block gives `ADC0 = 36`, while the `#ifdef LARK_LITE_SDK` block
starts the enum at **`ADC0 = 0`**. The three-way cross-check above says the EVB on this bench
follows the **LARK (not Lite)** numbering — but that is inference from three matching values, not a
read-back, so **sweep the route value if the first setting is silent** rather than concluding the
mic is dead.

## What is genuinely in the way — all Pi-side, all already known

1. **RP1 will not lock to the narrow TDM frame sync** (`SAI_MODE=STEREO` only). Capture is
   therefore **2 channels**, exactly as playback is. One mic is plenty; four is not available.
2. **`i2s0` and `i2s1` claim the same four pins** (`rp1_i2s0_18_21` / `rp1_i2s1_18_21`), and
   `i2s2` has no DMA and no pinctrl. So TX and RX **cannot be two blocks** — full duplex has to be
   one block doing both.
3. **That needs `duplex/dummy_duplex.c`** — the ~90-line ASoC codec written here, because
   `simple-card.c:407` fetches the codec node with `of_get_child_by_name(node, "codec")`,
   *singular*, so a two-codec link matches nothing. It worked on **6.12.47**.
4. **Duplex has NOT been re-verified on 6.18.39.** `[gap]` This is the open item from
   `RESULTS-2026-09-07.md`, still open. Everything above assumes it survives the kernel change,
   and that assumption is untested.

If capture-only is acceptable (transcribe *or* speak, not both at once), the `-rx` overlay avoids
the duplex problem entirely and is the cheaper first test.

## Engine choice — the distinction that decides the latency

`[fetched]` The engines split into two architectures, and the split is what matters for
"as close to real-time as possible":

- **Truly streaming** (transducer/CTC models — emit words *as you speak*): **sherpa-onnx**
  streaming Zipformer (~80 MB, explicitly targets Raspberry Pi and ARM, reported ~160 ms latency
  class on mobile silicon) and **Vosk** (Kaldi, 50 MB up, runs in ~500 MB RAM). Latency is a frame
  or two.
- **Not streaming** — **Whisper** in any wrapper (`whisper.cpp`, `faster-whisper`). Whisper is a
  30-second-window encoder-decoder; every "real-time Whisper" is a chunking harness around a batch
  model, so **0.5-2 s behind live speech is structural**, not a tuning failure. `tiny`/`base` run
  faster than real time on a Pi 5; accuracy on accents and noise is better than Vosk.

**Recommendation:** sherpa-onnx streaming Zipformer for the live path — it is the only option whose
architecture matches the requirement. Keep `whisper.cpp base.en` as a second pass if a transcript
needs to be *correct* rather than *immediate*; they can run off the same captured stream.

## Mic hardware — what the part will accept

`[fetched]` The ADAU1860 is **3 analog in / 1 out, 8 PDM mic in**. Two shapes work:

- **Analog** — electret or analog MEMS into `ADC0-2`, the EVB's `P9`/`P10`/`P11` inputs, through
  the part's own PGA. Uses the most of the codec.
- **PDM digital MEMS** — straight into `DMIC0-7`, no analog front end, no bias network, and the
  cleanest signal path. Two of these give a stereo pair for beamforming later.

`[gap]` **Which EVB headers break out the PDM pins, and what bias/jumper the analog inputs need, is
not established here** — it needs the EVAL-ADAU1860EBZ user guide, which is the next thing to read
before ordering anything.

## Order of work, cheapest risk first

1. Read the EVB user guide for the mic headers; settle the part choice. **Before ordering.**
2. Re-verify the **`-rx` overlay on 6.18.39** with no mic at all — `arecord` should produce silence
   at exactly real time. That separates the kernel question from the analog question.
3. Bring up `ADC0` (or `DMIC0`) -> `SPT0_ROUTE0 = 36`, capture, confirm the noise floor moves when
   the mic is tapped. **Tapping is the positive control** — a dead route and a quiet room look
   identical, which is the 2026-09-07 muted-DAC scar wearing a microphone.
4. Only then attach an STT engine. Debugging a transcriber on top of an unproven capture path is
   how a silent mic becomes a "model accuracy problem".
