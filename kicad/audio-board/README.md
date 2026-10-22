# Audio board (AeroNode side) — clean-slate redo

**Status:** rulings recorded, schematic **not yet redrawn**. Started 2026-10-22, per Peter:
*"redo the audio board schematic on a clean slate using the new reference diagram from Juliette."*

**Reference:** JULIETT's interface spec, `Aerosense-Dev-Team-Sync:reports/john/2026-10-21_aeronode_audio_flow.pdf`
(company `1cf7160`, 10 pages), with John's 2026-10-21 rulings: the ADAU1467 hub is adopted
(`L-2026-W36-011`), the ADXL354 and ADAU1761 leave production, the cabin mic is single-ended analogue.

**What it replaces:** the ADAU1861 + AD2428 + ADXL354 + LTC6242 + level-shifter board last committed at
`72278d1` (`audio-board.kicad_sch` + `boom-mic-tx-select.kicad_sch`). That board was a different
architecture, not an earlier revision of this one; it stays retrievable from git at that SHA.

## Architecture (from the spec, §1–§2)

- **Normal — entirely digital.** Panel earphone → SP-74 (T2/T3) → high-Z tap → `ADAU1372 ADC1` → ADAU1467
  hub → (a) CM5 for AeroVault, (b) AD2433 → A2B → cups. Pilot voice: cup PDM mic → A2B → hub → CM5
  PureVoice → hub → `ADAU1372 DAC0` → buffer → K1 → panel mic line.
- **Bypass — entirely analogue, entirely aircraft-powered.** Panel audio → SP-74 → cup K2 N.C. → driver.
  Failsafe electret (console-biased) → K1 de-energised → panel mic line.
- **Cabin mic:** IM68A130A, single-ended analogue → `ADAU1372 ADC0`. No I²S mic.
- **Clock:** one 12.288 MHz XO → ADAU1467 `XTALIN/MCLK`; hub distributes `CLKOUT` and BCLK/LRCLK to the
  1372, CM5 (slave) and AD2433. Hub self-boots from EEPROM.
- **ICM-45686** (DVNC reference) is on SPI to the CM5 and never enters the audio chain — not on this board.

## Rulings (Peter, 2026-10-22)

| # | Ruling | Note |
|---|---|---|
| 1 | **Keep A2B**, per the spec | Peter floated I²S + power + bypass over an HDMI-type cable with JST ends, then withdrew it |
| 2 | **K1 = Panasonic AQW612S pair**, same as cup K2 | One package per leg; Form B (LED off) = electret → panel mic = bypass; Form A (LED on) = DAC → panel mic. Both legs broken, so our ground leaves the electret loop. Replaces the spec's "relay" and my earlier G6K-2 suggestion. At mic-level impedances (~1 kΩ) the 2.5 Ω on-resistance is negligible, so K2's open THD question barely applies here `[derived]` |
| 3 | ~~K1 LEDs driven from a TPS3430 watchdog kicked by the PureVoice process~~ | Ruled earlier the same day, then **superseded by 4** once the bare TPS3430 turned out not to latch (below) |
| 4 | **Watchdog left off for now** | K1 LEDs driven from a CM5 GPIO through a transistor, LEDs **off** at GPIO reset/high-Z (pull-down on the base), so power loss and CM5 boot both sit in bypass. `[default]` — the GPIO drive is my choice, not Peter's words. **Accepted residual:** power present + CM5 hung leaves K1 in NORMAL with a silent DAC on the panel mic — the spec §3 failure mode. Leave footprint room for a TPS3430 + 74LVC1G74 so it can return without a re-spin |
| 5 | ~~A2B part is the AD2428, not the AD2433~~ — **superseded by 6 the same day** — both ends (AeroNode main node, each cup sub-node) | Peter, 2026-10-22, after the AD2433's full data sheet turned out to be NDA-only. **Reverses the 2026-09-25 choice** (JULIETT `2026-09-25-003`), whose reason was that the AD2428W has **no SPI**, so DVNC/ANC coefficients cannot go *CM5 → SPI → A2B → cup ADAU1861* as spec §2 draws. They go by **A2B remote I²C** instead. `docs/a2b-remote-i2c-throughput.md` (2026-09-25) found that viable: 14 kB/s against a 384 kB/s control-header ceiling `[derived]`. **Condition carried with it:** erratum 18000075 — a failed remote-I²C write may not report an error, so coefficients must be written with **read-back verification**, or the canceller silently stops tracking; erratum 18000052 — remote I²C contends with GPIO-over-distance for the same header fields. **John/JULIETT not yet told** |
| 6 | **A2B part is the AD2433 at both ends** — AeroNode main node and each cup sub-node | Peter, 2026-10-22, once the SPI point was clear. Restores JULIETT `2026-09-25-003`: coefficients go *CM5 → SPI0 → hub → AD2433 SPI over distance → cup ADAU1861*, landing straight in DSP memory. Ruling 5's remote-I²C errata no longer apply to the coefficient path. **Brings back the NDA blocker** for the AD2433 symbol (below) |
| 7 | **I²S from the CM5 to the audio board** | Peter, 2026-10-22. CM5 is I²S slave to the hub (spec §4). Over the AeroNode's existing audio header J3/J4 — below |

