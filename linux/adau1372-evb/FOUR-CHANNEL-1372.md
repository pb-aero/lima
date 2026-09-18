# Four capture channels off the ADAU1372 — the three things it needs

**Date:** 2026-09-18 · **Agent:** LIMA · for Monday 2026-09-21, John in the office with his RME.
**Scope:** only the 1372's channel count. Everything else — mic wiring, supply voltages, the test
order, the 1860 side — belongs to JULIETT's build spec
(`john/agents/2026-09-10_dvnc-rig-build-spec/`) and test sheet, and is not repeated here.

**Why this file exists:** John's option (c) ruling asks the 1372 for **four** channels (ADXL354 X/Y/Z
plus the IM68A130A mic). **This rig delivers two.** Not because of a codec limit — because of a
missing wire, a driver default, and an overlay. All three are identified, two of them are fixed in
this directory, and the third needs hands at the bench.

---

## The state of play, measured

| | |
|---|---|
| Codec | `0x3C`, 12.288 MHz crystal, control port good `[measured]` |
| Driver | mainline, built out-of-tree as `snd-soc-adau1372-oot.ko`, autoloads, card + 50 ALSA controls `[measured]` |
| Digital link | **bit-exact** through the codec at 64 fs `[measured]` |
| DAC | audible and clean `[measured, by ear]` |
| ADC | **works** — a finger on the AIN0 pin gave 41654 / 43410 nonzero samples on the two channels `[measured]` |
| Channels reaching the host | **2** (AIN0/AIN1 via `ADC_SDATA0`) |

So nothing is broken. The fourth channel is an integration job, not a debug job.

## Why two lanes and not TDM4

**The ADAU1372 has one serial port but two ADC data pins.** `ADC_SDATA0` carries AIN0/AIN1,
`ADC_SDATA1` carries AIN2/AIN3, and the split is `ADC_SDATA_CH` (`0x17`) — which **resets to `0x04`**:
`ADC_SDATA0_ST = 00` (start at channel 0), `ADC_SDATA1_ST = 01` (start at channel 2). `[fetched]`
datasheet p.53 Table 36. **That is exactly the split we want and it costs no register write.**

TDM4 was tried on this rig on 2026-09-17 and abandoned. It streamed without XRUN but **was never
slot-aligned**: a per-slot tone test gave a different map on each run, tones mixed across slot
boundaries, samples clipped to ±2³¹, and only 2 of 4 channels ever carried data. The cause is the
same one this lane keeps meeting — **RP1 wants a 64-BCLK frame and will not lock to a narrow frame
sync.**

Multi-lane sidesteps it entirely, and the Pi side is already proven: `[measured]`
`../adau1860-pi5/duplex/MULTILANE.md` streams 2, 4, 6 and 8 channels with exact byte counts, **with a
negative control showing unused lanes stay static**. Each lane carries its own 2×32-bit stereo pair,
so the frame stays 64 fs and the bit clock stays at the stereo rate — **1.536 MHz for 4 channels at
48 kHz**, not the 6.144 MHz a 4-slot TDM frame would need. Fewer edges, and no dependence on the
behaviour that does not work.

---

## 1 · THE WIRE — the one thing I cannot do from here

`ADC_SDATA1` must reach the host. **It is brought out on the board** — this corrects my own
2026-09-17 note, which said *"`ADC_SDATA1` is not wired"* with no qualifier and reads as a board
limitation. It is not: `[fetched]` UG-807 Figure 36 shows `ADC_SDATA1/CLKOUT/MP6` on **J4, the 12-way
serial audio header**, beside `LRCLK`, `BCLK`, `DAC_SDATA/MP0`, `ADC_SDATA0/MP1` and `EXT_MCLK`. It
also appears on **J9** (MPx pin jumpers). **Our harness simply has no wire on it.**

```
EVAL-ADAU1372Z  J4  ADC_SDATA1/CLKOUT/MP6   ──────►   host GPIO22
```

**GPIO22 is RP1 `i2s1` lane 1 SDI** `[repo]` `MULTILANE.md`:

| Lane | SDI | SDO |
|---|---|---|
| 0 | GPIO20 | GPIO21 |
| **1** | **GPIO22** | GPIO23 |
| 2 | GPIO24 | GPIO25 |
| 3 | GPIO26 | GPIO27 |

One jumper wire. Keep it short, and keep the existing single ground path — do not add a second.

## 2 · THE DRIVER PATCH — `0001-adau1372-MODE_MP6-as-serial-output-1.patch`

**Mainline actively takes that pin away at probe.** `[measured]`
`sound/soc/codecs/adau1372.c:1001-1002`:

```c
regmap_write(regmap, ADAU1372_REG_MODE_MP(1), 0x00); /* SDATA OUT */
regmap_write(regmap, ADAU1372_REG_MODE_MP(6), 0x12); /* CLOCKOUT */
```

`MODE_MP1 = 0x00` is Serial Output 0 — already what we want for lane 0. But **`MODE_MP6 = 0x12` is
CLKOUT**, and `[fetched]` datasheet p.26: the CLKOUT function *"disables the `ADC_SDATA1` serial port
output."* `MODE_MP6 = 0x00` is *Serial Output 1* `[fetched]` p.78 Table 70.

**A userspace write holds only until the next probe**, which is why this is a patch and not a
register poke. Nothing else needs changing: `CLKOUT_SEL` (`0x07`), written just below in the same
function, applies only *"when Pin ADC_SDATA1/CLKOUT/MP6 is set to clock output mode"* `[fetched]`
p.46 — so it becomes inert rather than wrong.

