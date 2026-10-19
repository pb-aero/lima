# Proof of concept — I2S and I2C over 1 m of cable

**Date:** 2026-10-19 · **Agent:** LIMA · **Status:** test plan. Nothing measured yet.
**Trigger:** Peter, 2026-10-19 — "We need to run a proof of concept at 1 m for I2S and I2C."

Provenance: `[repo]` = in this repository · `[fetched]` = vendor document, cited · `[derived]` =
arithmetic shown · `[assumed]` = not checked, flagged · `[gap]` = not established.

---

## 1. What the PoC has to answer

Three questions, each with a number attached:

1. **Does I2S data survive 1 m bit-exact?** Pass = **zero bit errors over ≥ 3×10¹⁰ bits per lane**,
   which bounds BER < 10⁻¹⁰ at 95 % confidence `[derived]` (zero errors in N bits ⇒ BER < 3/N).
2. **Does I2C survive 1 m at the speed we need, while I2S runs in the same cable?** Pass =
   **≥ 10⁶ write/read-back transactions, zero NACKs, zero mismatches**, with SCL/SDA rise time
   inside the I²C spec limit for the chosen speed.
3. **What margin is left?** Pass/fail alone is not enough to design from. Record, at the receiving
   end: BCLK overshoot/undershoot, whether any edge is non-monotonic inside the V_IL–V_IH band
   (the double-clock failure), and the data-to-clock setup margin at the highest BCLK tried.

Out of scope: DO-160 compliance. The near-field sniff in §6 is a smell test only.

## 2. Why this is not a formality — three things already known

