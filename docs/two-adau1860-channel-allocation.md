# Two ADAU1860s for stereo — channel allocation, and why the split goes by EAR not by function

**Date:** 2026-09-14 · **Agent:** LIMA · **Status:** analysis + recommendation. `[gap]` not ruled.

Peter, 2026-09-14: *"We will need 2 adau1860 evb for stereo. My thinking is we use one for dvnc using
the analog accelerometer ADXL354 and analog mic IM73A135 and the other for the feedback feedforward
mics IM73A135 as well as the electret boom mic."*

Provenance: `[fetched]` = read from the vendor PDF this session, spec quoted · `[derived]` =
arithmetic shown · `[repo]` = in this repository · `[gap]` = not established.

**Two ADAU1860s is right, and it is the first thing that makes per-ear ANC possible at all** —
`[repo]` §22 of `docs/h1-headset-mute-relay.md` recorded that the single-DAC part could never do it.
The part count is correct. **The proposed split of work across the two parts is not**, and §1 is why.

---

## 1. The split by function does not produce stereo

Each ADAU1860 has `[fetched]` **three ADCs and one DAC**. Under the proposed allocation:

| | EVB 1 (DVNC) | EVB 2 (ANC + voice) |
|---|---|---|
| ADCs | ADXL354 + one IM73A135 | FF mic + FB mic + boom electret — **full** |
| DAC | DVNC anti-tone, **mono** | ANC anti-noise, **mono** |

Four problems, in order of how hard they are to fix:

1. **There is still only one FF/FB pair, so only one earcup is being cancelled.** A feedback mic
   senses the residual *at one ear*. Copying that cup's anti-noise into the other cup applies a
   correction derived from the wrong acoustic path — at the frequencies where ANC earns its keep the
   two cups are acoustically independent, so the second ear gets **added noise, not cancellation**.
   Two chips split this way still buy mono ANC.
2. **Two DACs, two functions, one pair of ears — so they must be summed in analog anyway.** The
   summing amplifier from `docs/anc-dvnc-summing-amp.md` would now carry **three** inputs per ear
   (comm, ANC, DVNC) instead of two, and its headroom budget (§5 there) gets a third coherent term.
3. **The feedback loop crosses a chip boundary.** FB mic on EVB 2, DVNC on EVB 1, both landing in the
   same earcup: the DVNC output is now an uncontrolled disturbance inside the ANC loop's error path,
   arriving with an inter-chip transport delay. `[repo]` §19 puts the whole feedforward budget at
   **FastDSP, 768 kHz** precisely because ~1 ms at 48 kHz is already too slow. An inter-chip hop
   inside that loop is not affordable.
4. **It contradicts the bit map that already exists.** See §2.

---

## 2. John's Rev G upstream map already answers this — the split is per cup

`[repo]` `docs/johns-bitmap.html`, upstream, 6 × 24-bit:

| Slot | | | Slot | | |
|---|---|---|---|---|---|
| 0 | Cup A — FF | feed-forward mic | 3 | Cup B — FF | feed-forward mic |
| 1 | Cup A — FB | feedback / error mic | 4 | Cup B — FB | feedback / error mic |
| 2 | Cup A — voice | boom mic uplink | 5 | **Cup B — spare** | **unallocated** |

**Three channels per cup. That is exactly one ADAU1860's analog budget per cup, and it is not a
coincidence** — one codec per cup is the A2B architecture. Two EVBs on the bench is the correct
prototype of two cup codecs, provided they are clocked together (§5).

**And Cup B's slot 5 is spare because the pilot has one mouth.** That is where the DVNC reference
belongs. The allocation writes itself:

| | **Chip A — Cup A (left)** | **Chip B — Cup B (right)** |
|---|---|---|
| ADC0 | IM73A135 feed-forward, **differential** | IM73A135 feed-forward, **differential** |
| ADC1 | IM73A135 feedback, **differential** | IM73A135 feedback, **differential** |
| ADC2 | **Boom voice** (see §4) | **ADXL354, one axis, single-ended — DVNC reference** |
| DAC | Left earcup | Right earcup |

Both chips exactly full, nothing spare, and each cup's feedback loop closes on the chip that drives
it. DVNC parameters computed on Chip B reach Chip A the way Rev G already specifies — `[repo]`
byte-packed parameter frames on **downstream slot 2 at ~10% occupancy** — or over the second serial
port chip-to-chip. `[gap]` which, not decided.

**The accelerometer costs nothing that was being used.** That is the whole point of putting it there.

---

## 3. The parts, checked

### ADXL354 — good choice, and for a better reason than bandwidth

`[fetched]` ADXL354/ADXL355 Rev. A: three **single-ended** outputs `XOUT`/`YOUT`/`ZOUT` referred to
`V1P8ANA/2`; **400 mV/g** typ at ±2 g (200 at ±4 g, 100 at ±8 g); **20 µg/√Hz**; internal low-pass
**fixed at 1500 Hz, 50% response**; supply **2.25–3.6 V**, **150 µA**.

