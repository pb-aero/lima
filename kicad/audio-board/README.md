# Audio board (AeroNode side) — clean-slate redo

**Status:** **schematic redrawn 2026-10-22** — one A1 sheet, 108 parts (ruling 10 applied 2026-10-23), drawn entirely through Konnect.
Netlist matches `doc/design_nets.py` exactly; ERC 0 errors (4 expected strap warnings). Not reviewed,
no footprints for the custom parts, no layout. Started 2026-10-22, per Peter:
*"redo the audio board schematic on a clean slate using the new reference diagram from Juliette."*

**Reference:** JULIETT's interface spec, `Aerosense-Dev-Team-Sync:reports/john/2026-10-21_aeronode_audio_flow.pdf`
(company `1cf7160`, 10 pages), with John's 2026-10-21 rulings: the ADAU1467 hub is adopted
(`L-2026-W36-011`), the ADXL354 and ADAU1761 leave production, the cabin mic is single-ended analogue.

**What it replaces:** the ADAU1861 + AD2428 + ADXL354 + LTC6242 + level-shifter board last committed at
`72278d1` (`audio-board.kicad_sch` + `boom-mic-tx-select.kicad_sch`). That board was a different
architecture, not an earlier revision of this one; it stays retrievable from git at that SHA.

## Architecture (from the spec, §1–§2)

- **Normal — entirely digital.** Panel earphone → SP-74 (T2/T3) → high-Z tap → `ADAU1372 ADC1` → ADAU1467
  hub → (a) CM5 for AeroVault, (b) AD2428 → A2B → cups. Pilot voice: cup PDM mic → A2B → hub → CM5
  PureVoice → hub → `ADAU1372 DAC0` → buffer → K1 → panel mic line.
- **Bypass — entirely analogue, entirely aircraft-powered.** Panel audio → SP-74 → cup K2 N.C. → driver.
  Failsafe electret (console-biased) → K1 de-energised → panel mic line.
- **Cabin mic:** IM68A130A, single-ended analogue → `ADAU1372 ADC0`. No I²S mic.
- **Clock:** one 12.288 MHz XO → ADAU1467 `XTALIN/MCLK`; hub distributes `CLKOUT` and BCLK/LRCLK to the
  1372, CM5 (slave) and AD2428. Hub self-boots from EEPROM.
- **ICM-45686** (DVNC reference) is on SPI to the CM5 and never enters the audio chain — not on this board.

## Rulings (Peter, 2026-10-22)