- **Clock direction decides which path is hard.** `[derived]` With the codec as clock master (the
  bench's proven configuration, `[repo]` `linux/adau1860-pi5/duplex/MULTILANE.md`), codec → Pi data
  travels *with* the clock, so the cable delay cancels. Pi → codec data does not: BCLK goes out 1 m
  (~5 ns), the Pi launches data, and the data comes back 1 m (~5 ns). That **~10 ns round trip plus
  the Pi's clock-to-out** is taken from the codec's setup window. At 3.072 MHz (163 ns half period)
  it's nothing. At 12.288 MHz (41 ns) it matters. **SDO (Pi → codec) is the line to watch.**
- **The cup board's I²C pull-ups won't do 400 kHz over 1 m.** `[repo]` R1/R2 are 10 kΩ to 1V8.
  `[assumed]` typical multicore cable ~50–100 pF/m, so 1 m plus three devices and the host is around
  150 pF. `[derived]` t_r ≈ 0.847·R·C = 0.847 × 10 kΩ × 150 pF ≈ **1.27 µs**, against an I²C limit of
  300 ns (400 kHz) or 1000 ns (100 kHz). It fails both. To meet 300 ns at 150 pF you need
  R ≤ 2.4 kΩ, and at 1.8 V with V_OL 0.4 V at 3 mA the floor is R ≥ 470 Ω. **The usable window is
  about 0.5–2.4 kΩ, not 10 kΩ.** The PoC must measure the real cable capacitance, not trust 150 pF.
- **The TXS0108E bench translator dislikes long, capacitive leads.** `[repo]`
  `docs/rig-logic-levels.md` §6 quotes TI: heavy capacitive load can time out the one-shot and cause
  *"output signal oscillations."* **Don't put 1 m of cable on a TXS0108E output.** Translate at the Pi
  end with the strapped-direction SN74LVC8T245 (the product part), so the cable is driven by a real
  push-pull buffer.

## 3. Bench setup

Reuse the existing rig. Insert the cable where the product will have it, between the host side and
the codec side.

```
 Pi 5 / CM5 ──[SN74LVC8T245, 3.3↔1.8 V]──┬── 1 m cable under test ──┬── ADAU1860 EVB (P2/P3, 1.8 V)
                                         │  BCLK  FSYNC  SDO  SDI   │
                                         │  SDA   SCL    GND ×n     │── I²C targets (EVB ctrl port,
                                         └─ probe points A ────────── probe points B ┘ LSM6/MAXM86161 breakouts)
```

| Item | Notes |
|---|---|
| Host | Pi 5 (bench `scopenode`) or CM5. RP1 `i2s1` 4-lane overlay, `[repo]` `duplex/i2s1-4lane-overlay.dts` |
| Far end | ADAU1860 EVB, codec as clock master. `[assumed]` ADAU1861 serial-port I/O behaves like the 1860's; the 1861 has no EVB here |
| Translator | SN74LVC8T245, at the **Pi end**. The cable runs at **1.8 V**, the product's cup-side level |
| I²C targets | EVB control port, plus LSM6DSV16BX and MAXM86161 breakouts if we have them (the cup-board bus) |
| Cables (A/B) | **A:** ribbon, GND between every signal. **B:** twisted pair per signal (each with its own GND), e.g. CAT6. **C:** the real headset-cord type, if known `[gap]` |
| Cable H | **Repurposed 1 m passive HDMI cable**, see §3.1. The practical choice for cable B |
| Series R | 33 Ω footprints at **each driver**: BCLK + FSYNC + SDI at the codec end, SDO at the Pi end. Fit 0 Ω or 33 Ω per run |
| Scope | ≥ 500 MHz bandwidth, spring ground tips. Probe at the **receiving** pin, not the driver |

**Caution on the EVB I²C:** `[repo]` its control port goes through an on-board PCA9517 to a 3.3 V
side. Cable on that side tests a 3.3 V bus, not the cup board's 1.8 V bus. Run the I²C tests mainly
against the breakouts at 1.8 V, and treat the EVB control port as a secondary target.

### 3.1 Repurposed HDMI cable (added 2026-10-19, per Peter)

A standard HDMI type A cable has **four individually shielded twisted pairs** (the TMDS lanes), plus
a separate **DDC I²C pair** (SCL/SDA) with its own ground. That matches the four I2S signals plus I²C
exactly. Two HDMI-to-screw-terminal breakout boards make it a bench cable.

| HDMI pin | Normal use | PoC use |
|---|---|---|
| 1 / 2 / 3 | TMDS D2+ / D2 shield / D2− | **BCLK** / GND / GND (return) |
| 4 / 5 / 6 | TMDS D1+ / D1 shield / D1− | **FSYNC** / GND / GND |
| 7 / 8 / 9 | TMDS D0+ / D0 shield / D0− | **SDO** (Pi → codec) / GND / GND |
| 10 / 11 / 12 | TMDS CLK+ / CLK shield / CLK− | **SDI** (codec → Pi) / GND / GND |
| 15 / 16 | DDC SCL / SDA | **SCL / SDA** |
| 17 | DDC/CEC ground | GND (I²C return) |
| 13, 14, 18, 19 | CEC, utility, +5 V, hot-plug | Unused. Leave open; don't power anything through 18 |

Each I2S signal rides one wire of a shielded pair with its twin and the pair's drain as ground, so
every signal gets its own return and shield. The connector shell goes to GND at **one end only**
for the first runs; try both ends as a variable if emissions or crosstalk come up.

Caveats:
- **Passive cables only.** Active or "RedMere" cables have chips in them.
- **Beep out every pin with a meter before use.** `[assumed]` The pinout above is the HDMI type A
  standard, but cheap cables sometimes merge shields or omit pins 13/14. Record what the cable
  actually has.
- **It flatters the result.** Shielded 100 Ω pairs beat most headset cords, so a pass on HDMI is a
  best case for the product cord, not proof of it. The DDC wires are usually *not* twisted or
  shielded, which makes them a fair stand-in for I²C in a cord.
- `[assumed]` The single-ended impedance of one wire of a shielded pair with its twin grounded is
  roughly 50–60 Ω. A 33 Ω series resistor plus a typical CMOS driver's output impedance lands near
  that. Measure overshoot with and without it rather than trusting the estimate.

## 4. I2S test — bit-exact loopback

**The data path.** `[repo]` `linux/adau1860-pi5/TESTING.md`: the ADAU1860 has no direct
serial-in → serial-out route. The only all-digital loop is **serial-in → EQ → serial-out**, with EQ
coefficients loaded as pass-through. Whether that is bit-transparent is `[gap]`. **The 10 cm
baseline in step 1 settles it.** If the baseline isn't bit-exact, the codec is altering data and the
cable test is meaningless. In that case, swap the far end for a plain echo device (an RP2040 PIO
running as I2S slave and echoing RX → TX) and keep everything else the same.

**Pattern.** Use the `send_test_pattern.py` scheme `[repo]`: a magic byte plus a 24-bit sequence
counter in each word, and add a PRBS-31 payload on the other channel. The checker reports slips, lost
frames and bit errors separately. Open `hw:` only, never `plughw:` (`[repo]` `DATA_OVER_I2S.md` §1).

**Procedure:**

| Step | Cable | BCLK | Series R | Run | Purpose |
|---|---|---|---|---|---|
| 1 | 10 cm | 3.072 MHz | 0 Ω | 30 min | **Baseline.** Proves the loop and checker are bit-exact before the cable is blamed |
| 2 | 10 cm | 3.072 MHz | 0 Ω | 1 min | **Positive control.** Checker flips one bit every 10⁶ words in software, and must report exactly that count |
| 3 | 1 m A | 3.072 MHz | 0 Ω | 3 h | Worst cheap case |
| 4 | 1 m A | 3.072 MHz | 33 Ω | 3 h | Does termination matter |
| 5 | 1 m B | 3.072 MHz | best of 3/4 | 3 h | Cable construction |
| 6 | best | 6.144 MHz (96 kHz) | best | 3 h | Margin |
| 7 | best | 12.288 MHz (192 kHz stereo) | best | 3 h | TDM8-equivalent clock rate. The SDO round trip in §2 bites here |
| 8 | best | best passing rate | best | 1 h | **Disturbed:** flex the cable continuously, run a switching load (motor/PWM) next to it, I²C stress from §5 running |

Run length: at 3.072 Mbit/s per lane, 3×10¹⁰ bits needs about 2.7 h on one lane `[derived]`. Running
all 4 lanes counts each lane separately, so 3 h per row covers it.

The 12.288 MHz BCLK rows use stereo at a high fs on purpose. `[repo]` RP1 won't lock to the codec's
narrow TDM frame sync (`RESULTS-2026-09-07.md`), so TDM8 itself can't be tested on this host. 192 kHz
stereo puts the same edge rate on the wire.

**Scope captures to keep for each row:** BCLK and SDO at the receiving pin (overshoot, undershoot,
any ledge or reversal between V_IL and V_IH), and SDO-to-BCLK setup time at the codec end measured
with persistence over at least 10 s.

## 5. I²C test

| Step | Speed | Pull-up (at the host end) | Concurrent I2S | Run |
|---|---|---|---|---|
| 1 | — | — | — | Measure SDA and SCL capacitance to GND on the cable alone (LCR meter), then with all targets attached |
| 2 | 100 kHz | 10 kΩ (as drawn) | off | 10⁵ cycles. Expected to fail the rise-time limit (§2); check that it really does |
| 3 | 100 kHz | 4.7 kΩ | off | 10⁶ cycles |
| 4 | 400 kHz | 2.2 kΩ | off | 10⁶ cycles |
| 5 | 400 kHz | value from 3/4 | **on, at the highest passing BCLK** | 10⁶ cycles. **Crosstalk test:** a pulled-up-high I²C line is high-impedance, and BCLK edges in the same cable couple into it |
| 6 | 400 kHz | same | on + cable flex | 10⁵ cycles |

**A cycle** = write a pattern to a scratch register, read it back, compare, plus one read of a fixed
ID register. `[assumed]` ID registers are LSM6DSV16BX `WHO_AM_I` 0x0F and MAXM86161 `PART_ID` 0xFF.
Read the datasheets for the expected values before relying on them. The ADAU1860 scratch register
also needs choosing from the HRM `[gap]`: pick one with no side effects.

Log every NACK, mismatch and bus-stuck event with a timestamp so it can be lined up with flex or load
events. **Positive control:** address a non-existent device once per 10⁴ cycles; the log must show
exactly those NACKs.

Scope: SCL and SDA rise time (30–70 %) at the far end against the I²C limit: ≤ 1000 ns at 100 kHz,
≤ 300 ns at 400 kHz. Also record the glitch amplitude on SDA/SCL during step 5.

**If I²C fails and pull-ups can't fix it:** a bus buffer at each end. The PCA9517 (datasheet already
in `docs/datasheets/`) or a P82B96-class long-distance buffer. That's a fallback, not part of the
PoC.

