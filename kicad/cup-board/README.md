# Cup board — one schematic for both earcups

**Status:** preliminary, not reviewed. Replaces the separate `cup-a-board` / `cup-b-board`
first passes (commits `891d746`, `7ffb480`): per Peter, 2026-10-16, both cups are now
**identical**, so there is one board, fitted twice.

This departs from John's Rev G per-cup map (`docs/two-adau1860-channel-allocation.md` §2),
where cup A carried the boom-mic uplink on ADC2 and cup B carried the DVNC accelerometer there.
Here the accelerometer moves off the analog inputs onto TDM, which frees ADC2 on *both* cups,
and the boom mic is replaced by a third MEMS mic. `[gap]` Rev G's upstream slot map has not
been updated to match — see open items.

## What's on it

| Ref | Part | Connection |
|---|---|---|
| U1 | ADAU1861 | Codec, 3 ADC + 1 DAC (ruled 2026-09-22) |
| MK1 | IM73A135V01 | Feed-forward ANC mic → AINP0/AINN0, differential |
| MK2 | IM73A135V01 | Feedback (error) ANC mic → AINP1/AINN1, differential |
| MK3 | IM72D128VV01 (PDM) | **Voice pickup, added 2026-10-20, per Peter** — DATA → `DMIC_DATA` → U1 DMIC01/MP1; CLOCK ← `DMIC_CLK` ← U1 DMIC_CLK/MP0; VDD on 1V8; LR → GND. Replaces the analog IM73A135 MK3 removed earlier the same day (ADC2 now carries the aircraft audio, below). See "Voice mic" |
| C11 | 1 µF | MK3 VDD bypass (IM72D128V datasheet, Table 5 note 3) |
| J5 | 2-pin | **Panel audio in, already isolated** (since 2026-10-20): pin 1 `XF_SEC_A`, pin 2 `XF_SEC_B`, the secondary pair of this cup's SP-74 on the audio board (T2 left / T3 right, its J6 / J7). Was `AC_AUDIO`/`AC_GND` straight from the aircraft |
| ~~T1~~ | Triad SP-74 | **Moved to the audio board 2026-10-20, per Peter** (one per cup: T2 left, T3 right, on its AIRCRAFT AUDIO I/O sheet). Below, "T1" means this cup's SP-74 there. Was: | 80 Ω : 32 Ω (series) / 8 Ω (parallel), 3.143:1:1, no centre tap. Primary 1–2 across J5; secondaries 3–4 and 5–6 **in parallel** → `XF_SEC_A`/`XF_SEC_B` (symbol is `Device:Transformer_1P_2S`, numbered as Triad's; swap done 2026-10-20) |
| U4, U5 | Panasonic AQW612S ×2 | Solid-state speaker switch, one per speaker leg (replaced relay K1, 2026-10-20, per Peter). **Unpowered (N.C., pins 7–8 closed): speaker ← T1 secondary. Driven (N.O., pins 5–6 closed): speaker ← HPOUTN/HPOUTP.** See "Speaker switch" |
| R7, R8 | 330 Ω ×2 | LED current limit for U4/U5, from `SW_DRV` |
| C9/C10, R4/R5, R6 | 1 µF ×2, 10 kΩ ×2, 22 kΩ | ADC2 tap off the T1 secondary → `ADC2_P`/`ADC2_N` = AINP2/AINN2 |
| J6 | 2-pin | Speaker-switch drive in: `SW_DRV` (5 V `[assumed]`), GND — driven from upstream (see below). Was `RLY_COIL`; D1 (coil flyback) removed with K1 |
| U2 | LSM6DSV16BX | DVNC reference, TDM slave into U1's SPT1 (`TDM_DATA`/`TDM_BCLK`/`TDM_WCLK`); I²C host mode for config |
| U3 | MAXM86161 | In-ear optical HR/SpO₂ module (added 2026-10-19, per Peter) — I²C on the shared bus, own LED supply |
| J2 | 2-pin | Earcup driver, 32 Ω: `SPKR_1`/`SPKR_2` from the U4/U5 switch commons (was HPOUTN/HPOUTP direct) |
| ~~J3~~ | — | Removed 2026-10-23: power now from the A2B bus (see "A2B sub-node") |
| ~~J4~~ | — | Removed 2026-10-23: VLED from U9 |
| R1/R2 | 10 kΩ | I²C pull-ups to 1V8 (LSM6DSV16BX datasheet value) |
| R3 | 10 kΩ | U3 INTB pull-up to 1V8 (INTB is open-drain) |
| C1–C3 | 100 nF, 100 nF, 10 µF | U1 1V8 decoupling |
| C4/C5 | 100 nF ×2 | U2 VDD_IO / VDD decoupling (datasheet §7) |
| C6 | 10 µF | U3 VLED bypass (datasheet pin table) |
| C7/C8 | 1 µF ×2 | U3 VLDO and VREF bypass (datasheet pin table) |

### MAXM86161 (U3) — how it's wired and why

`[fetched]` from ADI's MAXM86161 datasheet: 14-pin OLGA 2.9 × 4.3 × 1.4 mm; VLED 3.0–5.5 V;
VLDO (internal 1.8 V LDO output) and VREF (1.21 V) are outputs needing only a 1 µF bypass each;
LED drive full-scale up to 124 mA; I²C address fixed at 0x62; INTB open-drain; GPIO open-drain
or sync input; pins 6/7/8 are internally tied to the LED cathodes and must be left unconnected
(solder only).

- **VLED has its own rail and connector (J4), deliberately not the 3V3_MIC rail.** 3.3 V would
  just meet the 3.0 V minimum, but the LED driver pulses up to 124 mA, and putting that on the
  bias supply of all three ANC/voice mics would inject LED-rate noise into the audio path.
- **I²C shares SDA/SCL with U1 and U2, no address clash:** U3 0x62 `[fetched]`, U1 0x64
  (`1100 1 ADDR1 ADDR0` with both straps low — `[repo]` `linux/adau1860-pi5/REGISTER_CONFIG.md`,
  Table 22), U2 0x6A with SA0 low `[assumed — ST's standard LSM6 address; not re-read from the
  LSM6DSV16BX datasheet]`. The existing 10 kΩ pull-ups (R1/R2) serve all three.
- **LDO_EN tied to 1V8** — the module is always on whenever both rails are up. Shutdown is still
  available by register.
- **INTB → `PPG_INT`**, pulled up by R3, brought out as a label for whatever host reads the sensor.
- **GPIO no-connect** (power-on default is tristate).

