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
| MK3 | IM73A135V01 | Voice mic (replaces the boom mic) → AINP2/AINN2, differential |
| U2 | LSM6DSV16BX | DVNC reference, TDM slave into U1's SPT1 (`TDM_DATA`/`TDM_BCLK`/`TDM_WCLK`); I²C host mode for config |
| U3 | MAXM86161 | In-ear optical HR/SpO₂ module (added 2026-10-19, per Peter) — I²C on the shared bus, own LED supply |
| J2 | 2-pin | Earcup driver: **pin 1 = HPOUTN, pin 2 = HPOUTP** (ordered so the two wires don't cross) |
| J3 | 3-pin | Power in: 1V8, 3V3_MIC, GND — source TBD |
| J4 | 2-pin | LED supply in: VLED, GND — voltage and source TBD |
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

## Power budget (estimate, per cup) — 2026-10-19

Datasheet typicals only, `[fetched]` unless marked. Nothing measured. Excludes the speaker's
output power (signal-dependent) and the A2B subnode, which isn't on this sheet yet.

| Part | Rail | Current | Power | Basis |
|---|---|---|---|---|
| U1 ADAU1861, ANC config | 1V8 | 6.4 mA (HP amp idle) – 11.3 mA (HP amp on, no load) | 11.5 – 20.3 mW | Table 7, "High performance, normal voltage": 3 ADCs + DAC + FastDSP @192 kHz, HiFi 3z bypassed. AVDD 3.04 / 7.87 mA + DVDD 3.06 mA + IOVDD 0.32 mA. `[assumed]` DVDD current is drawn from the 1V8 rail by the internal regulator — the datasheet doesn't name the regulator's input |
| U2 LSM6DSV16BX | 1V8 | 0.60 (accel + TDM) – 0.95 mA (+ gyro) | 1.1 – 1.7 mW | Table 4, LA_IddHPT / IddHPT |
| MK1–MK3 IM73A135 ×3 | mic rail, 2.75 V | 0.51 mA typ, 0.69 mA max | 1.4 – 1.9 mW | Table 7: 170 µA typ / 230 µA max each, normal mode |
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
- **MK3 placement/purpose.** Assumed to be a voice-pickup mic replacing the boom. Its acoustic
  position in the cup (and whether it is useful on both sides) is not established.
- **VLED voltage is undecided.** The datasheet gives only the 3.0–5.5 V range and says to set it
  for the LEDs' forward voltage plus driver headroom. The green LED is the one most likely to need
  more than 3.3 V; 5 V would be the conservative choice, but nothing here establishes it.
- **`PPG_INT` goes nowhere yet.** It needs a GPIO on whatever reads the sensor — most likely the
  A2B subnode's GPIO, which doesn't exist on this sheet yet.
- **MAXM86161 power-up sequencing** (VLED vs 1V8 / LDO_EN) wasn't in the extracted datasheet
  text — not checked.
- **Optical placement.** The module has to sit against skin in the ear canal / concha through a
  window; where that is on the cup, and whether both cups need one, isn't established.
- **The MAXM86161 symbol is hand-entered** from the datasheet's pin table into
  `kicad/lib/AnalogDevices.kicad_sym`; worth a second check against a hand-downloaded PDF.
- **No AD2428W A2B subnode, no power-delivery path, no footprints** — unchanged from before.