**The patch is verified to apply, with both controls** `[measured]`:

- applies clean to the unpatched source (`exit 0`), and the result reads `MODE_MP(6), 0x00`
- re-applying to the patched tree is refused as *"previously applied"* rather than silently passing

Rebuild and reinstall:

```bash
patch -p1 < 0001-adau1372-MODE_MP6-as-serial-output-1.patch
make -C /lib/modules/$(uname -r)/build M=$PWD modules
sudo make -C /lib/modules/$(uname -r)/build M=$PWD modules_install && sudo depmod -a
```

> **Not submitted upstream, deliberately.** Changing a driver default would break any board that
> relies on CLKOUT. The correct upstream fix is the pinctrl support the driver's own comment says is
> missing.

## 3 · THE OVERLAY — `adau1372-pi5-4ch-overlay.dts`

Claims all ten `i2s1` pins (the stock `rp1_i2s1_18_21` group claims four, which is one lane) and
points the controller's `pinctrl-0` at that group. Channel order follows option (c):

| Capture ch | Codec input | Jack | Lane |
|---|---|---|---|
| 0 | AIN0 | J18 tip | 0, first word |
| 1 | AIN1 | J20 tip | 0, second word |
| 2 | AIN2 | J22 tip | 1, first word |
| 3 | AIN3 | J22 **ring** | 1, second word |

**`[measured]` it compiles** — `dtc -@` exits 0, and the resulting `.dtbo` carries `__fixups__` for
`rp1_gpio`, `i2s_clk_consumer`, `i2c_arm` and `sound`, `gpio22` in the pin list, and a
`__local_fixups__` entry for `pinctrl-0`. The known-good 2-channel overlay compiles the same way, so
`dtc` is not merely being permissive.

**The 2-channel overlay is left untouched** and remains the fallback. That rig state has a bit-exact
digital loopback behind it; this one has never run.

```bash
dtc -@ -I dts -O dtb -o adau1372-pi5-4ch.dtbo adau1372-pi5-4ch-overlay.dts
sudo cp adau1372-pi5-4ch.dtbo /boot/firmware/overlays/
# config.txt: dtoverlay=adau1372-pi5-4ch      (own line; do NOT also set dtparam=i2s=on)
```

---

## Bring-up order on Monday, and the checks that make each step falsifiable

**Do these in order and stop at the first failure.** Two of this lane's scars apply directly: a
register that reads back correctly can still do nothing, and a card that enumerates can have no
hardware behind it.

| # | Step | Pass when |
|---|---|---|
| 0 | Codec present | `i2cdetect` shows `0x3C`. **Not `aplay -l`** — the card enumerates with the board unplugged |
| 1 | Patched driver loaded | `grep -i '^3e' /sys/kernel/debug/regmap/1-003c/registers` reads **`0x00`**, not `0x12`. **This is the whole patch; if it reads `0x12` nothing downstream is interpretable** |
| 2 | Card up on the 4ch overlay | `arecord -l` lists `adau1372`; address it **by name**, `hw:CARD=adau1372,DEV=0` |
| 3 | **2 channels still work** (regression control) | `-c 2` records for exactly 3 s. If this broke, the overlay did it — revert and stop |
| 4 | 4 channels stream | `-c 4` takes **exactly 3 s** and returns **2,304,000 bytes** (3 × 48000 × 4 × 4B). **A short run is a failure that looks like a pass** — the Pi is the clock consumer, so only the codec pacing it gives real time |
| 5 | The new lane carries data | tap/tone on **AIN2 or AIN3 only**, and confirm channels 2/3 move while 0/1 stay quiet. **Then the reverse** — a tone on AIN0 must NOT appear on 2/3 |

Step 5's second half is the one to insist on. Four channels of plausible-looking data proves nothing
about *which* input landed where; this lane has already been caught by a slot map that was garbage
while the stream looked healthy.

```bash
arecord -D hw:CARD=adau1372,DEV=0 -f S32_LE -c 4 -r 48000 -d 3 four.wav
```

## Known-unknowns — stated before the run, not after

- **This configuration has never run on hardware.** It is built and reasoned. The first attempt is
  Monday. `[assumed]` that the driver accepts a 4-channel `hw_params` on this DAI at all; the Pi-side
  multi-lane capability is `[measured]` but never with *this* codec.
- **Lanes fill in order from the channel count and are not independently selectable.** `-c 4` means
  lanes 0 and 1. There is no way to ask for lane 1 alone, so lane 0 must be working for lane 1 to be
  testable — hence the step-3 regression control.
- `[gap]` **Channel-to-lane word order within a lane is assumed, not measured** — that AIN2 lands on
  capture channel 2 rather than 3. Step 5 settles it. Do not build a slot map on the table above
  until it has.
- **If 4b does not come up, option (c) still part-works.** The 1372 gives two of its four channels and
  which two is freely choosable through the SOUT muxes. Put **ADXL X and Y** on them and hold Z and
  the mic — two axes plus the 1860's mics is still a useful capture, and it keeps Monday moving.

## Not in scope here

The 1860 side (P9/P10 differential mics, the digital mic on the DMIC header at **1.8 V IOVDD — not
3.3 V**, see `peter/outbox/2026-09-18-005` §2), mic supply voltages and the measure-before-connect
checklist, the RME test order, and the P11 ~64 dB shortfall. All JULIETT's, all in the build spec.