Defaults stated to Peter 2026-10-22 and not overridden — **confirm before layout**:

- Only VBAT crosses to the host board; all rails regulated locally (carries the 2026-09 ruling forward).
- A2B daisy-chained AeroNode → cup L → cup R; cup boards stay identical.
- The failsafe electret gets its **own connector** on this board, so spec §8's open question (where it
  physically lives) does not force a redraw.

## Parked — TPS3430 alone will not hold K1 in bypass `[fetched]`

Kept for when the watchdog comes back (ruling 4 parks it).

From the TPS3430 data sheet (SBVS366A, Oct 2021):

1. **`~WDO` is not latched.** §7.3.3.3: *"When asserted, WDO remains down for tRST"*. Then the watchdog
   restarts and waits up to tWDU(max) for a first edge. A **hung** CM5 therefore produces a pulse train:
   `~WDO` high (K1 normal, silent DAC on the panel mic) for ~tWDU, low (bypass) for tRST. With factory
   timing (CWD = NC, SET = 11) that is **~1.6 s normal / 200 ms bypass** — the pilot loses transmit ~89 %
   of the time. Stretching tRST to 3.2 s (CRST = 1 µF) with an 11 ms window inverts the ratio but leaves a
   ~12 ms dropout-to-silence every 3.2 s: clicks on the radio.
2. **`~WDO` is high at power-up.** §7.4.2: below VDD(min) *"WDO is logic high"*, and the watchdog is
   disabled until tRST expires. Below VPOR it is *"undefined"*. High = LEDs on = **normal** — the wrong
   state while the CM5 is still booting.

**Proposed fix (parked with the watchdog):** keep the TPS3430 and add one 74LVC1G74 D flip-flop. `~WDO` (open drain)
and an RC power-on network share the flop's `~CLR` node, so both a watchdog fault and power-up **clear**
it; the CM5 clocks it set (`ARM`) once PureVoice is producing audio. LEDs on = Q high **and** `~WDO` high.
A hung box then falls to bypass and stays there until a living CM5 re-arms it. Same signal can later
drive cup K2 (spec §3, "proposed, not designed").

## CM5 ↔ audio board — the AeroNode's actual audio header `[measured]`

Read from `~/aerosense/aeronode/aerosense/aerosense.kicad_sch` (file dated 2026-08-31), netlist exported with
`kicad-cli sch export netlist --format kicadxml`, 2026-10-22. **Not under git there — confirm it is the current
AeroNode revision.** Supersedes the RP1-table guess that stood here earlier the same day (it assumed SPI0 was free).

| J3 pin | Net | | J4 pin | Net |
|---|---|---|---|---|
| 1 | GND | | 1 | CTL_MIC |
| 2 | WS | | 2 | CTL_SPKR |
| 3 | BCLK | | 3 | I2S1_SDI2 |
| 4 | I2S1_SDI0 | | 4 | I2S1_SDO2 |
| 5 | I2S1_SDO0 | | 5 | I2S1_SDI3 |
| 6 | I2S1_SDI1 | | 6 | I2S1_SDO3 |
| 7 | I2S1_SDO1 | | | |
| 8 | I2C_SCL | | | |
| 9 | I2C_SDA | | | |
| 10 | BAT_PWR | | | |

