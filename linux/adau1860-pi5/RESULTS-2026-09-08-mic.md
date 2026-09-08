# Mic capture on P11 — duplex proven on 6.18.39, mic silent, and one of my claims retracted

**Date:** 2026-09-08 · **Agent:** LIMA · Peter plugged a mic into P11 and asked for a mic test.
All `[measured]` on `aeronode` (192.168.0.99, kernel `6.18.39+rpt-rpi-2712`).

## Closed: full duplex works on 6.18.39

The open item from 2026-09-04 (proven on 6.12.47, never re-verified) is **closed**.

- `dummy_duplex.ko` **compiles clean** against the 6.18.39 headers — no source change.
- `adauduplex` enumerates in **both** `aplay -l` and `arecord -l`. It is now **`card 1`**
  (vc4hdmi0 took card 0), so the device is **`hw:1,0`**, not `hw:0,0`.
- `arecord -d 3` returned **3.004 s** and 1,152,000 bytes = 144000 x 2ch x 4B. Real time, so the
  codec paced it. `dmesg` clean.

Installed persistently: dtbo in `/boot/firmware/overlays/`, module in
`/lib/modules/$(uname -r)/extra/` with `/etc/modules-load.d/adau1860-duplex.conf`. The TX line in
`config.txt` is commented, not deleted — going back is one edit. Backup at
`config.txt.bak-LIMA-mictest`.

## Closed: the ADC -> SPT0 -> I2S -> Pi chain carries real analog

`SPT0_ROUTE0 = 38` (ADC2), `ADC2_EN`, `SPT0_OUT_EN` — capture came back with **2189 distinct
values**, not zeros, and a spectrum dominated by **49.8 Hz with harmonics at 100, 200 and 400 Hz**.
Mains hum. **The front end is live and picking up the room** — the positive control arrived free,
without needing a working microphone.

`STT_PATH.md`'s prediction that a mic is a *direct* route (`ADC -> SPT0`, unlike the 2026-09-04
loopback that needed EQ0) is **confirmed on hardware**.

## The mic itself: no acoustic response in 45 seconds

180 windows of 250 ms, high-passed above 120 Hz to step over the mains pickup:

```
full-band RMS   -85.7 dBFS  +/- 0.2 dB   across the whole 45 s
>120 Hz RMS     -98.5 dBFS  +/- 0.4 dB
windows >6 dB above floor:  ZERO
```

**CONFIRMED 2026-09-08, tap witnessed.** Peter tapped the mic hard, six times in two groups of
three, and said so. Re-captured 40.0 s and looked for transients above 200 Hz at 25 ms resolution
— a knuckle tap is broadband, mains pickup is not:

```
full-band RMS                   -92.6 dBFS
>200 Hz median envelope         -87.5 dBFS
>200 Hz maximum envelope        -84.1 dBFS   (at t=31.20 s)
peak-to-median ratio             3.5 dB      over the whole 40 s
events > median +6 dB            0
events > median +10 dB           0
events > median +20 dB           0
```

**3.5 dB peak-to-median across 40 seconds is stationary noise.** A working capsule taps in at
20-40 dB above its floor. Not one window moved. The earlier flat result was not a missed tap —
**the microphone produces nothing at all.**

Not "quiet", *nothing*: an electret's JFET needs drain current to amplify, and with no bias it does
not conduct, so there is no small signal to dig out with more gain.

## The route sweep, which is the interesting measurement

Same PGA settings per channel as configured, 2 s each:

| Route | Input | RMS | 50 Hz | uniq |
|---|---|---|---|---|
| 36 | ADC0 / **P9, empty** | **−28.1 dBFS** | −33.6 | 81548 |
| 37 | ADC1 / **P10, empty** | −70.8 dBFS | −97.0 | 1090 |
| 38 | ADC2 / **P11, MIC** | **−85.9 dBFS** | −92.8 | 2147 |

**The jack with the microphone in it is the quietest of the three — by 58 dB against an empty
one, and ADC2 is carrying +24 dB of PGA gain that ADC0 is not.** Referred to the input that is a
~82 dB difference.

An empty high-impedance input floats and works as an antenna, which is what P9 is doing. For P11
to be that much quieter, **something is loading it down**. Two candidates, and I cannot separate
them from here:

1. **The mic capsule is loading the input** — it is electrically present, and silent because
   nothing biases it. This is the predicted outcome (`MIC_INPUT_P11.md`).
2. **`P13`/`P15` are in a single-ended position that grounds `AINP2`**, disconnecting the TIP
   entirely. A shorted input is also very quiet.

`[gap]` **Needs eyes on the board:** the P13/P15 jumper position. Default per UG-2017 Table 3 is
differential — `P13` pin 1-2 **and** `P15` pin 1-2.

