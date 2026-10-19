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