## 6. Near-field emissions sniff (optional, 30 min)

H-field probe plus a spectrum analyser along the cable, at the 3.072 / 12.288 MHz fundamentals and
harmonics, comparing series R 0 Ω vs 33 Ω and cable A vs B. It gives a relative ranking only, and
says nothing absolute about DO-160 Section 21.

## 7. What the result decides

- **Passes at 3.072 MHz with margin, I²C passes at 400 kHz with BCLK running:** raw I2S/I²C over the
  cord is viable at multilane-stereo rates. The next questions are EMI and ESD on the real cord.
- **Passes only with termination and twisted pairs:** viable, but it fixes the cord construction and
  connector pin count (a GND per signal pair).
- **Fails at 12.288 MHz but passes at 3.072 MHz:** the cup board's TDM8 plan (`[repo]`
  `kicad/cup-board/README.md`) can't cross the cord as TDM. It would need multilane stereo, or
  A2B as already planned.
- **I²C fails under concurrent I2S at any pull-up:** the cord can't share them. That means a bus
  buffer, separate shielding, or control over A2B.

## 8. Open questions for Peter before running

1. **Which 1 m link is this?** Cup to base unit or CM5 through the headset cord, or something else?
   It sets the cable for row C and which end is clock master in the product.
2. **Is the PoC meant to evaluate dropping A2B** for this link, or to de-risk a bench or harness
   extension? The pass bar and which BCLK rate counts as "must pass" depend on it.
3. **What hardware is on hand:** a ≥ 500 MHz scope, an LCR meter, LSM6DSV16BX and MAXM86161
   breakouts, and an RP2040 for the fallback echo far end?