| # | Ruling | Note |
|---|---|---|
| 1 | **Keep A2B**, per the spec | Peter floated I²S + power + bypass over an HDMI-type cable with JST ends, then withdrew it |
| 2 | **K1 = Panasonic AQW612S pair**, same as cup K2 | One package per leg; Form B (LED off) = electret → panel mic = bypass; Form A (LED on) = DAC → panel mic. Both legs broken, so our ground leaves the electret loop. Replaces the spec's "relay" and my earlier G6K-2 suggestion. At mic-level impedances (~1 kΩ) the 2.5 Ω on-resistance is negligible, so K2's open THD question barely applies here `[derived]` |
| 3 | ~~K1 LEDs driven from a TPS3430 watchdog kicked by the PureVoice process~~ | Ruled earlier the same day, then **superseded by 4** once the bare TPS3430 turned out not to latch (below) |
| 4 | **Watchdog left off for now** | K1 LEDs driven from a CM5 GPIO through a transistor, LEDs **off** at GPIO reset/high-Z (pull-down on the base), so power loss and CM5 boot both sit in bypass. `[default]` — the GPIO drive is my choice, not Peter's words. **Accepted residual:** power present + CM5 hung leaves K1 in NORMAL with a silent DAC on the panel mic — the spec §3 failure mode. Leave footprint room for a TPS3430 + 74LVC1G74 so it can return without a re-spin |
| 5 | ~~A2B part is the AD2428, not the AD2433~~ — **superseded by 6 the same day** — both ends (AeroNode main node, each cup sub-node) | Peter, 2026-10-22, after the AD2433's full data sheet turned out to be NDA-only. **Reverses the 2026-09-25 choice** (JULIETT `2026-09-25-003`), whose reason was that the AD2428W has **no SPI**, so DVNC/ANC coefficients cannot go *CM5 → SPI → A2B → cup ADAU1861* as spec §2 draws. They go by **A2B remote I²C** instead. `docs/a2b-remote-i2c-throughput.md` (2026-09-25) found that viable: 14 kB/s against a 384 kB/s control-header ceiling `[derived]`. **Condition carried with it:** erratum 18000075 — a failed remote-I²C write may not report an error, so coefficients must be written with **read-back verification**, or the canceller silently stops tracking; erratum 18000052 — remote I²C contends with GPIO-over-distance for the same header fields. **John/JULIETT not yet told** |
| 6 | ~~A2B part is the AD2433 at both ends~~ — **superseded by 9** — AeroNode main node and each cup sub-node | Peter, 2026-10-22, once the SPI point was clear. Restores JULIETT `2026-09-25-003`: coefficients go *CM5 → SPI0 → hub → AD2433 SPI over distance → cup ADAU1861*, landing straight in DSP memory. Ruling 5's remote-I²C errata no longer apply to the coefficient path. **Brings back the NDA blocker** for the AD2433 symbol (below) |
| 7 | **I²S from the CM5 to the audio board** | Peter, 2026-10-22. CM5 is I²S slave to the hub (spec §4). Over the AeroNode's existing audio header J3/J4 — below |
| 8 | **DVNC/ANC coefficients travel as audio data, not SPI** — CM5 → spare I²S lane → hub → A2B downstream TDM slot → cup ADAU1861 serial port → unpacked by the cup DSP | Peter, 2026-10-22, because the AeroNode audio header carries no SPI (option 1 of the three below). **Lane:** `I2S1_SDO1` (J3.7) `[default]`. **Requirements this creates:** (a) the hub must route that channel **bit-exact** — no gain, mix, ASRC, dither or limiter on it; (b) the stream carries its own **framing + CRC**, and the cup **keeps its previous coefficients** when a block fails — an audio slot has no ACK; (c) **cup firmware** work on the HiFi 3z, the cost JULIETT's SPI route avoided; (d) **one more downstream slot** in the A2B TDM map (still unfrozen). Bandwidth: 1 slot × 32 bit × 48 kHz = 1.536 Mbit/s vs ~112 kbit/s needed `[derived]`. **Consequence:** the AD2433's only stated advantage over the AD2428 was SPI-over-A2B for exactly this path (JULIETT `2026-09-25-003`), so ruling 6's reason no longer holds — the AD2428 (non-NDA, symbol already in the library) would serve. **Ruled in 9.** John/JULIETT not told |
| 9 | **A2B part is the AD2428 at both ends** — AeroNode main node and each cup sub-node | Peter, 2026-10-22, once ruling 8 took SPI out of the coefficient path: full data sheet public (`docs/datasheets/AD242x_RevC.pdf`), symbol already in `AnalogDevices`. Remote I²C over A2B is now **control traffic only**, so errata 18000075/18000052 touch configuration, not the canceller. **Slot capacity `[fetched]`** AD242x TRM: *"Up to 32 channels (1 x TDM32 or 2 x TDM16)"*, TDM2–TDM32 per pin — the two-slot cap asked about in JULIETT `2026-09-25-003` §2.3 is the PDM-clocked-from-BCLK case only (TDM2/32 or TDM4/16), which does not apply: the cup voice mic is on the ADAU1861's DMIC, not the AD2428's PDM pins |
| 10 | **PureVoice output through a Bourns SM-LP-5001 (T4), not the TLV9062 buffer** | Peter, 2026-10-23. Restores his September ruling (*"use the transformer approach for the aircraft side"*, status.md), which the clean-slate redraw had dropped — and the redraw had also bonded our GND to the panel mic return through K1 mic-lo, the exact failure status.md warned about. Both HPOUTL legs drive the 600 ohm primary directly (no primary cap). **Attenuator on the secondary** (R10 10k: primary then sees ~116 ohm, LF corner ~5 Hz; on the primary it would be 419 Hz). **DC block on the aircraft side** (C37 220 nF film, 63 V; 69 Hz with 10.47k) so the console's mic bias never reaches the winding. Secondary return **PV_RTN -> K1 mic-lo (U11.5)**, never our GND. Level `[derived]` from ADAU1372 DS (1.94 Vrms diff FS at AVDD 3.3 V `[fetched]`): 1.54 Vrms after 2 dB insertion loss, ~69 mVrms into a ~470 ohm mic node at 0 dBFS. Removes U8, R11-R16, C36, C38. SP-74 rejected for this job: 80:32/8 ohm speaker matching, 1000 Vrms/1 s hipot vs 2000 Vrms/1 min, 300 Hz low edge. **Open:** SM-LP-5001 environmental rating vs the SP-74's MIL-T-27E — check before flight hardware |
| 11 | **CTL_SPKR (J2.2) controls the cup K2 PhotoMOS via A2B GPIO-over-distance: AD2428 IO7 (pin 16) -> virtual port -> each cup's AD2428 IO pin -> K2 LED drive.** A2B IRQ (pin 6) unused; the CM5 polls `A2B_INTSTAT` over I2C | Peter, 2026-10-23, after first choosing a dedicated conductor pair per cup and then switching. `[fetched]` AD242x TRM "GPIO Over Distance": no host intervention after set-up; main-node IO7 is a GPIO when PDM is off; virtual ports OR together, so both cups can follow one port. Fails toward bypass: K2 can only energise while bus power, the A2B link and the cup are alive. **Open:** a sub-node's GPIO output state if the data link drops while bus power stays up — not in the section read. Requires the A2B sub-node on the cup board (being added) |
| 12 | **8 V regulated A2B bus: U12 LM2731X boost from VBAT (VBUS8), feeding the bus bias (D3) and the main node's VIN (D2)** | Peter, 2026-10-23, after `docs/a2b-bus-power-budget.md` showed a battery-direct bus puts cup R below the AD2428's 3.7 V minimum under 5.26 V battery. `[fetched]` LM2731 SNVS217G: VFB 1.23 V, R2 ≥ 13.3 k, Cf for a ~6 kHz zero, 10 µH at 1.6 MHz, Schottky diode, EN must not float. R27/R28 73.2k/13.3k = 8.00 V; C60 330 pF; L7 10 µH; D4 MBR0520; C57 10 µF in, C58/C59 2×10 µF 25 V out. Peak switch current ~0.38 A at 5 V in and 190 mA out vs 1.4 A min limit `[derived]`. Main-node VIN 7.6 V (max 9.0); `A2B_SWCTL.MODE` stays 0 because VIN and bias share the 8 V source. Cup R VIN 6.44 V worst case. Cup R7/R8 → 680R to match |

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