On the CM5 sheet: I2S1 = GPIO 18–27 (SCLK 18, WS 19, SDI0–3 = 20/22/24/26, SDO0–3 = 21/23/25/27); I2C1 =
GPIO 2/3; `GPIO_RLY_SPKR` = GPIO16, `GPIO_RLY_MIC` = GPIO17 (the old relay drives, presumably `CTL_SPKR`/`CTL_MIC`).

**What it means here:**

- **No SPI reaches the audio board** (Peter was right). GPIO 7–11 are labelled `SPI3_SCLK`/`SPI4_*` on the CM5
  sheet and go to no connector. So "SPI0 → hub" and "SPI0 → AD2433" are both off the table as drawn.
- **I²S is plentiful:** four data lanes each way. **I²C** is there for hub + ADAU1372 + AD2433 control.
- **BAT_PWR is the only power** — consistent with "only VBAT crosses". **One GND pin** for 16 signals,
  including two I²S clocks — thin for return current; worth a second GND when the header is next revised.
- `CTL_MIC` → K1 drive (ruling 4), `CTL_SPKR` → candidate for the cups' K2 drive.

**⚠ The header is not connected to the CM5 in that file `[measured]`.** Every J3/J4 net except GND has exactly
one node: the top sheet uses `/WS`, `/BCLK`, `/I2S1_SDI0`, `/I2C_SCL`, `/CTL_MIC`… while the CM5 sheet uses
`/CM5/I2S1_WS`, `/CM5/I2S1_SDI[0]`, `/CM5/I2C1_SCL`, `/CM5/GPIO_RLY_MIC`… — different names, no hierarchical
pins joining them. As drawn, the header goes nowhere. Owner of that schematic to fix (not this repo's file).

### Open — how the coefficients reach the AD2433 with no SPI on the header

1. **I²S slot** — CM5 → spare I²S lane → hub → A2B TDM slot → cup serial port; cup DSP unpacks + CRC-checks.
   Fits the header as-is. Costs cup firmware and a bit-exact hub route.
2. **I²C to the hub, hub's SPI master → AD2433 SPI** — keeps SPI-over-A2B to the cup. I²C ≤ 1 MHz on the hub
   (data sheet), ~7× headroom at 1 MHz, ~2.5× at 400 kHz, shared bus. `[assumed]` that the hub's SPI master
   (also its self-boot EEPROM port) can forward host data on demand — not checked.
3. **Add SPI to the AeroNode header** — GPIO 7–11 already carry SPI3/SPI4 labels on the CM5 sheet; costs 4–5 pins
   and an AeroNode change.

## Symbols

| Part | Library | Source | State |
|---|---|---|---|
| ADAU1467 | `AnalogDevices` | ADAU1463/1467 Rev A, Table 18 (`docs/datasheets/ADAU1463_1467.pdf`, gitignored) | **Done 2026-10-22.** 88 pins + EP as pin 89; numbers asserted 1–89 exactly. Footprint field empty — no stock 88-LFCSP 12×12 P0.5 in KiCad 10 |
| IM68A130A | `Infineon` | IM68A130A Rev 1.10, Table 3 | **Done 2026-10-22.** 1 OUT, 2/4 GND, 3 VDD. Footprint empty — PG-TLGA-4-2 not stock |
| AD2433 | — | **Blocked again (ruling 6): full data sheet is NDA-only.** Public `ad2431-32-33-35.pdf` (Rev SpB) is a 2-page summary, no pinout; ADI: a2b.support@analog.com. John spoke to ADI 2026-09-25 and may hold it. The AD2428 symbol stays in the library, unused here |
| K1 AQW612S, G6K-2, TPS3430, SiT8008, OPA1678, ADP7118 | existing / KiCad stock | — | available |

Both new symbols generated by `scripts/gen_adau1467_im68a130a_syms.py` and read back through
`kicad-cli sym export svg`: every pre-existing symbol in both libraries still parses (7 → 8 in
AnalogDevices, 1 → 2 in Infineon) `[measured]`. Pin-to-pad cross-check waits for the footprints.

## Still needed before drawing

- **AD2433 NDA data sheet** (ruling 6).
- Konnect (KiCad MCP) reconnected — the schematic is edited through it, not by hand.
- Spec §8 (electret location / count / isolation) and §4 (clock survival on the hub, not re-demonstrated)
  remain open; neither blocks the schematic, both block layout.