Because all three mic inputs are now differential, U1's `CM` pin is unused and no-connected
(it was only needed to bias the single-ended boom input in the old cup A).

U1 strap pins as on `audio-board`: ADDR0/ADDR1/SELFBOOT/ROM_BOOT_MODE/REG_EN low, PD high.
U2: CS high (I²C), SA0 low, Qvar electrodes to GND, INT1/INT2 no-connect.
SPT0 (`I2S0_*`) is brought out as labels only, reserved for the A2B subnode link.

## 2026-10-26 — brought in line with the redone audio board, per Peter

Three changes, each checked: netlist == `doc/design_nets.py`, ERC 0 errors (6 strap warnings, unchanged) `[measured]`.

1. **U1 DVDD overvoltage fixed.** Pin 54 (DVDD) had been on 1V8 against a **1.21 V absolute maximum**, with pin 28
   REG_EN grounded `[fetched]` ADAU1861 DS (DVDD 0.85–1.21 V; abs max −0.3 to +1.21 V). Now, per the DS pin table:
   **REG_EN → AVDD (1V8)** so the internal regulator makes DVDD; DVDD on its own net `U1_DVDD` with **C47 1 µF + C48
   100 nF** to ground (*"decouple DVDD to DGND with a 1 uF and 0.1 μF capacitor"*); `#FLG10` PWR_FLAG marks the rail
   as internally driven. Commit `f502399`.
2. **Connectors match the audio board, JST GH 1.25 mm.** J5 is gone. **J7 (4-pin, SM04B):** 1 `A_LINE_P`,
   2 `A_LINE_N`, 3 `XF_SEC_A`, 4 `XF_SEC_B` — the same order as the audio board's J3 (A2B+, A2B−, speaker pair), so a
   straight 1:1 GH cable joins audio J3 → cup L J7. **J8 (2-pin, SM02B):** A2B out to the next cup. **J2 (2-pin, SM02B):**
   speaker driver. **Cup R needs a split harness into its J7:** pins 1–2 from cup L's J8, pins 3–4 from the audio
   board's J4 — the cost of one board for both cups. (Alternative if that harness is unwelcome: a 6-pin chain that
   carries cup R's speaker pair through cup L — changes the audio board's J3/J4 too. Not done.)
3. **`PPG_INT` → U6 IRQ/IO0 (pin 6).** `[fetched]` AD242x DS Table 15: in slave mode, when not used for mailbox
   interrupts, IRQ/IO0 *"serves as a general-purpose I/O pin with interrupt request input capability"*. MAXM86161 INTB
   is open-drain, pulled up to 1V8 by R3; U6 IOVDD is 1V8, so levels match. Software: configure IO0 as an input with
   falling-edge interrupt; the CM5 already polls `A2B_INTSTAT` (audio-board ruling 11). Not yet checked against the TRM
   register list.

## A2B sub-node — 2026-10-23, per Peter

Peter: *"lets try io7 and add a2b to the cup board"*. The cup is now a **bus-powered AD2428 sub-node** (U6): no power wires
in the cup cable, so everything on the board runs from the A2B bias. Intended connectivity is `doc/design_nets.py` —
the netlist at `b641179` plus these edits — and `python3 -I doc/design_nets.py check <netlist.xml>` diffs it against
the kicad-cli netlist. **Result: OK** (every pre-existing net unchanged, every new net complete) `[measured]`.
ERC 0 errors; 6 warnings, all strap pins tied to rails (the 4 old ones plus U6 ADR1/ADR2). The two single-pin
`I2S0_*` warnings are gone — U6 terminates them.

| Block | Parts | Source |
|---|---|---|
| A side (upstream, J7) | FB1/FB2→ACM (+C12 330 nF), C13 12 pF, L1/L2 180 nH, C14/C15 27 pF, FL1 CMC, R9/R10 120R + C16/C17 33 nF, C18/C19 10 nF series, C20/C21 33 nF, C22 470 nF across | EVAL-AD2428WD1BZ sheet 2, A side, read from a rendered image `[fetched]` |
| Bus power in | L3 (line+ → V_NODE), L4 (line− → GND), D1 ZLLS400 → VIN_CUP, C23/C24 | AD242x DS Fig. 36 (bus-powered sub-node) `[fetched]` |
| B side (downstream, J8) | Q1 AO3401A switched by SWP (R11–R14, C25/C26), L5/L6, same coupling as the audio board's main node | DS Fig. 36 + eval B side |
| U6 | I²S master: DTX0 → `I2S0_SDATAI`, DRX0 ← `I2S0_SDATAO`, BCLK/SYNC → `I2S0_BCLK`/`I2S0_FSYNC`; I²C master on SDA/SCL; IOVDD on 1V8; VOUT1/VOUT2 decoupled | AD242x TRM |
| K2 drive | U6 IO7 → R17 2.2k → Q2 MMBT3904 (R18 100k pull-down) switches U4/U5 LED returns; R7/R8 **680R** from VIN_CUP (220R until the 8 V bus) | audio-board rulings 11, 12 |
| Power | U7 TPS62161 → 1V8, U8 ADP7118-3.3 → 3V3_MIC, U9 ADP7118-3.3 → VLED (separate, as before, to keep PPG pulses off the mic rail) | TPS6216x DS, ADP7118 |

**Removed:** J3 (1V8/3V3_MIC in), J4 (VLED in), J6 (`SW_DRV` in), and the PWR_FLAGs on 3V3_MIC/VLED (the LDOs drive
them now). **Why a BJT for K2:** U6's IO is 1.8 V, too low to turn a 2N7002 on reliably. **Why 680R:** with the AeroNode's 8 V bus (ruling 12) VIN_CUP is 6.4–7.2 V, giving 5.1–7.2 mA per string
(220R would have pushed ~20 mA and wasted ~0.27 W per cup).

**Ground rule `[fetched]` EE-419:** *"the ground of a bus-powered node is not at the same potential as the ground of a
locally-powered node ... only floating signals ... should be connected."* J5 (SP-74 secondary) is transformer-isolated
and reaches U1 only through C9/C10; the speaker reaches it only through K2. The IO7 route also avoided a wired K2 drive
that would have DC-tied the grounds.

### Open — A2B sub-node

- ~~**VIN_CUP margin at low battery.**~~ **Closed 2026-10-23:** `docs/a2b-bus-power-budget.md` → 8 V boost on the audio
  board (ruling 12); cup R VIN 6.44 V worst case.