## RETRACTION — the power cycle was probably not necessary

I told Peter the EVB power cycle "mattered" because `PGA2_EN` lives in `PLL_PGA_PWR` (`0x4000C005`),
which `bringup.sh` documents as one of three **cold-only** registers.

**That was wrong, and I am correcting it before it becomes procedure.** Later in the same session,
with the part fully powered up and running, I wrote `PGA0_EN` and `PGA1_EN` into that same register
and **both latched**: `0x43 -> 0x73`, read back `0x73`. `[measured]`

So the **PGA enable bits are writable while hot.** I never actually tested `PGA2_EN` hot — I
asserted it would fail from the register's cold-only reputation and power-cycled first, which made
the claim unfalsifiable in exactly the way §3 warns about. The cold-only property presumably
applies to other bits in that register (`XTAL_EN`, `PLL_EN`), not to the PGA enables.

**Practical consequence:** enabling the analog gain does **not** require asking Peter to power-cycle
the board. `bringup.sh`'s comment should be narrowed to the specific bits that are genuinely
cold-only, once someone measures which those are.

## Next

**Both closed.** Peter confirms **`P13` and `P15` are both on pins 1-2** — the differential
default — so `AINP2` is not grounded and the TIP reaches the ADC. And the tap test is now witnessed
and flat.

That leaves exactly one explanation standing, reached by elimination rather than assumption:
**the capsule is electrically present (it damps 82 dB of antenna pickup) and acoustically dead
because nothing biases it.** Which is what `MIC_INPUT_P11.md` predicted from the schematic before
the mic was ever plugged in.

**The fix is an amplified module** — MAX9814 or MAX4466 class, powered from the Pi's 3.3 V. Nothing
else about the path needs to change: duplex, the route, the gain and the transport are all proven
and waiting. `[gap]` parts not yet priced or stock-checked.


---

## 2026-09-08 later — the unplug test refuted my explanation, twice over

**Prediction:** unplug the mic and P11 should go loud, proving the plug was grounding the inputs.
**Result:** it stayed quiet. `[measured]`

```
route=38  ADC2 / P11  MIC UNPLUGGED   -89.1 dBFS
route=36  ADC0 / P9   empty           -25.0 dBFS
route=37  ADC1 / P10  empty           -28.7 dBFS
```

**P11 is quiet with nothing in it at all.** So neither the microphone nor the connector was ever
the cause — the ~64 dB difference is a property of the **ADC2 channel**, present with an empty jack.

### The PGA gain field does almost nothing — retracting a number I quoted

I claimed P11 was "82 dB quieter *while carrying +24 dB of PGA gain*". A two-sided control kills
that:

| change | result |
|---|---|
| `PGA2_GAIN` 1951 -> 0 | ADC2 −89.1 -> −91.5 dBFS (**2.4 dB**) |
| `PGA0_GAIN` 0 -> 1951 | ADC0 −25.0 -> −22.2 dBFS (**2.8 dB**) |

The full span of an 11-bit field the datasheet calls a **0-24 dB** PGA moves the level by **~2.5 dB**,
in both directions, on two different channels. `[gap]` **Either the gain code is not what I think it
is, or the PGA is not actually in circuit** — something else (an input mux, a bypass, a mode bit)
must be enabled first. `adi_lark_adc.c`'s call order is the place to look.

**Consequences:** the "82 dB referred to input" figure was wrong — the true difference is ~64 dB
with no gain correction to apply. And **swapping the gains did not swap the behaviour**, which is
what rules the PGA out as the cause entirely.

### What is actually left

The difference is physical and upstream of every register I have touched. `AINP0`/`AINN0` float on
an empty jack and pick up mains; `AINP2`/`AINN2` do not. The obvious candidate is the **input-mode
jumpers**: `P13`/`P15` for ADC2 versus `P104`/`P105` for ADC0. Peter reports P13/P15 on pins 1-2,
which per UG-2017 Table 3 is differential and should float — so either the report, the silkscreen
numbering, or my reading of Figure 8 is wrong.

`[gap]` **Cheapest next check, and it needs no pin numbers:** compare the jumper positions of
`P13`/`P15` against `P104`/`P105` **relative to each other**. ADC0 demonstrably floats and ADC2
demonstrably does not; if the two pairs are in different positions, that is the whole answer.

### The method note worth keeping

Three explanations were offered for P11's quietness and **all three were wrong**: the unbiased
capsule, the TRRS plug grounding the inputs, and the PGA gain. Each was plausible, each fitted the
data available at the time, and each died to one cheap control. The pattern is that every one of
them was a story about **the thing I had just changed** — the mic, the plug, the register I wrote —
while the real difference sat in a channel property nobody had touched. **Suspect the constant, not
just the variable.**
