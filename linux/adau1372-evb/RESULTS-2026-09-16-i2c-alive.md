# ADAU1372 on the Pi's own I2C — confirmed, clocking, transporting. ADCs silent.

`[measured]` 2026-09-16 on `aeronode.local` (Pi 5, 6.18.39+rpt-rpi-2712), after Peter wired the EVB's
control port to the Pi's **i2c-1** and confirmed the USBi's **D1 (I2C mode) LED is lit**.

## Confirmed: it is an ADAU1372, at 0x3C

`i2cdetect -y 1` now shows **0x3c** (and 0x51 — see the warning below). Six of seven datasheet reset
values read back exactly, over 16-bit register addressing (`i2ctransfer -y 1 w2@0x3c 0x00 0xRR r1`):

| reg | read | datasheet reset | |
|---|---|---|---|
| 0x1B ADC_CONTROL0 | 0x19 | 0x19 | OK |
| 0x1C ADC_CONTROL1 | 0x19 | 0x19 | OK |
| 0x23 PGA_CONTROL_0 | 0x40 | 0x40 | OK |
| 0x2E DAC_CONTROL1 | 0x18 | 0x18 | OK |
| 0x31 OP_STAGE_MUTES | 0x0F | 0x0F | OK |
| 0x3E MODE_MP6 | 0x11 | 0x11 | OK |
| **0x29 POP_SUPPRESS** | **0x00** | **0x3F** | **mismatch — see correction 1** |

That cannot happen by accident. **The part is alive and the control port works.**

## The control port is gated on the internal clock — with a clean negative control

Writes to `ADC0_VOLUME` (0x1F) did **not** stick until `CLK_CTRL` (0x00) was written. With
`CLK_CTRL = 0x03` or `0x01` (MCLK enabled), `0x55` and `0x33` both read back exactly; with
`CLK_CTRL = 0x00` (MCLK disabled) the same writes read back `0x00`. So the EVB oscillator **is
running**, and the datasheet's "most registers are inaccessible unless the internal clock is enabled"
is literally true.

`[gap]` This does **not** discriminate 12.288 MHz from 24.576 MHz — register access works under both
`CC_MDIV` settings. The EVB's MCLK frequency is still unknown; the overlay assumes 12.288 MHz.

## The codec drives the I2S clocks, and the Pi locks to them

With `SAI_1` (0x33) `SAI_MS = 1`:

| pin | before | after |
|---|---|---|
| GPIO18 `I2S1_SCLK` | lo × 80 | **hi=39 lo=41** |
| GPIO19 `I2S1_WS` | lo × 80 | **hi=41 lo=39** |

A dead line reads 80/0; a running clock scatters. `arecord -f S32_LE -c 2 -r 48000 -d 2` on the
existing `adauduplex` dummy-codec card then ran clean — 96000 frames, no XRUN, no EIO. **Worth
noting against the 2026-09-07 ADAU1860 scar: the Pi locked to this codec's clocks first time.**

## The transport is proven end to end — by loopback, not by assumption

Routing `SOUT_SOURCE_0_1` (0x13) `= 0x98` sends **Serial Input 0/1 straight back out** on slots 0/1.
Playing a 1 kHz tone on GPIO21 while recording GPIO20 returned **peak −0.5 dBFS on slot0 and
−0.9 dBFS on slot1**.

So: Pi TX → codec `DAC_SDATA` → codec `ADC_SDATA0` → Pi RX all work, **both data pins are wired
correctly**, and the serial port, framing and slot mapping are good. This is the measurement that
turns "it might be wiring" into "it is not wiring".

## What does NOT work: the ADC path returns exact zeros

With the full chain configured — `ADC_SDATA0` pin set to serial output, output ASRC enabled,
decimators powered, muxes routed, PGAs unmuted — capture is **0 nonzero samples out of 96000**, on
both slots. Even with **PGA0 at +35.25 dB into a floating input**, which must produce obvious noise
if the analog front end and ADC are alive.

Registers verified in place at the time: `0x00=0x03 0x13=0x54 0x18=0x54 0x1a=0x02 0x1b=0x01
0x1d=0x03 0x23=0xBF 0x32=0x00 0x33=0x01 0x34=0x00 0x39=0x00 0x44=0xFF`.