- **Cup power budget not run** (U1's HiFi 3z, three mics, LSM6, MAXM86161 LED pulses) against the main node's 300 mA
  VSSN limit for both cups.
- **Sub-node IO7 state on data-link loss with bus power still up** — not in the TRM section read.
- **Cup R speaker pair** still arrives on its own J5 from the audio board's J4; A2B comes from cup L's J8.
- ~~**Still unfixed, needs Peter's go-ahead:** U1 DVDD (pin 54) on 1V8 against a 1.21 V abs max (REG_EN low).~~
  **Fixed 2026-10-26** (internal regulator, see above).

## Aircraft audio in — 2026-10-20, per Peter

Peter ruled: aircraft audio goes into **ADC2 on each cup** (MK3 dropped), the speaker is
**32 Ω**, and the cup must **still be heard unpowered** (fail-passive). Peter proposed the
SP-74 for the bypass path.

```
   audio board                    cable    cup board
 Ring ──┐                 ┌─ J6/J7 ─────── J5 XF_SEC_A ──┬── U4/U5 N.C. ─┐
        SP-74 (pri)   SP-74 (2 sec ∥)                   │               ├─ SPKR_1/2 ── J2 speaker 32 Ω
 Sleeve ┘  T2 / T3        └─ J6/J7 ─────── J5 XF_SEC_B ──┼── U4/U5 N.C. ─┘   U4/U5 N.O. ── HPOUTN / HPOUTP
                                             └── C9/R4, C10/R5, R6 ── AINP2 / AINN2
```

- **Unpowered, or `SW_DRV` dropped:** U4/U5's N.C. switches are closed and T1 drives the speaker. `[derived]` With
  the full primary and the two secondaries in parallel, the turns ratio is 3.143:1, so the
  impedance ratio is 9.88:1 and a 32 Ω speaker looks like **≈ 316 Ω** to the panel. Two cups
  on a mono panel come to ≈ 158 Ω, which is inside the ≥ 150 Ω the panel is rated for.
  `[fetched]` The Garmin GMA 340 is specified at 100 mW per channel into 150 Ω. Against the
  120 Ω series resistor considered first, the transformer is ≈ 3.6 dB louder at the same panel
  voltage and halves the panel loading. Triad's own rating is 80 Ω : **32 Ω with the secondaries
  in series**, or 8 Ω in parallel. We deliberately use the parallel connection with a 32 Ω load,
  so the panel sees 316 Ω and not 80 Ω.
  **Correction, 2026-10-21:** the SP-74 has **no primary centre tap.** DigiKey's "80 CT"
  description is wrong, and Triad's drawing shows pins 1–2 only. My 2026-10-20 note that "the
  centre tap would give 79 Ω" was built on that listing and is withdrawn. The conclusion stands,
  because the full primary was the connection used anyway.

### SP-74 pinout — `[fetched]` Triad datasheet, publish date 2024-05-30 (`docs/datasheets/Triad_SP-74.pdf`)

| Pin | Winding | Dot | Net here |
|---|---|---|---|
| 1 | Primary, 80 Ω, 12.5 Ω DCR | ● | `RX_RING` (audio board; was `AC_AUDIO` here) |
| 2 | Primary | | `AC_GND` (audio board) |
| 3 | Secondary 1 | ● | `XF_SEC_A` |
| 4 | Secondary 1 | | `XF_SEC_B` |
| 5 | Secondary 2 | ● | `XF_SEC_A` |
| 6 | Secondary 2 | | `XF_SEC_B` |

- **Parallel (8 Ω, this design):** 3∥5 and 4∥6, dot to dot. **Series (32 Ω):** link 4–5 and
  take the output across 3–6.
- **Package:** six gold-plated 0.020″ pins, with a tab at pin 1. The body is
  0.410 × 0.310 × 0.465″ max and the leads are 0.750″ min.
  `[derived]` **Two rows of three: 1-3-5 and 2-4-6, with 2 opposite 1, 4 opposite 3 and 6
  opposite 5.** Pitch is 0.100″ along each row and the rows are 0.300″ apart. The face marked PRI
  reads 1 3 5 and the opposite face, marked SEC, reads 6 4 2; seen from the same side that reverses
  to 2 4 6. The plan view's .100/.200/.300 dimensions agree. **So it is a DIP-6 grid, but not
  DIP-6 numbering** (DIP runs 1-2-3 / 6-5-4). A stock DIP-6 footprint would put the wrong pins
  on the primary, so draw a custom one. `[gap]` The plan view itself is an embedded low-resolution
  bitmap and stays unreadable even at 600 dpi. Check one physical part before releasing the
  footprint.
- **Max DC unbalance in the primary: 3.0 mA.** `[derived]` Across 12.5 Ω that is only 37 mV. If
  a panel's earphone output carries any DC offset, it could exceed that and push the core toward
  saturation. `[gap]` Whether panel outputs are capacitor-coupled isn't established. A series
  blocking capacitor on the primary would remove the question.
- Rated 50 mW, ±2 dB from 300 Hz to 100 kHz, 1000 V rms hipot, 150 V DC working voltage,
  −40 to +85 °C, MIL-T-27E "Red Spec".
- **Powered, `SW_DRV` on:** the speaker moves to HPOUTN/HPOUTP and T1's secondary is left
  driving only the ADC tap. That tap is galvanically isolated from the aircraft, so it breaks the
  aircraft-ground loop, and the 1861 datasheet gives no CMRR figure to lean on otherwise.
  `[derived]` The tap loads the secondary with ≈ 34 kΩ, which reflects to ≈ 330 kΩ on the
  primary, so it bridges the line.
- **Level.** The secondary is the line voltage ÷ 3.143. `[fetched]` R6 sits in parallel with the
  1861's 36 kΩ differential line input (Table 1, no PGA), so the divider is 13.65 / 33.65 = 0.41.
  The aircraft line reaches **0 dBFS (0.98 V rms) at ≈ 7.6 V rms**, and 3.9 V rms (100 mW into
  150 Ω) lands at about −6 dBFS. If the PGA is enabled, the input resistance changes and so does
  this gain. C9/C10 give a corner near 10 Hz; T1's 300 Hz is the corner that actually limits.
- **The switch drive (`SW_DRV`) comes in on J6 from upstream.** It is applied only while the
  digital path is healthy, so losing power, the cable, or the host drops the cup into bypass.
  That is the fail-passive property.

### Speaker switch: AQW612S pair (U4/U5), 2026-10-20, per Peter

Relay K1 is replaced by two Panasonic AQW612S PhotoMOS parts, one per speaker leg, keeping K1's
pairing: U4 switches `SPKR_1` between `XF_SEC_A` (N.C.) and `HPOUTN` (N.O.); U5 switches `SPKR_2`
between `XF_SEC_B` (N.C.) and `HPOUTP` (N.O.). Source: `[fetched]` Panasonic catalogue ASCTB137E
202601, `docs/datasheets/Panasonic_AQW61xS_GU-SOP8-1a1b.pdf` (pinned in
`scripts/fetch-datasheets.sh`). The symbol `Panasonic:AQW612S` (`kicad/lib/Panasonic.kicad_sym`)
was drawn from the datasheet's p. 6 schematic: LED 1–2 (anode 1) drives N.C. 7–8, and LED 3–4
(anode 3) drives N.O. 5–6.

- **Fail-passive by construction:** the N.C. switch's on-resistance is specified at IF = 0 mA. It
  is closed with no power at all, like K1's NC contacts. Both legs are switched, so the
  transformer is never connected to an unpowered U1.
- **Drive:** each part's two LEDs are in series (pins 2–3 linked, the datasheet's "1 Form A &
  1 Form B use"), one string per part, from `SW_DRV` through 330 Ω. `[derived]` Assuming
  `SW_DRV` is 5 V ± 5 %, with V_F ≈ 1.14 V typ at 5 mA (and ≤ 1.5 V): ≈ 8.2 mA typical, ≥ 5.3 mA
  worst case, inside Panasonic's recommended 5–30 mA and well above the 3 mA maximum operate
  current. **J6 must be able to source ≈ 16.5 mA (≈ 20 mA worst case).**
- **On-resistance:** 1 Ω typ, 2.5 Ω max per switch, so 2 Ω typ / 5 Ω max in series with the 32 Ω
  speaker. That is ≈ 0.5 dB loss typical, ≈ 1.3 dB worst case, in both modes. K1's contacts were
  ≈ 0.1 Ω.
- **Ratings:** 60 V abs max (48 V recommended), 0.45 A, 1 µA off-state leakage, −40 to +85 °C.
  Our signals peak below 2 V.
- **Timing:** on power-up, N.O. closes in ≈ 0.65 ms while N.C. takes up to 3 ms to open, so for a
  few ms HPOUT can be connected to the T1 secondary. **Firmware must keep U1's headphone output
  muted for ≥ 5 ms after `SW_DRV` comes up.** On power loss, N.O. opens in 0.08 ms and N.C. closes
  in 0.2–1 ms: a sub-ms gap, no overlap.

### Open — speaker switch

- `[gap]` **Distortion is not specified.** Panasonic calls the part suitable for low-level analog
  signals but gives no THD figure. The powered ANC path runs through two of these switches, so
  measure THD and ANC performance on the bench.
- **Drive power is ≈ 82 mW per cup, not a large saving.** `[derived]` 2 × 8.2 mA from 5 V,
  against K1's 100 mW. (An earlier estimate of ≈ 50 mW assumed exactly 5 mA, with no tolerance
  margin.) The gains are no contacts, no click, no wear and a smaller footprint, not power.
