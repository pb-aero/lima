# IM73A135 vs IM72D128V — the two Infineon mics, compared from the datasheets

**Date:** 2026-09-22 · **Agent:** LIMA · **Status:** derived from both datasheets. Nothing measured.
**Trigger:** Peter, after the phase budget: *"how does this mic compare with the IM73A135"*.

`[fetched]` IM73A135V01 datasheet **V1.20** (2021-07-07) and IM72D128V datasheet **v01.00**. Both
pinned in `scripts/fetch-datasheets.sh`; Infineon serves both to `curl` directly, unlike analog.com.

---

## 1. Side by side

| | **IM73A135V01** (analog, differential) | **IM72D128V** (digital PDM) |
|---|---|---|
| Output | **Differential analog** | PDM bitstream |
| Sensitivity | −38 dBV @ 94 dBSPL (**12.6 mV/Pa**) | −36 dBFS @ 94 dBSPL |
| **SNR** | **73 dB(A)** | 71.5 dB(A) @ fCLK 3.072 MHz |
| Noise floor | −111 dBV(A) | — |
| **AOP (10% THD)** | **135 dBSPL** | 128 dBSPL |
| **THD @ 94 dBSPL** | 0.5% | **0.1%** |
| **LF cutoff (−3 dB)** | 20 Hz | **11 Hz** |
| **Phase @ 75 Hz** | **12°** | **11°** |
| Phase @ 1 kHz | +2° | −0.3° |
| **Group delay @ 250 Hz** | **52 µs** | 60 µs |
| Group delay @ 1 kHz | **2 µs** | 6 µs |
| Group delay @ 4 kHz | **0.5 µs** | 3.5 µs |
| **Polarity** | Increasing Vout = increasing SPL | Positive pressure = more 1's |
| Tolerance | ±1 dB | — |
| Package | 4 × 3 × 1.2 mm | — |
| Ingress | IP57 | IP57 |

## 2. The finding that matters most: their phase is nearly identical

**12° against 11° at 75 Hz.** `[derived]` Mic-to-mic that is a **1° residual**, which alone would
allow **−35 dB** of cancellation — i.e. between two microphones the low-frequency phase error is
essentially **common-mode and cancels.**

That is worth stating plainly because it isolates the real problem. `[repo]`
`docs/dvnc-phase-budget.md` shows the DVNC mismatch is **18–21°** across 50–300 Hz — and none of that
is a mic-versus-mic effect. It is **mic versus accelerometer**: both mics roll off at 11–20 Hz and lead
in phase there, while the ADXL354 is a `[fetched]` sinc filter contributing a **pure 148 µs delay** and
no low-frequency lead at all.

**So the phase problem is structural to using a vibration reference, not a property of either mic.**
Swapping mics does not touch it.

Note also that their **group delays are close** — 52 µs against 60 µs at 250 Hz — so a mic-to-mic
delay mismatch is ~8 µs, against the accelerometer's 148 µs. The accelerometer is the outlier by a
factor of roughly three.

## 3. Where each one actually wins

**IM73A135, for the cups' FF and FB sensors:**

- **+1.5 dB SNR** (73 vs 71.5 dB(A)) — and ANC performance is set by the error mic's noise floor.
- **+7 dB AOP** (135 vs 128 dBSPL). In a cockpit that is real headroom, not a spec-sheet flourish.
- **Lower and flatter group delay** above 250 Hz — 2 µs vs 6 µs at 1 kHz, 0.5 µs vs 3.5 µs at 4 kHz.
  Less phase to correct across the band.
- **Differential output**, so common-mode rejection on the run into an earcup. `[repo]` This is why the
  cup mics connect straight to the 1861's differential inputs with no receiver.

**IM72D128V, for the audio board:**

- **5× lower distortion** at 94 dBSPL (0.1% vs 0.5%).
- **Lower corner**, 11 Hz vs 20 Hz.
- **It costs no analog channel.** `[repo]` The ADAU1861 has only **three** ADCs and eight independent
  DMIC inputs — so a digital mic is free where an analog one is scarce. On a board already spending
  three ADCs on accelerometer axes, that is decisive.
- No coupling capacitors, no analog routing, no buffer.

## 4. System headroom — the digital mic is the tighter of the two

`[derived]` from each datasheet plus the codec's full scale:

| | Chain limit | Set by |
|---|---|---|
| IM73A135 → ADAU1861 | **131.8 dBSPL** | the **codec** — 0.98 V rms FS ÷ 12.6 mV/Pa = 77.8 Pa; the mic's 135 dB AOP is 3.2 dB beyond it |
| IM72D128V (PDM) | **128.0 dBSPL** | the **mic** — 0 dBFS sits at 130 dBSPL, and its 128 dB AOP arrives 2 dB earlier |

**The analog chain has 3.8 dB more usable headroom**, and the limits sit on opposite sides: with the
analog mic the codec clips first and the mic still has margin; with the digital mic the mic distorts
before the numeric full scale, so there is nothing to recover by turning gain down.

`[repo]` This confirms the existing note that *"the codec clips 3 dB BEFORE the mic does"* for the
analog part — **3.2 dB**, from the datasheet rather than from memory.

## 5. Polarity — both non-inverting, and that closes a sign term

`[fetched]` IM73A135: *"Increasing Vout"* for *"Increasing SPL"*. IM72D128V: *"Positive pressure
increases density of 1's."*

**Both are non-inverting**, so they agree with each other and neither introduces a sign flip. `[repo]`
That leaves the ADAU186x's 180° analog-path inversion as the only deliberate sign in the chain, plus
the accelerometer's axis convention. Two of the four sign terms flagged in the level-shifter work are
now closed.

## 6. Conclusion

**Keep both, for the reasons the architecture already implies.** The IM73A135 is the better *acoustic*
part — more SNR, far more headroom, lower group delay — and belongs where acoustic performance decides
the outcome, which is the cups. The IM72D128V's advantage is architectural rather than acoustic: it
consumes none of the ADAU1861's three scarce ADC channels.

**Neither choice moves the phase problem**, because that is mic-versus-accelerometer and both mics sit
on the same side of it.

`[gap]` Not established: the IM72D128V's `[graph]` phase at 50/150/300 Hz is read off Figure 4 (±2–3°);
the IM73A135's phase curve has not been read off its Figure 4 at all, only the three tabulated points.
If a correction filter is to be designed rather than measured, both curves want tabulating properly.

## Sources

- **IM73A135V01 datasheet V1.20**, 18 pp, Infineon, 2021-07-07 — Table 3 acoustic characteristics p.6,
  Table 4 free-field response p.7.
- **IM72D128V datasheet v01.00**, 19 pp, Infineon, 2025-05-04 — Table 2 acoustic specifications p.5,
  Figures 4 and 5 p.4.
- `[repo]` `docs/dvnc-phase-budget.md`, `docs/two-adau1860-channel-allocation.md`,
  `docs/audio-board-decision-record.md`.