## CM5 ↔ audio board — one FFC, mating AeroNode J9 (2026-10-26, supersedes the J3/J4 section below)

Peter, 2026-10-26: *"for j1 and j2 can we please use one connector for a flex ribbon"*. Source: AeroNode
schematic **HW ver 0.0.2 rev 1** (Altium PDF, 2026-10-01, ~/Downloads), sheet 6, **J9 "audio breakout"** —
Cvilux **CF31241D0R0-05-NH**, 24 circuits, 0.5 mm pitch, downside (bottom) contact, "FLEX contact side to face PCB".

**Ours:** J1 = the same Cvilux part (footprint `Cvilux:Cvilux_CF31241D0R0-05-NH_…`, from drawing CF3101SF sheet 2).
**Cable:** flat, connectors facing each other (Peter) → standard **Type A** (same-side contacts) 0.5 mm, 24-way FFC,
so **our pin n = J9 pin 25−n**. If the cable is ever folded, this rule changes — re-check before ordering.

| J9 | AeroNode net | ours | | J9 | AeroNode net | ours |
|---|---|---|---|---|---|---|
| 1 | Gnd | J1.24 GND | | 13 | Audio_I2S_WS | J1.12 I2S_WS |
| 2 | Vcm3.3 | J1.23 **NC** | | 14 | Audio_I2S_SDI0 | J1.11 HOST_SDI0 |
| 3 | Audio_IN_Dat0_I2S_SDI3 | J1.22 HOST_SDI3 | | 15 | Audio_I2S_SDO0 | J1.10 HOST_SDO0 |
| 4 | Audio_IN_Dat1_I2S_SDO3 | J1.21 HOST_SDO3 | | 16 | reserved | J1.9 **NC** |
| 5 | Audio_IN_Clk_I2S_SDO2 | J1.20 HOST_SDO2 | | 17 | GPIO_RLY_SPKR | J1.8 CTL_SPKR |
| 6 | Gnd | J1.19 GND | | 18 | GPIO_RLY_MIC | J1.7 CTL_MIC |
| 7 | Audio_I2S_SDI2 | J1.18 HOST_SDI2 | | 19 | Gnd | J1.6 GND |
| 8 | Audio_I2S_SDI1 | J1.17 HOST_SDI1 | | 20 | sensor_I2C_SCL | J1.5 I2C_SCL |
| 9 | Audio_I2S_SDO1 | J1.16 HOST_SDO1 | | 21 | sensor_I2C_SDA | J1.4 I2C_SDA |
| 10 | Gnd | J1.15 GND | | 22 | Gnd | J1.3 GND |
| 11 | Audio_I2S_SCLK | J1.14 I2S_BCLK | | 23 | Vsys via Q1/D1/F1 | J1.2 VBAT |
| 12 | Gnd | J1.13 GND | | 24 | Gnd (TVS Z4 return) | J1.1 GND |
| M | Gnd | J1.MP GND | | | | |