- **"Not for automotive use"** per the datasheet. The ADAU1861 is AEC-Q100; this part is not.
  Relevant to any qualification effort.
- **No footprint assigned.** This matches the rest of the sheet. The package is SOP8 at 2.54 mm
  pitch (4.4 × 9.37 mm), not a standard SOIC.

### Open — introduced by this change

- ~~**T1's symbol is wrong and must be swapped before layout.**~~ **Done 2026-10-20.** T1 was
  KiCad's `Device:Transformer_SP_2S` (7 pins, with a centre tap the SP-74 doesn't have, and pin
  numbers that didn't match the part). It is now `Device:Transformer_1P_2S`, whose 1–2 / 3–4 / 5–6
  numbering matches Triad's, wired per the pinout table above. `[measured]` kicad-cli netlist:
  `AC_AUDIO` = J5.1, T1.1; `AC_GND` = J5.2, T1.2; `XF_SEC_A` = C9.1, K1.2, T1.3, T1.5;
  `XF_SEC_B` = C10.1, K1.7, T1.4, T1.6. ERC: 0 errors and the same 8 pre-existing warnings.
  No shorted nets, no overlaps.
- **SP-74 core level.** `[fetched]` DigiKey: 50 mW, 300 Hz–100 kHz ±2 dB, 1000 V isolation,
  −40 to +85 °C, THT 10.4 × 7.9 mm, $19.48, **24-week lead time**. 50 mW at its 80 Ω rating is
  ≈ 2 V rms. `[assumed]` 3.9 V rms at 300 Hz is about twice the rated flux, so expect distortion
  at full panel volume. This needs a bench measurement.
- **Everything goes through T1, so the digital path is band-limited too:** ≥ 300 Hz in normal
  use. That's fine for comms and alerts, but music input would lose its bass.
- ~~**The coil costs 100 mW per cup.**~~ K1 replaced by U4/U5 (see "Speaker switch"). Their LED
  drive is ≈ 82 mW per cup, still more than the rest of the cup in normal use.
- **What drives J6 (`SW_DRV`) is undecided.** Likely candidates are the A2B subnode's GPIO through a
  low-side switch, or the audio board.
- **The unpowered ADC sees signal.** In bypass, ≈ 1.2 V rms is applied through 10 kΩ into an
  unpowered U1. `[assumed]` The ESD-diode current is about 0.1 mA, which should be harmless.
  Not checked against an abs-max input-current figure.
- ~~**Voice pickup is gone from the cups.**~~ **Restored 2026-10-20:** MK3 is now a PDM mic
  (IM72D128V) on U1's DMIC input, which leaves ADC2 for the aircraft audio. See "Voice mic" below.
- **DSP:** ADC2 → DAC mixing, and the feedback-ANC loop must treat ADC2 content as wanted
  signal and not cancel it. Firmware, not on this sheet.

## Voice mic (MK3, PDM) — 2026-10-20, per Peter

Peter asked for one IM72D128V for voice pickup. It uses U1's digital-mic port, which was
otherwise unused, so the three analog inputs are unchanged: ADC0/ADC1 for the ANC mics and ADC2
for the aircraft audio. Wiring copies the audio board's IM72D128V (commit `4f1c7a8`), with the
same net names.

- `[fetched]` IM72D128V datasheet v01.00, Table 9: 1 DATA, 2 VDD, 3 CLOCK, 4 LR, 5 GND. That
  matches `kicad/lib/Infineon.kicad_sym`. The library is now registered in this project's
  `sym-lib-table`.
- **VDD on 1V8**, inside the mic's 1.62–3.6 V range. U1's IOVDD is also 1V8, so the PDM logic
  levels match with no shifter. C11 (1 µF) is the bypass the datasheet asks for at the VDD pad.