**Leading hypothesis `[assumed]`: the EVB's analog supply (AVDD) is not present or not linked.**
Every digital function works perfectly — control port, oscillator, serial port, clock generation,
data output. Only the analog-to-digital path produces literally nothing. A missing AVDD (or an
unfitted supply link) fits that split exactly. Worth a meter before any more register archaeology.

Second candidate: something in the hand-rolled init sequence is still wrong, which is why the next
step is to let the **mainline driver** run its own validated init rather than keep guessing.

## Two corrections to CONFIG-PLAN.md

**Correction 1 — `POP_SUPPRESS` (0x29) does not reset to 0x3F; it reads 0x00.** Verified readable and
writable: writing 0x3F reads 0x3F, writing 0x0F reads 0x0F, so this is a real value and not a dead
register. The plan said that for single-ended line inputs on AIN1/2/3 "the correct configuration is
*don't touch it*" because `PGA_POP_DISx` was already 1 at reset. **That was wrong.** Those bits are
0, and the datasheet asks for them to be set for a single-ended line input, so they must be written
explicitly. The datasheet's own reset column for this register disagrees with the silicon.

**Correction 2 — two registers must be written that the plan never mentioned**, both of which the
mainline driver sets at probe and neither of which is obvious from the register map:

- **`MODE_MP1` (0x39) resets to 0x10 = "push-button volume up".** The pin is `ADC_SDATA0/MP1`, so
  until it is set to **0x00 (Serial Output 0)** the codec's only data output pin is not a data
  output at all. A capture will run perfectly and return silence.
- **`ASRC_MODE` (0x1a) bit 1 `ASRC_OUT_EN` resets to 0.** The whole ADC capture path runs through the
  output ASRCs, so with this clear nothing reaches the serial port. The driver models it as the
  `Output ASRC Supply` DAPM widget.

## Warning: 0x51 on i2c-1 is the USBi's own EEPROM

AN-1006 states the USBi carries an EEPROM at **0x51** holding its VID/PID and firmware, and warns
against a second EEPROM at that address. With the ribbon attached while the Pi drives the bus, that
EEPROM now sits on the Pi's I2C bus: **a stray write to 0x51 would brick the USBi.** It also means
two potential masters on one bus. **Unplug the USBi ribbon when the Pi owns the bus.**

## State the codec was left in

`SOUT_SOURCE_0_1` restored to `0x54` (ASRC0/ASRC1), `POP_SUPPRESS` left at `0x0F`, PGA0 at +35.25 dB,
`CLK_CTRL = 0x03`, `SAI_MS = 1`. All of it is volatile — a power cycle returns the part to reset.

## Staged, not yet run

`adau1372-pi5.dtbo` is built and installed in `/boot/firmware/overlays/`; `config.txt` is backed up.
Loading it needs `dtoverlay=adau1860-duplex` (line 81) commented out, because that overlay holds the
same `i2s_clk_consumer` block and GPIO18-21 — and that needs a reboot and Peter's say-so.

---

# Update — the mainline driver is running, and the ADC is still silent

`[measured]` 2026-09-16, after swapping `dtoverlay=adau1860-duplex` for `dtoverlay=adau1372-pi5`
and rebooting.

## The driver had to be built — Raspberry Pi OS does not ship it

`snd-soc-adau1372` is **not built in the Pi kernel**: nothing matching `adau1372` in
`/lib/modules/6.18.39+rpt-rpi-2712/kernel/sound/soc/codecs/` (which has 54 codec modules, including
adau1701/1977/7002 — but adau1372 and its `adau-utils` dependency are absent). The card sat in
`deferred probe pending: asoc-simple-card: parse error`, which was simply the codec DAI never
appearing.

Built out-of-tree against the running kernel — headers were already installed:

```
cd ~/adau1372/build
# adau1372.c adau1372-i2c.c adau1372.h adau-utils.c adau-utils.h from raspberrypi/linux rpi-6.18.y
obj-m += snd-soc-adau1372-oot.o
snd-soc-adau1372-oot-objs := adau1372.o adau1372-i2c.o adau-utils.o
make -C /lib/modules/$(uname -r)/build M=$PWD modules
sudo cp snd-soc-adau1372-oot.ko /lib/modules/$(uname -r)/extra/ && sudo depmod -a
sudo modprobe snd-soc-adau1372-oot
sudo modprobe -r snd_soc_simple_card && sudo modprobe snd_soc_simple_card   # kick the deferred probe
```