- **One axis, not three.** Three outputs would consume all three ADCs and a harmonic *reference*
  needs frequency and phase, not a vector. `[gap]` Which axis is a bench question — pick the one
  with the best harmonic SNR at blade-pass in the real airframe.
- `[derived]` **Headroom: 0.693 V pk** (the ADAU1860's `[fetched]` 0.49 V rms single-ended full
  scale) ÷ 400 mV/g = **1.73 g peak at 0 dB PGA**. Using the PGA's 24 dB drops that to **0.11 g**.
  `[gap]` airframe vibration at the headset mount is unmeasured, so the range strap and the PGA
  setting are both undecided.
- `[derived]` Noise: 20 µg/√Hz × 400 mV/g = **8 nV/√Hz** referred to the codec input. That is far
  below anything the ADAU1860 will contribute, so **the accelerometer will not be the noise floor —
  the codec will.** `[gap]` ADAU1860 input-referred noise is not in the abridged datasheet (the same
  no-register-map gap `linux/adau1860-pi5/` has carried since 2026-09-02).
- **AC-couple it.** `[repo]` `docs/h1-audio-board-codec-selection.md` §3: every one of these inputs
  is AC-coupled, and the ADXL354 sits at 0.9 V DC. Set the corner with the cap and pick the
  ADAU1860's 8 Hz digital HPF — the DVNC band starts around 50 Hz, so unlike the vibration work in
  `dsp/vibration-reference/` (dominant content at **8.30 Hz**, `[measured]`) the HPF is helpful here
  rather than destructive. **Same part, opposite filter decision, because the job is different.**

**The real argument for the analog ADXL354 over the digital ADXL355 is clock-domain coherence, not
bandwidth.** A tonal canceller lives or dies on the phase relationship between its reference and its
anti-tone. Into the codec's own ADC, reference and output share one sample clock and that
relationship is fixed by construction. Read over SPI by the CM5, it is not — you would be re-locking
phase in software across two asynchronous domains, forever. `[derived]`

### IM73A135 — right part, and one number that must not be ignored

`[fetched]` Infineon IM73A135V01, Rev. 1.00: **differential output**; sensitivity **−38 dBV**
(1 kHz, 94 dB SPL) = **12.6 mV/Pa**; **SNR 73 dB(A)**; **AOP 135 dB SPL** (THD 10%); noise floor
**−111 dBV(A)**; **low-frequency cutoff 20 Hz** (−3 dB re 1 kHz); **170 µA at 2.75 V**;
4 × 3 × 1.2 mm.

- **Differential output into differential inputs** — this is the part of the plan that is simply
  correct. It buys the ADAU1860's **0.98 V rms** differential full scale instead of 0.49 single-ended,
  and rejects cable-borne noise. `[repo]` §19's pseudo-differential capacitor front end was a
  workaround for single-ended modules; with the IM73A135 it becomes a real differential connection.
- `[derived]` **The codec clips 3 dB before the microphone does.** 0.98 V rms ÷ 12.6 mV/Pa = 77.8 Pa
  = **131.8 dB SPL** at 0 dB PGA, against the mic's 135 dB SPL AOP. **So the FF channel's PGA stays
  at 0 dB.** At a 100 dB SPL cockpit the mic delivers 25.2 mV rms = **−31.8 dBFS** — ample.
- **20 Hz cutoff is flat through the whole DVNC band.** No repeat of the §19 transformer scare.
- **`[fetched]` Phase response: +12° at 75 Hz** (2° at 1 kHz, −2° at 3 kHz). Group delay 52 µs at
  250 Hz, 2 µs at 1 kHz. `[derived]` **An uncorrected 12° phase error caps cancellation at
  2·sin(6°) = 0.209, i.e. −13.6 dB**, and it lands exactly on prop blade-pass. It is specified,
  repeatable and the sensitivity tolerance is ±1 dB, so it is **calibratable in the DSP — but it must
  be calibrated, not assumed away.** This is the single most important number on the microphone
  datasheet for this application and it is not the one on the front page.

### The electret boom mic — right for a reason that is acoustic, not electrical

`[repo]` §19 ruled against bare electret capsules on this part: the ADAU1860 has **no MICBIAS pin**
and only **0–24 dB** of PGA. That ruling stands electrically — an electret here needs an external
quiet rail, a bias resistor and a coupling cap that you design yourself.

**But the reason to want one anyway is directivity.** The IM73A135 is **omnidirectional**
`[fetched]`. An omni boom mic in a 100 dB SPL cockpit picks up the cockpit, not the pilot; aviation
boom mics are noise-cancelling pressure-gradient capsules for exactly this reason. So the instinct is
right and the ruling in §19 does not contradict it — §19 was about level, this is about pattern.