- **LR → GND** `[fetched]` (Table 8) makes the mic DATA1: data driven on the falling clock edge,
  high-Z on the rising edge. This was a free choice on the audio board too. `[gap]` Which of
  U1's DMIC channel numbers that edge maps to has to be confirmed when the DSP is configured.
- **DMIC23/MP2 keeps its no-connect.** DMIC01 has room for a second mic (LR → 1V8) if one is
  ever wanted.
- **Clock: run DMIC_CLK at 3.072 MHz.** `[fetched]` The mic's high-performance mode is
  2.9–3.4 MHz, so U1's other DMIC rate, 6.144 MHz (ADAU1861 Figures 41–45), is out of its range.
- **Headroom** `[repo]` (`docs/mic-comparison-im73-vs-im72.md`): the IM72D128V's AOP is
  128 dBSPL, so in a loud cockpit the mic clips before the codec does. Worth checking against
  in-cup levels.
- **Cosmetic:** the library symbol anchors its Reference and Value text on the GND and VDD pin
  ends, so "MK3" and "IM72D128VV01" overlap those stubs on the drawing. Konnect has no tool to
  move individual field text. A fix belongs in the library symbol, and it would also change the
  audio board.

## How it was drawn, and why differently from the earlier two

I²C and TDM are joined by **net labels at each end**, not long wires. On `cup-b-board` the
long-haul routes kept causing trouble — wires through symbol bodies, and one real short when two
bend heights snapped to the same 1.27 mm grid line. Labels remove that whole failure class.
The remaining direct wires (mics → U1, U1 → J2) use grid-exact lane coordinates.

## Verification

- ERC: **0 errors**, 8 warnings — the same benign set as before (strap pins tied to a power
  net; single-pin `I2S0_*` labels held open for A2B).
- `find_shorted_nets`: 0.
- Because that check only compares *labeled* nets, every unnamed net was also checked in the
  `kicad-cli` netlist: each is exactly two pins — MKn OUT+ → AINPn, MKn OUT− → AINNn (n = 0,1,2),
  J2.1 → HPOUTN, J2.2 → HPOUTP.
- After adding U3, re-checked the same way: VLED = J4.1, C6.1, U3.5 only; PPG_VLDO = C7.1, U3.4;
  PPG_VREF = C8.1, U3.12; PPG_INT = R3.2, U3.14; SDA/SCL each = U1, U2, U3 + one pull-up;
  U3 pins 6/7/8 and GPIO unconnected. ERC still 0 errors, same 8 warnings.
- After adding MK3 (2026-10-20) `[measured]`: kicad-cli netlist `DMIC_DATA` = MK3.1, U1.1;
  `DMIC_CLK` = MK3.3, U1.7; MK3.2 and C11.1 on 1V8; MK3.4, MK3.5 and C11.2 on GND; U1.8
  unconnected. Compared with the netlist before MK3, those are the only changes. ERC 0 errors,
  same 8 warnings; `find_shorted_nets` 0; overlaps 0.
- After swapping K1 for U4/U5 (2026-10-20) `[measured]`: compared with the netlist before, the
  only changes are K1/D1 removed, `RLY_COIL` renamed `SW_DRV` (J6.1, R7.1, R8.1), and
  `SPKR_1` = U4.6, U4.8; `XF_SEC_A` = U4.7; `HPOUTN` = U4.5; `SPKR_2` = U5.6, U5.8;
  `XF_SEC_B` = U5.7; `HPOUTP` = U5.5; U4.4 and U5.4 on GND; R7.2–U4.1, U4.2–U4.3, R8.2–U5.1 and
  U5.2–U5.3 each a two-pin net. ERC 0 errors, same 8 warnings; `find_shorted_nets` 0; overlaps 0.
  Checked visually in a render.
- After moving T1 to the audio board (2026-10-20) `[measured]`: compared with the netlist before,
  the only changes are T1 removed, `AC_AUDIO`/`AC_GND` gone, and J5.1 → `XF_SEC_A` (with C9.1,
  U4.7), J5.2 → `XF_SEC_B` (with C10.1, U5.7). ERC 0 errors, same 8 warnings;
  `find_shorted_nets` 0; overlaps 0. The audio-board side is described in the note on its
  AIRCRAFT AUDIO I/O sheet.

## Power budget (estimate, per cup) — 2026-10-19

Datasheet typicals only, `[fetched]` unless marked. Nothing measured. Excludes the speaker's
output power (signal-dependent) and the A2B subnode, which isn't on this sheet yet.

| Part | Rail | Current | Power | Basis |
|---|---|---|---|---|
| U1 ADAU1861, ANC config | 1V8 | 6.4 mA (HP amp idle) – 11.3 mA (HP amp on, no load) | 11.5 – 20.3 mW | Table 7, "High performance, normal voltage": 3 ADCs + DAC + FastDSP @192 kHz, HiFi 3z bypassed. AVDD 3.04 / 7.87 mA + DVDD 3.06 mA + IOVDD 0.32 mA. `[assumed]` DVDD current is drawn from the 1V8 rail by the internal regulator — the datasheet doesn't name the regulator's input |
| U2 LSM6DSV16BX | 1V8 | 0.60 (accel + TDM) – 0.95 mA (+ gyro) | 1.1 – 1.7 mW | Table 4, LA_IddHPT / IddHPT |
| MK1–MK3 IM73A135 ×3 | mic rail, 2.75 V | 0.51 mA typ, 0.69 mA max | 1.4 – 1.9 mW | Table 7: 170 µA typ / 230 µA max each, normal mode. **2026-10-20: MK3 removed, now ×2 (≈ 0.34–0.46 mA); K1 coil adds 100 mW (since replaced by U4/U5 LED drive, ≈ 82 mW) — budget below not yet re-run** |
| MK3 IM72D128V (PDM voice), added 2026-10-20 | 1V8 | 0.43 mA typ, 0.525 mA max | 0.77 – 0.95 mW | Table 6, Fclock = 3.072 MHz. **Not yet in the totals below** |
| U3 MAXM86161 LEDs + readout | VLED, 5 V `[assumed]` | 0.4 – 1.3 mA | 2.0 – 6.5 mW | Table: VLED = 5 V, 117 µs pulses, 100 sps; 0.4–0.6 mA at zero LED drive up to 1.3 mA with 3 LEDs at full scale. SpO₂ (red + IR, 2 LEDs, full scale) ≈ 0.97 mA |
| R1–R3 pull-ups | 1V8 | ≈ 0 average | ≈ 0 | 0.18 mA each only while a line is held low |
| **Total, per cup** | | **1V8 ≈ 7–12 mA · mic ≈ 0.5–0.7 mA · VLED ≈ 0.4–1.3 mA** | **≈ 16 – 30 mW** | |
| **Total, two cups** | | | **≈ 32 – 61 mW** | |