Result: driver bound (`/sys/bus/i2c/devices/1-003c/driver -> adau1372`) and
**`card 2: adau1372 [adau1372], device 0: 1f000a4000.i2s-adau1372`** with all 50 mainline ALSA
controls.

## RP1 DOES lock to this codec's TDM4 frame

`arecord -D hw:2,0 -f S32_LE -c 4 -r 48000` negotiated **channels 4, exact rate 48000**, and streamed
8 seconds with no XRUN or EIO. **This settles open question 5 of CONFIG-PLAN in the affirmative and
does not repeat the 2026-09-07 ADAU1860 failure.** The difference is the one predicted: the ADAU1372
runs TDM with a 50%-duty LRCLK (`LR_MODE = 0`) when the DAI format is `i2s`, and RP1's DesignWare
block locks to that where it would not lock to the ADAU1860's narrow frame sync.

`[gap]` Which ADC lands in which slot is still unverified — with all channels at zero there is
nothing to identify. That test waits on signal.

## The digital path is complete, by the driver's own account

DAPM widget states sampled **during** an active capture (sampling them afterwards shows everything
`Off`, which was a broken measurement on the first attempt):

```
AIN0: On                      Output ASRC Supply: On
PGA0: On                      Output ASRC0 Decimator: On
ADC0: On                      Output ASRC0 Mux: On
ADC0 Filter: On               Serial Output 0 Capture Mux: On
Decimator0 Mux: On            Capture: On  in 4 out 1
```

Every stage of the capture chain is powered, and the capture still returns **0 nonzero samples out of
384000 frames on all four channels**.

## Conclusion: the fault is in the analog front end, and it is not software

Stacking the evidence:

| Subsystem | Status | Proof |
|---|---|---|
| Control port | works | 6/7 reset values; write/readback under clock gating |
| Oscillator | running | writes stick only with MCLK enabled |
| Clock generation | works | BCLK/LRCLK scatter 39/41 where they were stuck low |
| Data pins, both directions | works | serial-in -> serial-out loopback at −0.5 dBFS |
| Serial port, framing, TDM4 | works | 4 ch @ 48 kHz negotiated, 8 s clean |
| Digital routing | works | driver's own DAPM reports the whole chain On |
| **ADC output** | **exact zeros** | 384000 frames, four channels, incl. PGA at +35.25 dB |

A converting ADC with a floating input and +35 dB of gain cannot produce mathematically exact zeros.
Every hypothesis that blamed the register sequence is now dead — the mainline driver's own
initialisation reproduces it exactly.

**`[assumed]` What remains is the analog supply: AVDD absent, or an EVB supply link unfitted.** It
explains the clean split — every digital function perfect, the analog-to-digital path producing
literally nothing — and nothing else on the list does.

Two ways to settle it, both needing hands on the bench:

1. **Meter AVDD at the codec** (datasheet: AVDD pin 10, 1.8 V to 3.3 V), and check the EVB's supply
   selection links.
2. **Play to the DAC and listen on the EVB headphone output.** The DACs share AVDD with the ADCs, so
   audible output would clear the analog supply and send the search back to the input stage.

## Control names — correction to setup-inputs.sh

Measured against the live card: the mux controls are **`Output ASRC0 Mux`**, not
`Output ASRC0 Capture Mux`. `Serial Output 0 Capture Mux` and `Decimator 0+1 Capture Mux` were right.
Fixed in the script.

`[own-goal]` The control dump in this session first printed names like `ADC +3 Bias` and
`PGA  Capture Switch`, which looked like missing controls. That was `tr -d "\x27"` — `tr` has no hex
escape, so it deleted literal `\`, `x`, `2` and `7` characters from the output. The instrument was
wrong, not the card. Same class of error as the `find /proc/device-tree` miss earlier in the session:
`/proc/device-tree` is a symlink and `find` does not follow it, so the codec node appeared absent
when it was present all along.