Checked `[measured]`: netlist == `doc/design_nets.py`; independent J9 cross-check (J9 typed from the PDF, mapped
25−n, compared with the exported netlist) 0 mismatches; ERC 0 errors.

**Open — AeroNode side, for its owner (not this repo's file):**
- **Power is one contact (J9.23) behind F1, 0ZCJ0010FF2E: 100 mA hold / 250 mA trip.** This board needs roughly
  0.35 A typical, 0.5 A worst case from a 5 V battery `[derived]` (cup power budget + hub + codec + 8 V A2B boost).
  **Re-run 2026-10-30 (`docs/h1-power-budget.md`): 327 mA normal, 606 mA worst case at 5.0 V; 201 mA even in bypass** —
  above F1's hold current in every mode.
  F1 will trip, and one 0.5 A CF31 contact `[fetched, sibling-part listing]` has no margin even with a bigger fuse.
  Their own sheet asks whether the TVS and polyfuse belong on the breakout board. Needs 2–3 power contacts (e.g.
  J9.2 and J9.16 re-assigned) and a fuse sized for the load.
- **Vsys voltage** is not stated on that sheet; this board still assumes VBAT = 5.0–7.3 V (my default 1).
- J9.2 Vcm3.3 is left open here on purpose — tying it to our +3V3 would put two regulators on one rail.
- Footprint tab-pad x (±7.00 mm) is derived from C and F, not dimensioned directly — check against the
  drawing / a sample before fab.

## CM5 ↔ audio board — the AeroNode's actual audio header `[measured]` (superseded 2026-10-26, kept for the record)

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
- **I²S is plentiful:** four data lanes each way. **I²C** is there for hub + ADAU1372 + AD2428 control.
- **BAT_PWR is the only power** — consistent with "only VBAT crosses". **One GND pin** for 16 signals,
  including two I²S clocks — thin for return current; worth a second GND when the header is next revised.
- `CTL_MIC` → K1 drive (ruling 4), `CTL_SPKR` → candidate for the cups' K2 drive.

**⚠ The header is not connected to the CM5 in that file `[measured]`.** Every J3/J4 net except GND has exactly
one node: the top sheet uses `/WS`, `/BCLK`, `/I2S1_SDI0`, `/I2C_SCL`, `/CTL_MIC`… while the CM5 sheet uses
`/CM5/I2S1_WS`, `/CM5/I2S1_SDI[0]`, `/CM5/I2C1_SCL`, `/CM5/GPIO_RLY_MIC`… — different names, no hierarchical
pins joining them. As drawn, the header goes nowhere. Owner of that schematic to fix (not this repo's file).

### Decided (ruling 8) — how the coefficients cross with no SPI on the header

Option 1 chosen. Kept for the record:

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
| AD2428 | `AnalogDevices` (existing) | AD242x Rev C | available — ruling 9. (AD2433 dropped; its NDA data sheet no longer needed) |
| K1 AQW612S, G6K-2, TPS3430, SiT8008, OPA1678, ADP7118 | existing / KiCad stock | — | available |

Both new symbols were first written by `scripts/gen_adau1467_im68a130a_syms.py` — a breach of the Konnect
rule (no direct `.kicad_sym` edits) — then deleted and **re-created through Konnect `create_symbol`** with the
same pins (pin geometry taken from the script as JSON; diff vs the script output: properties only). Read back through
`kicad-cli sym export svg`: every pre-existing symbol in both libraries still parses (7 → 8 in
AnalogDevices, 1 → 2 in Infineon) `[measured]`. Pin-to-pad cross-check waits for the footprints.

## The drawn schematic (2026-10-22)

`audio-board.kicad_sch`, one A1 sheet in five labelled blocks, connected by net labels. Flat rather than
hierarchical on purpose: Konnect's bulk labelling makes sheet-local labels only, so a hierarchy would
have meant several hundred single global-label calls. Old sheets are in git at `72278d1`.

**How it was checked.** `doc/design_nets.py` is the intended connectivity, written before drawing: every
pin of every part is on a named net or in an explicit no-connect list. `python3 -I doc/design_nets.py
check <netlist.xml>` diffs it against `kicad-cli sch export netlist --format kicadxml` — the KiCad
netlist, not Konnect's view of it. Result: **OK** — all nets complete, no extra pins, no stray pins,
all 42 NC pins unconnected `[measured]`. ERC: **0 errors**; 4 warnings, all `pin_to_pin`
bidirectional-to-power on straps (U5 WP/HOLD to +3V3, U9 ADR1/ADR2 to GND) — intended.

| Block | Parts | Source of the circuit |
|---|---|---|
| Power + host | J1/J2 (AeroNode J3/J4 mirror), U1 TPS62162 3V3, U2 TPS62160 1V2 (R1/R2 49.9k/100k = 1.199 V), U3 ADP7118 3V3A | TPS6216x DS: VFB 0.8 V, 2.2 µH + 22 µF `[fetched]` |
| Hub | U4 ADAU1467, Y1 12.288 MHz, U5 W25Q32 boot flash, PLL filter C9/C10/R5, R26 VDRIVE→GND, 13 decouplers | ADAU1463/1467 Rev A: Fig. 16, pin 3, self-boot section `[fetched]` |
| Codec | U6 ADAU1372, U7 IM68A130A, comms tap R7/R8/C27/D1, PureVoice out T4 SM-LP-5001 + R10/C37 (ruling 10; was U8 TLV9062) | ADAU1372 pin table `[fetched]` |
| A2B | U9 AD2428 + bus-power switch (D3, Q1 AO3401A, R17–R20, C46–C48, L3/L4) + coupling | EVAL-AD2428WD1BZ sheet 2, B side, read from rendered image `[fetched]` |
| Aircraft / bypass | J5 panel, J6 electret, T2/T3 SP-74, U10/U11 AQW612S (K1), Q2, R23/R24 390R | rulings 2 and 4; AQW61xS DS (IF 5–30 mA) `[fetched]` |

**Found on the way:** the old board's A2B network never connected the positive bus bias (`A2B_BIAS_P`,
L3.2, went nowhere) — coupling only, no bus power to the cups. The new one carries ADI's full SWP switch.

### My defaults in it — confirm or overrule

1. **VBAT = 2S LiFePO4, 5.0–7.3 V.** From my own AeroNode charger scar; the AeroNode sheet's `BAT_PWR` pin
   goes nowhere, so it does not say. Everything (bucks, AD2428 VIN, K1 LED current) is sized on it.
2. **1V2 buck is 1 A against a 940 mA hub maximum** (330 mA typical). Fine for the typical program; no margin
   for the worst case.
3. **Hub/codec reset = U2 power-good** — the header has no reset line.
4. **Codec I2C address straps all 0; AD2428 ADR1/ADR2 = 0; hub ADDR = 0.** Exact 7-bit addresses not
   checked against each other `[assumed]` — they are different part families.
5. **Comms tap grounds the cup-L speaker return (SPK_L_B) through R9 0R.** Depopulate R9 to float it.
6. **PureVoice level ~69 mVrms at 0 dBFS** (T4 + R10 10k into an assumed ~470 ohm mic node) — the panel mic input spec is unknown (spec §9); trim in DSP.
7. **J3 = cup L (A2B + speaker), J4 = cup R (speaker only)**; cup R gets A2B from cup L. **2026-10-29 (Peter): boom electret also arrives through either cup** — J3 is now 6-pin (5 `ELEC_HI`, 6 `ELEC_LO`), J4 4-pin (3 `ELEC_HI`, 4 `ELEC_LO`), both on the J6 / K1 electret nets; J6 stays as an alternative entry. Routed over the planes at 0.5 mm Aircraft clearance — **Peter, 2026-10-29: leave it so** (no EAR-style plane-free corridor).
8. ~~CTL_SPKR repurposed as A2B_IRQ~~ — superseded by ruling 11 (CTL_SPKR -> AD2428 IO7 -> cup K2).

### Still open

- **Footprints:** ADAU1467 (88-LFCSP 12×12) and IM68A130A (PG-TLGA-4-2) have none; T2/T3, FL1, J1–J6 not chosen.
- **Bus-power margin** at 5.0 V battery through D3, Q1, two cables and two cup nodes — not analysed.
- **SP-74 secondary polarity** (paralleling 3/5 and 4/6 wrongly shorts them) — still unverified.
- **SP-74 power at full panel volume — checked 2026-10-23 against the GMA 340.** Garmin spec sheet M02-10023-00
  (REV0300) `[fetched]`: *"100 mW per stereo channel, each headset, into 150 ohms"* = 3.87 Vrms. Our load is two
  SP-74s in parallel = 158 ohm, so `[derived]` **47.5 mW per SP-74 against its 50 mW rating (95 %)**. One SP-74
  driving both cups would carry **94.9 mW (190 %)** — so the second SP-74 stays (Peter asked 2026-10-23). Margin
  is thin even with two; the sheet is a 2000-era spec sheet, not the installation manual (190-00149-01), which
  was not checked. Other panels: re-run with their headphone rating.
  **Stereo split (T2 on L, T3 on R) considered and declined — Peter, 2026-10-23: both primaries stay on one mono
  earphone line.**
- **AeroNode header is unconnected in its own file** (see the header section) — owner's fix.
- Spec §8 (electret location / count / isolation) and §4 (clock survival on the hub) — block layout.
- Watchdog parked (ruling 4); TPS3430 + 74LVC1G74 footprint room not yet reserved (no layout yet).

## Cup harness topology — daisy chain kept (Peter, 2026-10-30)

Considered: merge J3 + J4 into one 12-way GH with a Y-split to both cups' J7, dropping cup L's J8. A2B cannot
branch (each link is one node's B port to the next node's A port), so that needs a second AD2428 main node on this
board (~20 bus-network parts, a second hub TDM port, a second I²C address, re-layout of the routed right edge).
Gains would be one connector, a symmetric harness and cup R independent of cup L. **Peter: keep the daisy chain**
(audio J3 → cup L J7, cup L J8 → cup R J7.1–2, audio J4 → cup R J7.3–6). Headband conductors are 6 either way.