Upstream losses aren't included. If 1V8 and the mic rail are linear regulators from a ~3.7 V
cell and VLED is taken straight from the cell (inside the 3.0–5.5 V range, but see the VLED open
item) `[assumed]`, the cell current is the sum of the rail currents, ≈ 8–14 mA per cup ≈ 30–53 mW
per cup at the cell. The real totals will be set by three things not budgeted here: the A2B
subnode, earphone output power (ANC anti-noise included), and whether the HiFi 3z core runs.

### With a 32 Ω over-ear speaker

`[fetched]` ADAU1861 Table 1: the headphone driver delivers **30 mW into 32 Ω** (50 mW into 16 Ω)
at <0.1 % THD+N from 1.8 V. Table 7 — which is itself measured into 32 Ω — suggests the amp's
quiescent draw is about 4.8 mA (AVDD 7.87 mA with the HP amp on vs 3.04 mA off), so the "HP amp on"
figure above is the right base. `[derived]` On top of that, a differential class-AB stage draws the
rectified average of the load current: for a sine, I = (2/π)·√(2·P/R), taken from the 1V8 rail.

| Speaker output (32 Ω) | Extra 1V8 current | Extra supply power | Per cup | Two cups |
|---|---|---|---|---|
| 0.1 mW | 1.6 mA | 3 mW | ≈ 28 – 33 mW | ≈ 55 – 67 mW |
| 1 mW | 5.0 mA | 9 mW | ≈ 34 – 40 mW | ≈ 68 – 79 mW |
| 10 mW | 15.9 mA | 29 mW | ≈ 53 – 59 mW | ≈ 107 – 118 mW |
| 30 mW (datasheet maximum) | 27.6 mA | 50 mW | ≈ 74 – 80 mW | ≈ 149 – 160 mW |

"Per cup" = the fixed load with the HP amp on (≈ 25–30 mW: 1V8 ≈ 11.9–12.2 mA, mics, VLED)
plus the speaker column. A 16 Ω speaker would draw ≈ 1.4× the current for the same electrical
power (7.1 mA vs 5.0 mA at 1 mW).

Which row applies depends on speaker sensitivity, which isn't established. `[assumed]` A typical
32 Ω over-ear driver of ~95–100 dB SPL/mW needs ≈ 0.1–0.3 mW for 90 dB SPL and ≈ 1–3 mW for
100 dB SPL at the ear, so speech plus ANC anti-noise most likely sits around the 0.1–1 mW rows,
occasionally a few mW. The maximum row sets the supply: **the 1V8 rail must deliver ≈ 40 mA per
cup** (≈ 80 mA for two) at full scale.

### Whole H1 headset: two cup boards + two 32 Ω speakers

| Speaker level (each) | 1V8 rail | Mic rail (2.75 V) | VLED (5 V) | Load power |
|---|---|---|---|---|
| 0.1 mW | 27 – 28 mA | 1.0 – 1.4 mA | 0.8 – 2.6 mA | ≈ 55 – 67 mW |
| 1 mW (expected normal use) | 34 – 35 mA | 1.0 – 1.4 mA | 0.8 – 2.6 mA | ≈ 68 – 79 mW |
| 10 mW | 56 mA | 1.0 – 1.4 mA | 0.8 – 2.6 mA | ≈ 107 – 118 mW |
| 30 mW (amp maximum) | 79 – 80 mA | 1.0 – 1.4 mA | 0.8 – 2.6 mA | ≈ 149 – 160 mW |

**What the source sees depends on the regulators, and the choice roughly triples the draw.**
`[assumed]` If the headset is fed from AeroNode's VBAT (`[repo]` 2S LiFePO4, 5.0–7.3 V, ≈ 6.4 V
nominal) through linear regulators, as `audio-board` does today, every rail current is drawn at
≈ 6.4 V: ≈ 36–39 mA ≈ **230–250 mW in normal use** (≈ 520–530 mW at full volume), about two thirds
of it lost as heat in the regulators. A buck converter to 1V8 at ≈ 85 % `[assumed]` would bring
normal use to ≈ 80–95 mW at the source. At ≈ 37 mA linear, each 1000 mAh of 2S pack is ≈ 25 h.

Not included: two A2B subnodes, the audio board, and AeroNode itself.

`[inferred, not stated]` Table 7 implies the amp runs from HPVDD_L in low-voltage mode. HPVDD_L is
tied to 1V8 here; feeding it from a lower rail (allowed range 1.2 V to AVDD) would cut the speaker
term by roughly HPVDD_L/1.8, at the cost of output swing.

## Found while budgeting — two supply errors on this sheet

- **DVDD is tied to 1V8 with REG_EN low. That exceeds the absolute maximum.** `[fetched]` ADAU1861
  Table 10: DVDD abs max is **1.21 V** (operating 0.85–1.21 V, 0.9 V typ). Pin 28: *"Tie to AVDD
  to enable the internal regulator, and tie to ground to disable."* Pin 54: DVDD is either the
  regulator output or an external supply, *"decouple DVDD to DGND with a 1 uF and 0.1 μF
  capacitor."* As drawn the regulator is off and 1.8 V goes straight onto the 0.9 V core. Fix:
  REG_EN → 1V8, DVDD on its own net with 1 µF + 100 nF to GND. **`kicad/audio-board` has the same
  wiring** (U1 pin 54 on 1V8, pin 28 on AGND) — it was copied from there.
- **The mic rail is named `3V3_MIC` but the IM73A135 maximum is 3.0 V** `[fetched]` (Table 6: normal
  mode 2.3 / 2.75 / 3.0 V). `[repo]` The audio-board decision record already says the mic supply is
  2.75 V, so the name is misleading rather than the design. It should be renamed (e.g. `2V75_MIC`)
  so nobody feeds 3.3 V into J3.

## Open items — real gaps, not decisions

- **Rev G slot map needs updating.** With both cups identical, each sends FF, FB and a voice
  mic upstream (6 analog channels across two cups) *plus* IMU data arriving on SPT1. Where the
  accel data goes on A2B, and whether two voice mics are wanted upstream or one is dropped, is
  undecided. The audio board decision record already notes the host sees only 4 of A2B's
  channels.