**There is a third option that costs no analog channel at all.** `[fetched]` UG-2017: the EVB
exposes **eight digital microphone (DMIC) channels** alongside the three analog ADCs. Voice uplink
has no latency constraint — unlike the FF/FB loop it is not inside a control loop — so it can be
**two PDM MEMS mics beamformed in the DSP**, which buys directivity in software and hands ADC2 back
to the analog budget on Chip A. `[gap]` **Confirm the 8 DMIC channels and 3 ADCs can be routed
simultaneously** — the abridged ADAU1860 datasheet still carries no register map, which is a
long-standing gap in this repo, not a new one.

---

## 4. Running two EVBs together — what UG-2017 actually says

`[fetched]` EVAL-ADAU1860 user guide UG-2017 Rev. 0, read this session:

1. **I²C address is strappable on switch `S14`: `0x64` / `0x65` / `0x66` / `0x67`.** Default is
   `0x64` on both boards, so **one must be changed** before they share a bus. This is a switch
   setting, not a problem — but it is the first thing that bites.
2. **Clock them together, or they will beat.** Three MCLK sources are provided: an external MCLK into
   `MCLKIN` via **`P3`** with the on-board oscillator disabled by a jumper on **`P25`**; the on-board
   **24.576 MHz oscillator**; or the on-board 24.576 MHz crystal. **Run one board's clock into the
   other's `P3`.** Two free-running oscillators on one head means two cancellers drifting against
   each other and against the comm audio — an audible, intermittent fault that will look like a DSP
   bug for a week.
3. **Single-ended vs differential is a per-channel jumper pair**, so mics-differential and
   accelerometer-single-ended coexist on one board with no rework: ADC0 = `P104`/`P105`,
   ADC1 = `P12`/`P14`, ADC2 = `P13`/`P15` (pins 1–2 differential, pins 2–3 single-ended).
4. **The analog output `P30` has a 32 Ω load fitted by default.** `[repo]` The aviation earphone is
   **320 Ω** and the summing amplifier presents 10 kΩ. **That load must come off** before any level
   measurement taken on the bench means anything about the aircraft.
5. Supplies: USB or a single 5 V; AVDD/HPVDD 1.8 V, IOVDD 1.8 V, DVDD 0.9 V from on-board LDOs.
   `[repo]` The 1.98 V IOVDD ceiling against a 3.3 V CM5 is the known level-shifting problem from
   `docs/h1-audio-board-codec-selection.md` §1 and it does not go away on the EVB.

---

## 5. What this changes downstream

- **The summing amplifier becomes two independent single-input summers, not a shared one.** Each cup
  has its own DAC, so `docs/anc-dvnc-summing-amp.md`'s `U1A` differential receiver is duplicated per
  chip and `ANTI` is no longer a shared node. The headroom budget (§5 there) is unchanged; the L–R
  question disappears completely.
- **`[repo]` §22's "per-ear ANC would need 2 DACs + 2 feedback mics = different codec" is now
  satisfied** — not by a different codec, but by two of this one.
- **`[repo]` §19's "channel budget is full with nothing spare" was true per chip and is still true.**
  Two chips does not create slack; it creates a second exactly-full chip. Any future analog channel
  still forces a part change.

## Open

1. `[gap]` **Ruling: split by ear, not by function?** Everything above depends on it.
2. `[gap]` Which ADXL354 axis, which range strap, and what PGA — all wait on a vibration measurement
   at the headset mount in the real airframe.
3. `[gap]` Boom voice: analog noise-cancelling electret (costs ADC2 + a bias network you design) or
   two PDM MEMS beamformed (costs nothing, needs the DMIC/ADC co-routing confirmed).
4. `[gap]` DVNC parameter transport between chips — A2B downstream slot 2 as Rev G specifies, or a
   direct SPT1 chip-to-chip link.
5. `[gap]` **Still open from §19 and still decides whether any of this is worth building: does the
   target headset already have its own ANR?** Two cancellers in one earcup is worse than either alone.

## Sources

- ADXL354/ADXL355 Rev. A — `https://www.radiolocman.com/datasheet/pdf.html?di=130145` (mirror;
  analog.com remains unreachable from this machine, the 2026-09-06 scar) `[fetched]`
- IM73A135V01 datasheet Rev. 1.00 —
  `https://www.infineon.com/assets/row/public/documents/24/49/infineon-im73a135-datasheet-en.pdf` `[fetched]`
- EVAL-ADAU1860 UG-2017 Rev. 0 —
  `https://docs.ampnuts.ru/analog.com.datasheet/adau1860/related_data/eval-adau1860-ug-2017.pdf` `[fetched]`
- In-repo: `docs/johns-bitmap.html`, `docs/h1-headset-mute-relay.md` §19/§22,
  `docs/h1-audio-board-codec-selection.md`, `docs/anc-dvnc-summing-amp.md`