- **Identical cups share an I²C address.** Fine if each cup sits behind its own A2B subnode's
  I²C (as Rev G implies); a problem if both ever share one bus. Not yet confirmed.
- **SPT1 must master BCLK/WCLK for the IMU** (it is a TDM slave). Register configuration,
  unverified against the ADAU1861 manual.
- **Aircraft-audio items** — see "Aircraft audio in" above: SP-74 polarity dots and core
  saturation, and speaker-switch drive power and who drives `SW_DRV`. (Voice pickup is back on
  the cups via MK3.)
- **VLED voltage is undecided.** The datasheet gives only the 3.0–5.5 V range and says to set it
  for the LEDs' forward voltage plus driver headroom. The green LED is the one most likely to need
  more than 3.3 V; 5 V would be the conservative choice, but nothing here establishes it.
- ~~**`PPG_INT` goes nowhere yet.**~~ **Closed 2026-10-26:** → U6 IRQ/IO0, see above.
- **MAXM86161 power-up sequencing** (VLED vs 1V8 / LDO_EN) wasn't in the extracted datasheet
  text — not checked.
- **Optical placement.** The module has to sit against skin in the ear canal / concha through a
  window; where that is on the cup, and whether both cups need one, isn't established.
- **The MAXM86161 symbol is hand-entered** from the datasheet's pin table into
  `kicad/lib/AnalogDevices.kicad_sym`; worth a second check against a hand-downloaded PDF.
- **No AD2428W A2B subnode, no power-delivery path, no footprints** — unchanged from before.

## Footprints — 2026-10-26, per Peter

**All 99 parts have footprints** (U3 added the same day, below). Checked `[measured]`: netlist == `doc/design_nets.py`,
ERC 0 errors, every symbol pin has a pad in its footprint (read from the .kicad_mod files, not Konnect's read-back).
*Correction:* commit `d93b17f` said "116 of 117" — that was the audio board's part count; the cup board has 99.

| Part | Footprint | Source |
|---|---|---|
| U1 ADAU1861 | `AnalogDevices:AD_LFCSP-SS-64-1EP_9x9mm_P0.5mm_EP6.3x6.3mm_CS-64-2` (new) | DS Rev A p.28 recommended pad layout: 9.50/8.00 SQ, 0.75×0.25 pads, EP 6.30 SQ = pin 65; 3×3 paste, 16 thermal vias |
| MK1/MK2 IM73A135V01, MK3 IM72D128VV01 | `Infineon:Infineon_PG-LLGA-5_4x3mm_IM73A135_IM72D128` (new, shared) | IM73A135 DS v1.20 Fig. 12/13, IM72D128 DS 1.2 Fig. 13/14 — same land pattern and numbering. GND ring = plated 0.8 mm port (Infineon's recommended port) in a 2.08 mm annulus; paste dots stand in for the C-ring stencil. **Port must open to the acoustic path** — enclosure work |
| U2 LSM6DSV16BX | stock `Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y` | matches DS13771 Rev 4 Fig. 31 (LGA-14L 2.5×3.0); DS defers land pattern to ST TN0018 (not read) |
| U4/U5 AQW612S | `Panasonic:Panasonic_GU-SOP8_…` (from the audio board) | Panasonic ASCTB137E |
| U6 AD2428 | stock QFN-32 5×5 EP3.6 | AD242x Rev C CP-32-12 |
| U7 / U8, U9 / Q1, Q2 / D1 | stock WSON-8 2×2 / TSOT-23-5 / SOT-23 / SOD-323 | |
| FL1, FL2 | stock ACM3216 | **same caveat as the audio board: MPN unchosen, winding 1–2/3–4 assumed** |
| L, FB, C, R | 0603 (10/22 µF 0805, R12 1206, 3.3 µH 1210, L9 1008) | packages by value, not chosen parts |
| J2, J7, J8 | JST GH | see 2026-10-26 above |

| U3 MAXM86161 | `AnalogDevices:Maxim_OLGA-14_2.9x4.3mm_P0.6mm_F142A4_MAXM86161` (new) | see below |

**U3 MAXM86161.** The datasheet (19-100523 Rev 1, saved by Peter to ~/Downloads, sha256 `c512ea35…24da`) gives only
the pin order and points to Maxim drawings, fetched 2026-10-26 from `mds.analog.com/api/public/content/` `[fetched]`:
**land pattern 90-100106 rev A** (IPC-7351A) — pads 0.660 × 0.400, pitch 0.600, D1 3.600, columns 1.900 apart;
**outline 21-100309 rev B** — body 2.9 × 4.3 × 1.4, leads L 0.6 × W 0.4, D1 3.6 / E1 1.9 BSC, pin 1 top-left, 1–7 down the
left, 8–14 up the right (top view). Pins 6/7/8 (LED cathodes) are soldered but left unconnected, as the DS requires.
**Optical side faces up:** the module needs a window to the skin, and placement on the cup is still open.

## PCB — outline, stackup, placement (2026-10-26, per Peter)

- **Outline:** ring, **68 mm OD / 38 mm ID**, centre (150, 100). 62/38 was tried first: 57 % courtyard fill on one side,
  too tight; Peter chose 68/38 (single-sided, ~43 %). Fits a 40 mm driver with 1 mm clearance — **adjust to the cup CAD.**
- **Stackup:** 4 layers — F.Cu / In1 (power) / In2 (mixed) / B.Cu. JLC 4-layer rules; Default 0.2/0.127, Power 0.4/0.127.
- **Holes:** H1–H3 M2 on the 26.5 mm mid-radius, as schematic symbols (no board-only footprints to trip the sync).
- **Placement:** `doc/ring_placement.py` packs parts round the ring in signal order, each turned to follow the circle,
  and checks exact courtyard corners against the ring and every pair for overlap (359.9° used — tight). Clockwise from
  upper right: codec U1 · IMU, FB mic (inner edge) and FF mic · K2 PhotoMOS pair · J2 speaker, J7 in · A2B U6 + both bus
  filters · J8 out · power (U7/U8/U9), PPG U3, voice mic MK3. Connector openings face outward. Render:
  `doc/placement-2026-10-26.png`.
- **How it was applied:** schematic sync through Konnect (one KiCad undo step); then positions **and non-90° angles**
  set with KiCad's pcbnew API with KiCad closed (`doc/apply_placement.py`) — Konnect's IPC refuses non-90° rotation of
  footprints with rounded-rect pads. Outline circles likewise (`doc/ring_outline.py`, `doc/ring_resize.py`; Konnect has
  no circular Edge.Cuts tool). Connectors then pulled inward 0.16–0.29 mm so their MP tabs clear the curved edge by
  0.5 mm (`doc/pull_in_connectors.py`). Every step on a committed board; read-back error 0.
- **Checked `[measured]`** with `kicad-cli pcb drc` on the saved file: **0 errors** (250 unconnected = unrouted;
  schematic parity 0). Warnings only: silkscreen overlaps, `lib_footprint_mismatch`, 2 silk-at-edge.
- **Open:** mic/PPG positions vs the enclosure (all on top, ports through the board); routing will be tight (little
  angular slack); "REF\*\*" silk on custom footprints (shared Konnect footprint-writer quirk, fix before fab).

## PCB — 72/38 ring, flex mics, ROUTED (2026-10-27, per Peter)

- **Ring widened to 72 mm OD / 38 mm ID** (Peter, after 68/38 proved over-constrained round U6). **H3 removed** — two
  M2 holes (H1, H2) are enough (Peter); H3 was blocking the top routing corridor.
- **Mics moved off-board onto Infineon's flex evaluation boards** (Peter): KIT_IM73A135V01_FLEX for MK1 (FF) and MK2 (FB),
  KIT_IM72D128V01_FLEX for MK3 (PDM voice). On the cup board each is a 6-pin 0.5 mm ZIF: **J9 (MK1), J10 (MK2), J11 (MK3)**,
  footprint Hirose FH12-6S-0.5SH. **Pinout is a PLACEHOLDER** (Peter: "verify later") — Infineon does not publish the
  flex-tail contact order and its adapter tables differ between 2020 and 2022. Current assignment: J9/J10 1 = 3V3_MIC,
  2 = OUT+, 3 = OUT−, 4 = NC, 5/6/MP = GND; J11 1 = 1V8, 2 = DATA, 3 = CLK, 4/5/6/MP = GND. **Check against a real kit
  (continuity) before fab**; the JLC/LCSC part for the FH12 is not chosen yet.
- **Routed `[measured]`:** `kicad-cli pcb drc --refill-zones --schematic-parity` on the saved file: **0 unconnected,
  0 errors, schematic parity 0**. Warnings only: 96 lib_footprint_mismatch, 135 silk-over-copper, 71 silk overlaps,
  3 silk at edge. In1 = GND plane, In2 = 1V8 plane (a few short signal slots, no islands). Renders:
  `doc/route/routed-2026-10-27.png` (F+B copper), `doc/route/in2-plane-2026-10-27.png`, `doc/route/render-top-2026-10-27.png`.
- **How:** `doc/route/build.sh` (placement + planes + fanout + DSN) → Freerouting → `finish.sh` (A2B B trio first, locked;
  DRC repair; rip-up loop) → `finish2.sh` → `finish3.sh` (rip every net near U1 and the ZIFs, re-route mic pairs first;
  In2 at 3× cost so the 1V8 plane stops being carved up) → last two links by hand-driven `ripnets.py --local`, `fanout.py`
  with `FANOUT_PADS`, and `maze.py` with `MAZE_BUDGET=15e6` (the 60 mm I2S0_BCLK run round the ring exceeded the old
  fixed 3 M-cell A* budget, which had been reporting "no path" silently).
- **Hand-check `[measured]`** (track length, vias):

  | Net(s) | Length | Note |
  |---|---|---|
  | A_AP / A_AN | 9.7 / 14.9 mm, 2 / 3 vias | 5 mm skew — ~30 ps, harmless at A2B rates |
  | B_BP / B_BN / B_BCM | 8.1 / 6.3 / 3.1 mm | the one forced crossing taken by BCM's vias |
  | SW1V8 (buck switch node) | 7.4 mm, F.Cu, 0 vias | longer than ideal (aim < 5 mm); acceptable, tighten if EMI shows |
  | MK2_OUTP / N | 20.2 / 21.8 mm, both mainly B.Cu | pair stays together |
  | MK1_OUTP / N | 22.2 mm F.Cu / 19.9 mm mostly B.Cu | **pair split across layers** — B.Cu references the 1V8 plane, F.Cu the GND plane; works, but worth re-pairing |
  | DMIC_CLK / DATA | 22.0 / 21.7 mm | fine for 3 MHz PDM |
  | I2S0 BCLK / FSYNC / SDATAI / SDATAO | 86 / 68 / 68 / 90 mm, 8 / 10 / 8 / 3 vias | long way round U6 → U1; fine at I2S rates, but the via counts are ugly |
  | HPOUTP / N | 58 / 48 mm | to the U4/U5 speaker switch |
- **Open (before fab):** ZIF pinout check against a kit; FH12 LCSC part; MK1 pair onto one layer; silkscreen tidy and
  "REF\*\*" on custom footprints; enclosure fit of the 72/38 ring and the flex tails.

## Boom electret pass-through — 2026-10-29, per Peter

Peter chose to bring the headset's boom electret in through a cup rather than straight to the audio board's J6.
- **J12 = two solder pads** (`Connector_Wire:SolderWire-0.15sqmm_1x02_P4mm_D0.5mm_OD1.5mm`): 1 `ELEC_HI`, 2 `ELEC_LO`.
  Peter chose pads over a connector: the outer band of the ring had no room for a 2-pin JST GH next to the wider J7.
  Placed at 311° on the outer edge, just past J2. The boom wires are soldered on (strain-relieve them in the cup).
- **J7 is now 6-pin (SM06B):** 1 `A_LINE_P`, 2 `A_LINE_N`, 3 `XF_SEC_A`, 4 `XF_SEC_B`, **5 `ELEC_HI`, 6 `ELEC_LO`**.
  The new pins mate audio J3.5/J3.6 (cup L) or J4.3/J4.4 (cup R). **Cup R's split harness becomes:** J7 pins 1–2 from
  cup L's J8; pins 3–6 from the audio board's J4 pins 1–4.
- `ELEC_HI`/`ELEC_LO` are an **aircraft circuit** (console-biased, isolated from our GND). On this board they touch only
  J12 and J7, in a new **Aircraft netclass (0.5 mm clearance)**. They run on B.Cu over the In2 1V8 plane, so the
  isolation is the 0.5 mm clearance; there is no galvanic contact. Both cups carry the pads; only the cup on the boom's
  side gets wires.
- **Checked `[measured]`:** cup DRC 0 unconnected, 0 errors (`916fef4`). One parity *warning*: J12's footprint is
  exclude-from-BOM and the symbol is not (Konnect can't set the symbol flag). Untick "In BOM" on J12 in eeschema,
  or drop J12 from the JLC BOM by hand.
