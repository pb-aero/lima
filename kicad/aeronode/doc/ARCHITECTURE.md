# AeroNode — ConnectCore 93 carrier board

**Status:** architecture agreed 2026-08-21, schematic not yet drawn.
**Module:** Digi ConnectCore 93, **castellated** variant, `Digi:ConnectCore93` +
`Digi:Digi_ConnectCore93_Castellated`.

## Decisions taken (from Peter, 2026-08-21)

| | |
|---|---|
| Role | **CC93 carrier only** — no sensors on this board |
| IMU | **Separate board**, reached over a connector |
| Power source | **2S LiFePO4, 6000 mAh, with BMS** |
| Charging | **On-board, over USB** |
| Scope | Full schematic in one pass |

## Power architecture

```
USB-C ─┬─ CC1/CC2 ─► PD sink ──► VBUS 5 / 9 / 15 / 20 V
       │                              │
       └─ D+/D- ───────────────────►  │  ──► CC93 USB_OTG1 (pads 113/114)
                                      │      recovery + debug console
                                      ▼
                       buck-boost charger (1-4S, I2C)
                                      │
                    ┌─────────────────┴───────────────┐
                    ▼                                 ▼
          2S LiFePO4 6 Ah + BMS                 SYS (power-path)
          5.00 V empty ... 7.30 V full          5.0 - 7.3 V
                                                      │
                                                      ▼
                                            buck ──► 5.0 V
                                                      │
                                    ┌─────────────────┼──────────────┐
                                    ▼                 ▼              ▼
                            CC93 VSYS (33)    CC93 VSYS2 (31,32)   USB host VBUS
                                    │
                            on-module PCA9451 PMIC
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
             3V3 out (pad 29)                1V8 out (pad 27)
             carrier logic, PHY,             level-sensitive I/O
             CAN VIO, IMU connector
```

**Why a buck-boost charger and not a boost:** the input is 5 V from a plain USB port but
9–20 V from a PD source, and the pack sits at 7.2 V. That crosses the output voltage in both
directions, so the charger must do both.

**Why a 5.0 V rail and not buck-boost to VSYS:** VSYS accepts 3.7–6.0 V and the pack never falls
below 5.0 V, so boosting is never required. A synchronous buck that supports 100% duty simply passes
the pack through at deep discharge (~4.9 V), still well inside the VSYS window.

## ⚠ Hazard 1 — LiFePO4 charge voltage is 7.2 V, not 8.4 V  · **REVISED 2026-08-22, worse than first stated**

Two-cell **Li-ion** charges at 4.20 V/cell = 8.40 V. Two-cell **LiFePO4** charges at 3.60 V/cell =
**7.20 V**. Nearly every 2S charger IC defaults to the Li-ion figure.

If the charger begins charging at its power-on default before Linux has booted and written the
correct `VREG`, it drives **1.2 V of overcharge** into an LFP pack. LFP degrades above ~3.8 V/cell.

**Required mitigation:** charging must be **disabled by hardware default** — `/CE` pulled to the
inactive state by a resistor, not by software — and enabled only after the CPU has set
`VREG = 7.20 V`. Confirm the charger's POR default from its datasheet **before** committing the part;
if it cannot be made safe at POR, choose a charger with a resistor-programmed charge voltage.

**The BMS is the backstop, never the control.** A design that relies on the protection board to stop
routine overcharge is a design that cooks the pack every cycle until the BMS wears out.

### REVISION — the watchdog reverts VREG on its own

`[fetched]` from the BQ25798 datasheet (SLUSDV2C), verified in the document, not from a summary:

> "Assuming that the CELL bits remain at the 2s battery configuration, then when the REG_RST bit is
> set **or the watchdog timer expires**, the registers are reset to default values with ICHG, VSYSMIN
> and **VREG automatically returning to 1A, 7V and 8.4V** respectively."

**This is the dangerous part, and it is not a power-on problem — it is a runtime one.** Setting
`VREG = 7.2 V` once at boot is *not sufficient*. Every watchdog expiry silently restores **8.4 V**:
+1.2 V of overcharge into a LiFePO4 pack, applied automatically, with no host involvement. The
watchdog fires in **40 / 80 / 160 s** depending on setting. A host crash, hang, suspend, or a firmware
update that pauses the driver is enough to trigger it.

**Required mitigations, all three:**

1. **`/CE` pulled HIGH by a resistor** so charging is disabled at power-on until the host explicitly
   enables it. The datasheet is explicit that this pin must not float: *"CE pin must be pulled HIGH or
   LOW, do not leave floating."* Implemented as **R1 (100k) from `REGN` to `CHG_CE_N`** — REGN is the
   charger's own LDO, so the pull-up exists whenever the charger is powered, before any host boots.
2. **The I2C watchdog must be DISABLED** (`WATCHDOG` bits = 0) by the host immediately after it writes
   `VREG = 7.2 V` — or serviced without fail forever, which is a far weaker guarantee. **This is a
   firmware requirement created by the hardware, and it must be written into the driver bring-up
   notes, not left to be discovered.**
3. **`PROG` resistor sets the 2S POR profile** so the cell count is right before the host says
   anything. R2 — value still to be read from the datasheet's PROG table.

Note the POR default for 2S is VREG **8.4 V**, i.e. Li-ion. The part will happily do the wrong thing
out of reset; that is exactly what mitigation 1 is for.

## ⚠ Hazard 2 — PD VBUS must not reach the module's USB1_VBUS pin

`USB1_VBUS` (pad 116) is a 5 V VBUS-detect input. If the PD sink negotiates 9 V, 15 V or 20 V, that
voltage appears on the connector's VBUS — and must **not** be wired to pad 116.

Use a separate 5 V-referenced VBUS-present sense (divider + clamp, or a comparator running off the
carrier 5 V rail). A direct connection is the obvious thing to draw and it destroys the module the
first time someone plugs in a PD charger.

## Charge budget `[measured]`

Pack: 6.4 V nominal × 6.0 Ah = **38.4 Wh**. 4 W system load while charging, 90% charger efficiency,
0.5C LFP charge ceiling, CC phase only — a CV tail adds roughly 20%.

| Source | Input | To charge | Charge current | CC time |
|---|---|---|---|---|
| USB 5 V / 3 A | 15 W | 9.9 W | 1.38 A | 4.4 h |
| USB-C PD 9 V / 3 A | 27 W | 20.7 W | 2.88 A | **2.1 h** |
| USB-C PD 15 V / 3 A | 45 W | 36.9 W | 3.00 A (pack limit) | 2.0 h |
| USB-C PD 20 V / 3 A | 60 W | 50.4 W | 3.00 A (pack limit) | 2.0 h |

**PD at 9 V already reaches the pack's own 0.5C ceiling.** Negotiating 15 V or 20 V buys nothing for
charging and only raises the stress on Hazard 2. Recommend the sink request **9 V**.

Discharge: 38.4 Wh at 3–6 W gives roughly **6–9 hours**, less converter losses and unusable capacity.

## Peripheral allocation

| Block | CC93 pads | Part | Note |
|---|---|---|---|
| Gigabit Ethernet | 96–107 RGMII, 109 MDIO, 110 MDC | KSZ9031RNX + magnetics + 8P8C | largest block; PHY lives on the carrier |
| CAN 1 | 76 RX, 77 TX | SN65HVD23x | 3.3 V transceiver, direct to CC93 I/O |
| CAN 2 | 78 RX, 79 TX | SN65HVD23x | see CAN-FD note below |
| USB-C (charge + recovery) | 113/114 D±, 116 VBUS-sense | USB_C_Receptacle + PD sink | **Hazard 2** |
| USB host | 111/112 | USB-A | VBUS from the carrier 5 V rail |
| microSD | 1, 4–10, 12, 36 | Micro_SD_Card_Det | NVCC_SD2 rail, SD2_VSELECT |
| Console | 74 TX, 75 RX (UART6) | header | U-Boot default console |
| **IMU connector** | **13, 14, 80, 81 (LPSPI3 ALT1)** | 9-way | + CS2 pad 90, INT pads 91/92, 3V3, GND |
| Reset | 56 SYS_RESET | button | active low, internal pull-up |

### The IMU connector costs UART7

LPSPI3 is muxed onto UART7's four pins. Taking SPI means **there is no second UART** — UART6 (console)
is untouched, but nothing else is left. If the carrier later needs a spare serial port, that decision
has to be revisited before layout.

### CAN FD

The i.MX93 FlexCAN supports CAN FD. `SN65HVD23x` is **classic CAN, 1 Mbps** — it will not run FD data
phases. If FD is wanted, substitute an FD-rated transceiver (MCP2562FD / MCP2542FD class) and check
the logic-supply pin: parts without a `VIO` pin present 5 V logic to a 3.3 V module input.

## Decisions taken 2026-08-21 (later)

- **PD sink negotiates 9 V.** Already reaches the pack's 0.5C ceiling; higher voltages buy nothing
  for charging and only worsen Hazard 2.
- **No CAN.** Neither FD nor classic. The CAN1/CAN2 pads (76-79) are free for other use.
- **A2B transceiver instead** — see the blocker below.

## 🛑 BLOCKER — A2B cannot run on the castellated variant

An A2B main node (ADI AD242x) needs **two** host interfaces, both mandatory `[fetched]`: **I2C** for
control and readback, and a multichannel **I2S/TDM** link for audio. There is no alternative host
interface on the part.

I2C is fine — I2C2 (pads 17/18) and I2C4 (pads 88/89) are both available.

**I2S/TDM is not.** The complete SAI inventory of the castellated pinout `[measured]` from the HRM
mux tables:

| Instance | Available | Verdict |
|---|---|---|
| SAI1 | `RX_BCLK` pad 18, `RX_SYNC` pad 17 | no data, no MCLK |
| SAI2 | `RX_BCLK` pad 26, `RX_SYNC` pad 25 | no data, no MCLK — and both are **1V8** pads |
| SAI3 | `MCLK` pad 93, `RX_BCLK` pad 35, `RX_SYNC` **pad 2**, `TX_DATA00` **pad 2** | see below |

**`SAI3_TX_DATA00` is the only SAI data line anywhere on the 118 castellated pads, and it shares
pad 2 with `SAI3_RX_SYNC`, the only frame sync.** A pad carries one function at a time, so the best
achievable is MCLK + BCLK + *either* sync *or* data. Neither combination is a working I2S port, and
there is no RX data line at all.

Fallbacks considered and rejected: MQS1/MQS2 (pads 8/9) is PWM output only, not a bus; PDM is
microphone input, not I2S; FlexIO can synthesise I2S but Linux support is thin and an A2B TDM frame
is not a sensible bit-bang target for flight hardware.

### The LGA variant resolves it completely

`[measured]` from the same manual, LGA pad tables pp.43-82: full **SAI1**, **SAI2** and **SAI3** with
MCLK, TX_BCLK, TX_SYNC, RX_BCLK, RX_SYNC and data — SAI2 alone brings out **four TX and four RX data
lanes**, which is a genuine multichannel TDM interface and exactly what A2B wants.

**The footprint cost of switching is already paid.** Digi's own `CC93_DVK.PcbLib` converts cleanly to
a KiCad `.kicad_mod` through KiCad's built-in Altium importer — 474 pads plus 6 mounting holes,
vendor-authoritative, no transcription. Verified 2026-08-21.

**~~The real cost is the PCB. A 474-pad LGA on 1.27 mm pitch needs escape routing under the module —
realistically 8+ layers, likely via-in-pad~~ — RETRACTED 2026-08-22, see "Board stackup" below.**
That estimate was made from the pad count alone, before counting how many pads this design actually
uses. It is wrong: **4 layers is sufficient.**

The LGA also relieves the LPSPI3/UART7 conflict noted above, since it brings out far more I/O.

### RESOLVED 2026-08-21 — LGA variant adopted

Footprint `Digi:Digi_ConnectCore93_LGA` is built and verified (see `kicad/lib/README.md`).

## A2B link — SAI3, on dedicated pads

AeroNode **transmits** as well as receives audio, so the host needs a full-duplex I2S/TDM port.

**SAI3 is used, not SAI1.** All five signals are *dedicated primary pads* — they carry no other
function, so nothing is sacrificed and nothing conflicts:

| A2B role | SAI3 signal | LGA pad | Rail | Mux |
|---|---|---|---|---|
| bit clock | `SAI3_TXC` | E23 | 3V3 | primary |
| frame sync | `SAI3_TXFS` | C19 | 3V3 | primary |
| host -> A2B (DRX) | `SAI3_TXD` | E20 | 3V3 | primary |
| A2B -> host (DTX) | `SAI3_RXD` | E21 | 3V3 | primary |
| master clock | `SAI3_MCLK` | B24 | 3V3 | primary |

Control bus: I2C2 (V1/W1), I2C3 (AK24/AK25) or I2C4 (E29/F28) — all free.

### Why not SAI1 — a boot hazard avoided

SAI1 was the original choice, carried over from the castellated analysis where it was the only
instance with both a clock and a sync. **That reasoning did not survive the variant change** and was
re-derived. On the LGA, SAI1's transmit path is muxed onto the SPI1 block:

- `SAI1_TX_DATA00` -> **E17 = SPI1_SCK = BOOT_MODE3**
- `SAI1_TX_DATA01` -> **C17 = SPI1_CS0 = BOOT_MODE2**

There is no third TX data pad, so **transmitting over SAI1 always lands on a boot-mode strap.**
BOOT_MODE is sampled on the rising edge of POR_B, and Digi warns that peripherals on those lines can
change the sampled value and make boot fail. Choosing SAI3 removes the hazard outright — no 100k
pull-down discipline, no holding the transceiver in reset through POR, no buffer with output-enable.

SAI2 is also strap-free but sits entirely on the **1V8** rail (muxed onto ENET2), so it would need
level shifting to a 3.3 V transceiver and would cost the second Ethernet MAC.

## IMU interconnect — J1, wired 2026-08-22

`J1` (`Conn_02x10_Odd_Even`, value `IMU_BOARD`) carries the two IMUs on **independent SPI buses**,
one per chip. The IMUs live on `kicad/imu-board`; see its notes for why the buses are split.

| J1 | net | CC93 pad | function | | J1 | net | CC93 pad | function |
|---|---|---|---|---|---|---|---|---|
| 1 | `+3V3` | — | *pending power sheet* | | 2 | `GND` | — | *pending* |
| 3 | `ICM_SCLK` | **D17** | LPSPI8_SCK | | 4 | `GND` | — | |
| 5 | `ICM_MOSI` | **E18** | LPSPI8_SOUT | | 6 | `ICM_MISO` | **E22** | LPSPI8_SIN |
| 7 | `ICM_CS` | **E19** | LPSPI8_CS0 | | 8 | `GND` | — | |
| 9 | `ICM_INT1` | **E28** | GPIO2_IO22 | | 10 | `ICM_INT2` | **E27** | GPIO2_IO23 |
| 11 | `BMI_SCLK` | **N29** | LPSPI3_SCK | | 12 | `GND` | — | |
| 13 | `BMI_MOSI` | **M29** | LPSPI3_SOUT | | 14 | `BMI_SDO` | **R1** | LPSPI3_SIN |
| 15 | `BMI_SDO` | **R1** | *(tied — see below)* | | 16 | `BMI_ACC_CS` | **P1** | LPSPI3_PCS0 |
| 17 | `BMI_GYR_CS` | **C24** | GPIO2_IO24 | | 18 | `GND` | — | |
| 19 | `BMI_ACC_INT` | **AA1** | GPIO2_IO06 | | 20 | `BMI_GYR_INT` | **Y1** | GPIO1_IO10 |

Grounds are interleaved between the SPI groups rather than bunched at one end — a ribbon or FFC needs
a return conductor adjacent to each clock, not one at the far end of the connector.

### Why these two SPI instances

- **LPSPI8** sits on **dedicated primary pads** (D17/E18/E19/E22) — no mux conflict, no boot strap.
- **LPSPI3** sits on the UART7 pads (P1/R1/M29/N29), clean, and costs only UART7.
- **LPSPI4 and LPSPI5 were rejected** — both land on SAI3's pads, which the A2B link owns.
- **LPSPI1 and LPSPI2 were rejected** — both touch BOOT_MODE straps.

### J1 pins 14 and 15 are the same net, deliberately

The BMI088's accel and gyro dies have separate data outputs (`SDO1`, `SDO2`) but **share `SCK` and
`SDI`**, so they cannot have independent buses. `imu-board` brings both SDOs out separately; AeroNode
ties them onto `LPSPI3_SIN` (R1), which is Bosch's own topology — the chip selects arbitrate which die
drives the line.

**The tie lives here, on the host, not on the sensor board.** That is deliberate: cutting it is a
board-edit on AeroNode if the two dies ever need genuinely separate readback, and it keeps the ERC
output-conflict off the sensor board where it would have to be permanently excluded.

### Verified `[measured]` 2026-08-22

All 13 IMU nets land on exactly the intended endpoints (`BMI_SDO` on three: two J1 pins + R1);
`find_shorted_nets` **0**; ERC unconnected-pin count fell **349 -> 336**, exactly the 13 module pins
wired and no others disturbed.

**`+3V3` and `GND` on J1 are not yet tied to the module** — the CC93's 3V3/1V8 outputs and its 166 GND
pads belong to the power sheet, which is the next piece of work. Until then `+3V3` is legitimately a
single-pin net and ERC says so.

## Power sheet — stage 1: module rails, wired 2026-08-22

The SOM's own power distribution, sourced from HRM pp.13-15. Upstream (charger, buck, PD sink) is
stage 2 and not yet drawn.

### What the HRM actually says

**Only three rails must be fed externally:** `VSYS` (3.7-6.0 V), `VSYS2` (2.7-6.0 V) and
**`NVCC_SD2`** — the last is easy to miss; it is the i.MX93's uSDHC2 I/O supply and appears in the
*input* rail table, not the output one.

Outputs available to the carrier: `3V3` (BUCK4, from VSYS), `1V8` (BUCK5, from VSYS2),
`MUX_3V3_1V8` (LDO5, 150 mA, **not** used internally) and `SWOUT` (load switch, 2.8-5.5 V, 400 mA,
also not used internally).

### Connections made

| Net | Pads | Note |
|---|---|---|
| `+5V` | VSYS AL6/AL7/AL8, VSYS2 AJ2/AJ3/AJ4/AK2/AK3/AK4 | 9 pads. Tied as one supply — the Design Guidelines call VSYS/VSYS2 "the one and only input supply" |
| `+3V3` | AK1, AL2, AL3, AM3, AM4 | module output; also feeds J1 pin 1 |
| `+1V8` | AH1, AH2, AH3, E5 | module output |
| `NVCC_SD2` | F20 (`MUX_3V3_1V8`) + N1 (`NVCC_SD2`) | LDO5 powers the SD I/O rail, per Digi's note |
| `SD_VSELECT` | AH13 + AN5 (`SD2_VSELECT`) | Digi's explicit recommendation — LDO5 auto-tracks SDIO speed |
| `GND` | **all 166 pads** | two rail wires + 162 junctions + 2 labels |

### Deliberately left unconnected

- **`3V3_RF` (F17, F18)** — appears **exactly once in 103 pages**, as a bare pad name. No description,
  no power group, no comment; in neither the input nor the output rail table. **Direction unknown, so
  it is not wired.** Ask Digi before assuming.
- `SWIN` / `SWOUT` / `SW_EN` — the PMIC load switch, unused so far.
- `CLKIN1`, `CLKIN2`, `PMIC_STANDBY` — no requirement identified yet.

### Symbol pin types corrected

Regenerating exposed a real error and a false one:

- **`NVCC_SD2` was typed `power_out`. It is an input.** Corrected to `power_in`.
- `3V3` x5 and `1V8` x4 are multiple pads of **one internal rail**; typing them all `power_out` made
  KiCad flag 8 output-to-output conflicts. One driver kept per rail, duplicates set `passive`.
- `3V3_RF` set `passive` — asserting a direction on an undocumented supply pin would be a guess.
- Load switch typed properly: `SWIN` power_in, `SWOUT` power_out, `SW_EN` input.

### ERC after stage 1 `[measured]`

154 violations: 148 `pin_not_connected` (peripherals not yet wired), 3 `power_pin_not_driven`
(`+5V` and `GND` have no source until stage 2; `SWIN` unconnected), 3 `pin_not_driven`
(`SW_EN`, `ON_OFF`, `SYS_RESET`). **All 8 `pin_to_pin` conflicts cleared.**

Progression, each step matching its prediction exactly: 514 -> 170 (166 GND) -> 148 (22 rail pads).

## Power sheet — stage 2: supply chain, partial 2026-08-22

Placed and wired: **J2** USB-C receptacle, **U2** CYPD3177-24LQ PD sink, **U3** BQ25798 buck-boost
charger, **J3** 2S LiFePO4 + BMS connector, **R1** `/CE` pull-up, **R2** PROG.

Power path nets: `VBUS` (J2 -> U2 -> U3) · `CC1`/`CC2` (J2 -> U2) · `VBAT` (U3 <-> J3) ·
`BAT_TS` (U3 <-> J3 thermistor) · `REGN` · `CHG_CE_N` · `CHG_PROG` · `VSYS_CHG` · `GND`.

## Power sheet — stage 3: buck and setpoints, 2026-08-22

### `VSYS_CHG` -> `+5V` buck — U4 LMR33630ADDA

The charger's SYS rail sits at roughly **7.0-7.3 V** for a 2S pack (VSYSMIN POR default 7 V), which is
**above the CC93's 6.0 V absolute maximum** — this buck is not optional.

`[fetched]` LMR33630 datasheet: V_IN 3.8-36 V, V_OUT 1-24 V, 3 A, **V_FB = 1.000 V** (0.985-1.015),
"A" variant = 400 kHz.

| Ref | Value | Role |
|---|---|---|
| U4 | LMR33630ADDA | synchronous buck, EN tied to `VSYS_CHG` (always on with input) |
| L1 | **4.7 uH** | 7.3->5.0 V at 3 A, 400 kHz, 30% ripple gives 4.4 uH -> 4.7 uH standard |
| R9 / R10 | **100k / 24.9k** | feedback divider. V_OUT = 1.000 x (1 + 100/24.9) = **5.016 V** |
| C1 | 10 uF | input bulk on `VSYS_CHG` |
| C2 | 47 uF | output bulk on `+5V` |
| C3 | 100 nF | bootstrap, `BOOT_5V` to `SW_5V` |
| C4 | 1 uF | `VCC_BUCK`, the internal 5 V LDO |

5.016 V sits comfortably inside VSYS's 3.7-6.0 V window with ~1 V of headroom to the absolute maximum.

### PD setpoints — sourced, not guessed

`[fetched]` EZ-PD BCR datasheet (002-25383 Rev *B), Tables 2 and 3. These four pins are **resistor
dividers from `VDDD`** (the chip's own 3.3 V LDO), not single pulldowns.

| Pin | Setting | Pull-up | Pull-down | Refs |
|---|---|---|---|---|
| `VBUS_MIN` | **9 V** | 5.1k | 1k | R3 / R4 |
| `VBUS_MAX` | **9 V** | 5.1k | 1k | R5 / R6 |
| `ISNK_COARSE` | **3 A** | 5.1k | 5.1k | R7 / R8 |
| `ISNK_FINE` | 0 A | open | 0 | tied directly to GND |

Min and max are **deliberately both 9 V**. The datasheet's Note 3: *"VBUS_MIN and VBUS_MAX can be set
to the same value to select one specific voltage level from the Type-C power adapter."* That makes the
sink demand exactly 9 V rather than accept a range.

**⚠ Note 2 of that datasheet matters:** *"EZ-PD BCR device does not monitor the current on VBUS_IN and
enforce it within ISNK limits. It is the responsibility of the system to not consume more current than
what the power adapter can provide."* The ISNK setting is a **request, not a limit** — the BQ25798's
own input current limit has to do the actual enforcing. Do not treat R7/R8 as protection.

`FAULT` (U2 pin 9) is brought out as `PD_FAULT`; it goes high if the adapter cannot meet the
voltage/current request, or if VBUS drifts 20% outside the window. It wants a CC93 GPIO.

## Power sheet — stage 4: charger control link, 2026-08-22

**This is the link the whole LiFePO4 mitigation depends on.** Without it the host cannot write
`VREG = 7.2 V`, cannot disable the watchdog, and cannot enable charging at all.

| Net | CC93 pad | Function | Charger |
|---|---|---|---|
| `CHG_SCL` | **V1** | I2C2_SCL | U3 pin 14 |
| `CHG_SDA` | **W1** | I2C2_SDA | U3 pin 15 |
| `CHG_CE_N` | **AN4** | GPIO2_IO18 | U3 pin 13 — host pulls LOW to enable |
| `CHG_INT_N` | **E3** | GPIO2_IO19 | U3 pin 21 |
| `PD_FAULT` | **P29** | GPIO2_IO25 | U2 pin 9 |
| `PG_5V` | **R29** | GPIO2_IO27 | U4 pin 4 |

Pull-ups: R11/R12 **10k** on SCL/SDA (the BQ25798 datasheet specifies 10k to the logic rail), R13 10k
on the open-drain `INT`, R14 100k on the open-drain `PG`. `CHG_STAT_N` drives **D1** through R15 1k
from +3V3 — cathode to the charger's open drain, so the LED lights while charging.

### GPIO came from dropping CAN

Only two 3V3 pads with a GPIO alt were genuinely unallocated (AN4, E3). `PD_FAULT` and `PG_5V` use
**P29 and R29 — the CAN2 pads** — which are free because CAN was dropped in favour of A2B. Worth
knowing: **if CAN is ever reinstated, these two GPIOs go with it.** CAN1's pads (T29/U29) remain as
the next spare pair.

`CHG_CE_N` now has three connections — R1's pull-up (disable at POR), the charger, and the CC93 GPIO
that pulls it low to enable. That completes mitigation 1: the part is off until software deliberately
turns it on.

### Firmware obligations created by this hardware

Written here because they are hardware-imposed and will not be obvious from the driver's point of view:

1. Write `CELLS` = 2s, then **`VREG` = 7.20 V** (not the 8.4 V POR default).
2. **Disable the I2C watchdog** (`WATCHDOG` = 0). If it is left running, every expiry silently restores
   `VREG` to 8.4 V. See Hazard 1.
3. Only then drive `CHG_CE_N` low to enable charging.
4. Order matters. Enabling charge before setting VREG charges a LiFePO4 pack at the Li-ion voltage.

## Power sheet — stage 5: VSYS overvoltage protection, 2026-08-22

### The threat

`VSYS` has a **6.0 V absolute maximum** and the buck output is 5.016 V — a window of under a volt.
Behind it sits `VSYS_CHG` at **7.0-7.3 V**. Two realistic faults put that straight onto the module:

1. The buck's high-side FET fails short — input appears on the output.
2. **The feedback lower leg (R10) goes open** — FB reads 0 V, the buck drives to maximum duty, and the
   output runs up toward V_IN. This is a classic and it needs no exotic failure, just one bad joint.

**A TVS cannot do this job.** A 5 V TVS clamps around 9 V, far past the 6.0 V limit. Neither can a
Zener-referenced discrete: the usable window is 5.12 V (buck nominal +2%) to 6.0 V, and Zener
tolerance of +/-5% would either nuisance-trip or miss. This needs a precision reference.

### Implementation — U5 LTC4364CMS surge stopper

Inserted **between the buck and the module**. The buck's own output is now `+5V_RAW`; `+5V` is the
protected rail that feeds VSYS, so no module-side rework was needed.

**The feedback divider (R9/R10) deliberately senses `+5V_RAW`, not the protected side.** If it sensed
downstream and the OVP opened, the buck would lose feedback and drive to full duty — the protection
would cause the very fault it exists to stop.

| Ref | Value | Role | Result |
|---|---|---|---|
| Q1 | N-FET, **TBD** | series pass element, driven by HGATE | see open items |
| R22 | 15 mohm | current sense (`SENSE`-`OUT`) | 50 mV threshold / 3 A = 16.7 mohm |
| R16 / R17 | **34k / 10k** | OV divider | trip **5.500 V** |
| R18 / R19 | **22.1k / 10k** | UV divider | trip **4.013 V** |
| R20 / R21 | **30.1k / 10k** | FB divider | clamps output to **5.013 V** during a surge |
| C5 | 0.22 uF | TMR fault timer | |

`[fetched]` LTC4364 datasheet: OV, UV and FB all reference **1.25 V** (FB servo 1.22/1.25/1.28), VCC
operating range 4-80 V, overcurrent threshold ~50 mV. All three dividers land on E96 1% values almost
exactly. `OVP_FLT_N` goes to CC93 pad **T29** (ex-CAN1_TX).

Because this is a *surge stopper* rather than a plain disconnect, during an overvoltage it **regulates
the output down to 5.013 V and keeps the module running**, rather than dropping the system. The TMR
timer then shuts it off if the fault persists.

Margin: buck nominal 5.016 V (+2% = 5.116) -> OV trip 5.500 V -> VSYS absolute max 6.0 V.

### ⚠ Open items on this block — do not fabricate without closing these

1. **Q1 is unspecified.** During a clamped surge it dissipates (7.3 - 5.0) x I_load continuously until
   the TMR expires. It needs selecting on **SOA**, not just R_DS(on) and V_DS.
2. **`DGATE` (pin 4) is left unconnected.** That is the ideal-diode FET, which a single-source design
   does not need — but *whether the LTC4364 tolerates DGATE open* is not confirmed. Check the
   datasheet before layout.
3. **The part is used near the bottom of its range.** The LTC4364 is designed for 12-80 V rails and
   most of its specifications are characterised at 12 V. 5.016 V is above the guaranteed 4 V minimum
   but well below its design centre. A purpose-built low-voltage OVP switch with an adjustable
   threshold (TPS2596 class) would be the better part — it is not in the KiCad libraries, so it would
   need a symbol authoring. **Worth doing before this goes to fabrication.**
4. `ENOUT` (pin 14) is unused.

## Power sheet — stage 6: charger power stage and TS network, 2026-08-22

All values `[fetched]` from the BQ25798 datasheet's own application diagram and Table 7-1.

| Ref | Value | Role |
|---|---|---|
| **R2** | **6.04k** | PROG — Table 7-1: sets POR **1.5 MHz / 2s**. Was TBD |
| L2 | **1.0 uH** | buck-boost inductor, `CHG_SW1` to `CHG_SW2`. 1.0 uH pairs with 1.5 MHz (2.2 uH is the 750 kHz option) |
| C6 / C7 | 47 nF | bootstraps, `BTST1`->`SW1` and `BTST2`->`SW2` |
| C8 | 4.7 uF | `REGN` internal LDO |
| C9 | 10 uF | `VBUS` input |
| C10 | 10 uF | `PMID` |
| C11 | 10 uF | `BAT` |
| C12 | 10 uF | `SYS` |
| R23 / R24 | 5.24k / 30.31k | TS thermistor divider, `REGN`->`TS`->`GND` |

`VAC1` (pin 9) tied to `VBUS` as the adapter-present sense.

**Table 7-1 also confirms an assumption made earlier rather than checked:** the 2s POR defaults are
ICHG 1 A, **VSYSMIN 7 V**, VREG 8.4 V, with VREG programmable over 5-9.99 V. The 7 V VSYSMIN is what
puts the SYS rail at 7.0-7.3 V, which is why the buck and the OVP both exist. 7.20 V is comfortably
inside the allowed VREG range.

### ⚠ The TS divider values are the datasheet's **Li-ion** example, not LiFePO4

R23/R24 = 5.24k/30.31k come straight from the datasheet, where they are derived for
**T1 = 0 degC and T5 = 60 degC — the Li-ion/Li-polymer JEITA window.**

**LiFePO4 does not charge to 60 degC.** Its usual charge window is roughly **0 to 45 degC**; charging a
LiFePO4 cell at 60 degC degrades it. Left as-is, the hardware would permit charging well outside the
pack's safe temperature range.

Two ways to fix it, and one must be chosen before fabrication:

1. **Recompute R23/R24** for T1/T5 = 0/45 degC using the datasheet's equations (2) and (3) with the
   103AT NTC curve, or
2. **Tighten the JEITA thresholds over I2C** (`TS_COOL` / `TS_WARM` and the VREG/ICHG derating
   registers), leaving the divider as the coarse mapping.

This is the **third** LiFePO4-versus-Li-ion default to bite this design, after the 8.4 V VREG and the
watchdog revert. The pattern is consistent: **every charger default assumes Li-ion.** Anything on this
part that has a chemistry-dependent default should be treated as wrong until checked.

### ERC after stage 6 `[measured]`

182: 169 `pin_not_connected`, 8 `pin_not_driven`, 5 `power_pin_not_driven`. No isolated labels, no
`pin_to_pin`. All ten charger power-stage nets matched their predicted endpoint counts.

The 5 `power_pin_not_driven` are because no `PWR_FLAG` symbols have been placed yet — the rails are
fed by real regulators, but ERC cannot see a "source" without the flag. Worth adding on `+5V_RAW`,
`+3V3`, `+1V8`, `VBUS` and `GND` when the sheet is tidied.

### Still to do on this sheet

- `ILIM_HIZ`, `QON`, `ACDRV1`/`ACDRV2`, `SDRV`, `VAC2`, `D+`/`D-` on the charger: inductor, `BTST1`/`BTST2`, `SW1`/`SW2`, `PMID`, input/output bulk.
- R2 PROG value from the BQ25798 PROG resistance table.
- TS thermistor divider on the battery connector.
- `VAC1`/`VAC2`, `ACDRV1`/`ACDRV2`, `SDRV`, `ILIM_HIZ`, `QON` on the charger.

### ERC after stage 4 `[measured]`

187: 174 `pin_not_connected`, 9 `pin_not_driven`, 4 `power_pin_not_driven`. **Zero isolated labels** —
every net now reaches at least two pins. No `pin_to_pin` conflicts.

Progression across the whole power sheet, each step matching prediction:
514 -> 170 -> 148 -> 209 -> 204 -> 200 -> 188 -> **187**.

### Known cosmetic item

J2's `A4`/`B4` VBUS pins are **stacked at one coordinate** in the KiCad symbol, so wiring both left
two identical `VBUS` labels at the same point. Electrically it is one net with a redundant glyph;
Konnect cannot delete one of a coincident pair, so it wants a one-click tidy in eeschema.

### ERC after stage 2 (partial) `[measured]`

209: 190 `pin_not_connected` (U2/U3 setpoints, switching node and I2C not yet wired), 14
`pin_not_driven`, 4 `power_pin_not_driven`, 1 `isolated_pin_label` (`VSYS_CHG`, single-ended until the
buck exists). No `pin_to_pin` conflicts.

## Environmental sensor — U6 BME690, 2026-08-22

Bosch BME690: gas / temperature / humidity / pressure, LGA-8 3x3x0.93 mm. **Not in the KiCad
libraries**, so the symbol was authored at `kicad/lib/Bosch.kicad_sym` from the datasheet
(BST-BME690-DS001-00 Rev 1.0), Table 26.

| Pin | Name | Wired to | Why |
|---|---|---|---|
| 1, 7 | GND | `GND` | |
| 2 | CSB | **`+3V3`** | selects I2C — see below |
| 3 | SDI | `ENV_SDA` | = SDA |
| 4 | SCK | `ENV_SCL` | = SCL |
| 5 | SDO | **`GND`** | address LSB = 0 -> **I2C address 0x76** |
| 6 | VDDIO | `+3V3` | 1.2-3.6 V |
| 8 | VDD | `+3V3` | 1.71-3.6 V |

Bus: **I2C4** (CC93 pads E29/F28). **I2C3 stays reserved for A2B control.**
R25/R26 4.7k pull-ups; C13/C14 100 nF on VDD and VDDIO.

### ⚠ CSB must be at VDDIO *before* power-on-reset

The datasheet is explicit: *"If CSB is pulled down, the SPI interface is activated. After CSB has been
pulled down once (regardless of whether any clock cycle occurred), the I2C interface is disabled until
the next power-on-reset."* And: *"if I2C is to be used and CSB is not directly connected to VDDIO but
is instead connected to a programmable pin, it must be ensured that this pin already outputs the VDDIO
level during power-on-reset. If this is not the case, the device will be locked in SPI mode and not
respond to I2C commands."*

**CSB is therefore hard-wired to `+3V3`, not to a GPIO.** There is also an internal 70-190 kOhm pull-up
to VDDIO, but the hard wire removes any dependence on GPIO state at reset.

`SDI` is open-drain and **must** be externally pulled up — that is what R25 is for, not merely bus
convention.

### No interrupt line

The 8-pin package has no interrupt output, so the BME690 is **polled over I2C**. That is why no GPIO
was consumed, and **U29 (ex-CAN1_RX) remains the last free 3V3 GPIO.**

### Verified `[measured]`

Symbol pin numbers **1-8 match the footprint pads exactly, both directions**
(`Package_LGA:Bosch_LGA-8_3x3mm_P0.8mm_ClockwisePinNumbering` — the datasheet notes the unusual
clockwise-from-top numbering, which is why that specific footprint variant is correct).
`ENV_SDA` and `ENV_SCL` land on 3 endpoints each (sensor + module + pull-up). ERC 180, no isolated
labels, no `pin_to_pin`.

## GNSS — U7 u-blox DAN-F10N, 2026-08-22

L1/L5 dual-band with an **integrated 20 x 20 x 8 mm RHCP patch antenna**. Not in the KiCad libraries;
symbol authored at `kicad/lib/ublox.kicad_sym` from the datasheet (UBXDOC-963802114-13074 R04),
Table 11. 56 pins, of which 36 are GND and 7 Reserved.

**The DAN-F10N has no I2C and no SPI — it is UART only.** That drove the pin allocation.

| Function | Pin | Net | CC93 pad |
|---|---|---|---|
| module TXD | 10 | `GNSS_TXD` | **AK25** (LPUART5_RX, ALT5) |
| module RXD | 9 | `GNSS_RXD` | **AK24** (LPUART5_TX, ALT5) |
| TIMEPULSE (PPS) | 20 | `GNSS_PPS` | **U29** (GPIO) |
| ANT_CTRL | 32 | `GND` | selects the internal patch antenna (default) |
| VCC, V_BCKP | 52, 53, 55 | `+3V3` | |
| GND | 36 pins | `GND` | one rail + 34 junctions |

Left open per the datasheet: `RESET_N` (internal pull-up), `EXTINT`, `SAFEBOOT_N`, `VCC_RF`,
`EXT_RF_IN`, `LNA_EN`, and all 7 Reserved pins. C15 10 uF + C16 100 nF on VCC.

### Why LPUART5, and what it cost

**LPUART5 (AK24/AK25) was the only free 3.3 V UART.** The alternatives were all disqualified:

- LPUART6 — the U-Boot console. Not available.
- LPUART7, LPUART8 — already consumed by LPSPI3 and LPSPI8 for the IMUs.
- LPUART1 — on E13/E12, the **Bluetooth pads**, and E13 is a boot strap (see correction below).
- LPUART2 — TX lands on F11, BOOT_MODE1.
- LPUART3, LPUART4 — reachable only on **1V8** ENET pads. The DAN-F10N's `V_PIO` is referenced to VCC
  (abs max 3.6 V), so 1.8 V logic would not meet its input-high threshold; these would need level
  shifting.

**Cost: I2C3 is consumed.** A2B control now shares **I2C4** with the BME690 — no clash, since the
BME690 is 0x76 and the AD242x is a different address.

**`U29` was the last free 3V3 GPIO and PPS took it.** There is now no spare GPIO without muxing a
peripheral pad.

### ⚠ TIMEPULSE and SAFEBOOT_N share a pin internally

Datasheet: *"The SAFEBOOT_N pin is internally connected to TIMEPULSE pin through a 1 kOhm series
resistor"*, and *"The receiver enters safeboot mode if this pin is low at startup."*

`GNSS_PPS` therefore goes to a CC93 GPIO that **must not drive low at reset.** If U29 comes out of
reset as an output-low, it will drag SAFEBOOT_N through that 1 kOhm and put the receiver into safeboot
on every power-up. **Configure U29 as an input (or high-Z) in the device tree**, and verify its
power-on state.

### ⚠ The datasheet contradicts itself on pin numbers

**Table 11** (pin assignment) gives RXD=9, TXD=10, RESET_N=16, EXTINT=17, SAFEBOOT_N=18, TIMEPULSE=20,
LNA_EN=39. **Table 12** (pin state) on the very next page gives RXD=21, TXD=20, SAFEBOOT_N=1,
TIMEPULSE=3, RESET_N=8, EXTINT=4, LNA_EN=14 — numbers that look copied from a different module.

**The symbol follows Table 11**, which is self-consistent with the 56-pin package and the pin-out
figure. Worth confirming against the integration manual before fabrication.

### Mechanical

The integrated patch antenna makes this a **20 x 20 x 8 mm** component that must face the sky with a
clear view. It is by far the tallest part on the board and will drive the enclosure and the board
orientation — worth settling early rather than at layout.

### Verified `[measured]`

Symbol pin numbers **1-56 complete, no gaps or duplicates** (asserted at generation). `GNSS_TXD`,
`GNSS_RXD`, `GNSS_PPS` land on 2 endpoints each. U7's GND run reaches y=811.5 mm on an 841 mm sheet —
inside the frame. ERC 187, no isolated labels, no `pin_to_pin`.

## CORRECTION — the LGA boot-strap list was incomplete

Earlier work reported the boot straps on the LGA as **F11, C17, E17**. That was wrong: there are
**four**, and the fourth is **E13**.

The Design Guidelines name the straps `BT_UART1_TX`, `BT_UART1_RTS`, `SPI1_CS0`, `SPI1_SCK`. The LGA
pad table names that first pad **`BT_UART1_TXD`** — with a D. My strap detection matched the exact
string and silently missed it.

**Complete list: BOOT_MODE0 = E13, BOOT_MODE1 = F11, BOOT_MODE2 = C17, BOOT_MODE3 = E17.**

Nothing in the design touches any of them, so there is no rework — but the record was wrong, and the
same name mismatch would recur for anyone grepping the two Digi documents against each other.

## On/off switch — SW1, 2026-08-22

**SW1** is a momentary push button from `ON_OFF` (**AG18**) to GND, with R27 100R in series and C17
100 nF for debounce.

`[fetched]` HRM: AG18 is *"ON/OFF signal from the CPU (active low)"* on the module's **internal 1.8 V
supply**; the Design Guidelines add *"ON_OFF is the default power-on/off line of the ConnectCore 93.
It is active low and has an internal pull-up."*

**That 1.8 V reference is why the button goes to GND and nothing pulls it up.** An external pull-up to
3V3 would over-drive a 1.8 V-referenced input. The module's internal pull-up already defines the
idle state.

The PMIC watches this line even when the SOM is off, so one momentary button gives both power-on and
shutdown — it is a true on/off, not just a wake.

`PWR_ON` (**AJ12**) is deliberately left unconnected. The pad table is explicit: *"Output signal. Do
not drive this line externally."* It reports PMIC state (high = ON) and could drive a power LED, but
it too sits on an internal supply, so a buffer would be needed rather than a direct LED.

### ⚠ This is a SOFT off — the battery still drains

SW1 shuts down the SOM's PMIC. It does **not** disconnect the battery. The charger, the buck and the
OVP all keep running off the pack.

The dominant known term is the **LTC4364 at 370 uA typical** `[fetched]`; the LMR33630 adds ~25 uA in
regulation, and the BQ25798's quiescent has not been quantified yet. Call it order-1 mA, which drains
a 6 Ah pack over a period of months — **acceptable for daily use, not acceptable for storage.**

### The complement: true zero-drain off via ship mode

The BQ25798 already supports this and the pins are on the schematic, unwired:

- **`SDRV` (pin 24)** drives an external **ship FET** in series with the battery. *"When the device is
  in ship mode or in the shutdown mode, the SDRV turns off the external ship FET to minimize the
  battery leakage current."*
- **`QON` (pin 12)**: *"A logic low on this pin with tSM_EXIT duration turns on ship FET to force the
  device to exit the ship mode"* — typical **1 s** (or 15 ms, per `WKUP_DLY`).
- Ship mode is **entered** by writing `SDRV_CTRL[1:0] = 01` over I2C, and only with no adapter present.
  It exits on QON low, on `SDRV_CTRL` = 00, or on adapter plug-in.

So a complete storage-grade power control would be: **a second button on QON** (press to wake from
ship mode) plus **a ship FET on SDRV**, with software entering ship mode on a long press. That is a
different feature from SW1 and has not been added — flagged as a decision, not an oversight.

### Verified `[measured]`

`ON_OFF_N` lands on 3 endpoints (module, R27, C17), `ON_OFF_SW` on 2 (R27, SW1). ERC **185**, down
from 187 because `ON_OFF` was previously an undriven input. No isolated labels, no `pin_to_pin`.

## Status LEDs — D2 red, D3 green, D4 blue, 2026-08-22

Driven directly from CC93 GPIO, **no I/O expander** (Peter's call). LEDs **sink** into the GPIO —
anode to `+3V3` through the resistor, cathode to the pin — so they are **active low** and the pin
sinks rather than sources, which is the stronger direction on i.MX I/O.

| LED | Colour | Net | CC93 pad | GPIO | R |
|---|---|---|---|---|---|
| D2 | red | `LED_RED_N` | **C18** | GPIO1_IO12 | R28 160R |
| D3 | green | `LED_GRN_N` | **D18** | GPIO1_IO14 | R29 150R |
| D4 | blue | `LED_BLU_N` | **R29** | GPIO2_IO27 | R30 68R |

### Finding the three pins was the hard part

**There were zero free 3V3 GPIO left.** Every other GPIO-capable pad is on the **1V8** rail, and 1.8 V
cannot forward-bias a blue LED at all (Vf ~3 V). Sinking a 3V3 LED into a 1V8 pad would inject current
into that rail when the pin drove high.

- **C18 and D18** were recovered by re-examining an earlier over-broad exclusion: they are `SPI1_SIN`
  and `SPI1_SOUT`, and **SPI1 is unused in this design** (the IMUs are on LPSPI3 and LPSPI8). Neither
  is a boot strap — only `SPI1_CS0` (C17) and `SPI1_SCK` (E17) are.
- **R29 was reallocated from `PG_5V`.** That signal reported the 5 V rail was good, but if it were
  not, the module reading it would not be running — it is close to tautological on this topology. The
  genuinely dangerous case, overvoltage, is covered by `OVP_FLT_N`, which is retained. `PG_5V` remains
  as U4 pin 4 plus its R14 pull-up, so it is still probeable as a test point.

**AeroNode now has no spare GPIO of any kind at 3.3 V.** Anything further needs a 1V8 pad with a level
shifter or FET, the SD2 pads (costing microSD), or dropping an existing function.

### ⚠ Blue LED headroom on a 3.3 V rail

| | Vf | R | I |
|---|---|---|---|
| red | ~2.0 V | 160R | 8.1 mA |
| green | ~2.1 V | 150R | 8.0 mA |
| **blue** | ~2.9 V typ | 68R | **5.9 mA** |
| **blue, worst case** | **3.2 V** | 68R | **1.5 mA** |

Blue InGaN parts run Vf ~2.8-3.2 V, so on a 3.3 V rail the resistor sees only 0.1-0.5 V. The current
is therefore **very sensitive to Vf spread** — a 4x brightness variation across the tolerance band.

**Specify a blue LED with Vf max <= 3.0 V at the operating current**, and treat R30 as provisional
until a specific part is chosen. If consistent brightness matters, the alternative is to drive the
blue from `+5V` through a small FET — the PCA9536-style trick of sinking 5 V into the pin is *not*
available here, and driving 5 V into a 3.3 V CC93 pad would be worse.

## Magnetometer — U9 MEMSIC MMC5983MA, 2026-08-22

3-axis AMR magnetometer, LGA-16 3x3x1 mm, 18-bit. Not in the KiCad libraries; symbol authored at
`kicad/lib/MEMSIC.kicad_sym` from the datasheet (Rev A), pin description table.

| Pin | Name | Wired to |
|---|---|---|
| 1 | SCL/SPI_SCK | `I2C4_SCL` |
| 16 | SDA/SPI_SDI | `I2C4_SDA` |
| 4 | SPI_CS | **`+3V3`** — the datasheet: *"Tie to VDDIO for I2C Interface"* |
| 10 | **CAP** | **C18 10 uF to GND** — see below |
| 2, 13 | VDD, VDDIO | `+3V3` |
| 9, 11 | GND | `GND` |
| 15 | INT | left open — polled, no GPIO available |
| 5 | SPI_SDO | left open — unused in I2C mode |
| 3,6,7,8,12,14 | NC | no-connect |

I2C address **0x30** (fixed, `0b0110000`). No clash with the BME690 at 0x76. Supply 2.8-3.5 V,
absolute maximum 3.6 V — our regulated 3V3 (3.234-3.366 V with the PMIC's +/-2%) sits inside that,
but the margin to abs max is only ~0.23 V, so `+3V3` must not be allowed to rise.

### C18 is not decoupling

Pin 10 is `CAP`: *"Connect a 10uF capacitor for SET/RESET"*. It is the energy store for the
degaussing coil that performs the SET/RESET offset-cancellation cycle — the mechanism by which an AMR
sensor removes its own offset drift. **Omit it and SET/RESET does not work**, which quietly costs the
sensor its accuracy over temperature rather than failing outright. C19/C20 are the actual decoupling.

### ⚠ Magnetic interference — the real design constraint

A magnetometer on this board has to compete with:

- the **BQ25798 buck-boost at 1.5 MHz** with a 1.0 uH inductor, switching **battery-scale currents**
- the **LMR33630 buck at 400 kHz** with a 4.7 uH inductor, up to 3 A
- battery and charge currents of up to 3 A through the pack wiring
- three LED currents at ~8 mA
- the DAN-F10N's own supply currents

All of those are changing magnetic fields, and the field from a current loop falls off slowly. **A
magnetometer placed near them measures the board, not the Earth.**

This is a *placement* problem that the schematic cannot solve. Options, in decreasing order of
effectiveness:

1. **Put the magnetometer on the IMU board**, not AeroNode. It already goes off-board for the IMUs;
   the magnetometer belongs with them, away from the power stage. This is the strongest option and it
   costs nothing — `imu-board` has spare interface capacity.
2. Keep it on AeroNode but place it at the far corner from the charger and buck, with the inductors'
   loop area minimised and no high-current traces routed beneath it.
3. Accept it and calibrate — hard-iron and soft-iron calibration can remove *static* offsets, but
   **not** the time-varying field from a switching converter whose duty cycle follows the load.

**As wired it is on AeroNode. Flagging this as a decision worth taking before layout**, because
moving it later means changing two boards.

### Verified `[measured]`

`I2C4_SDA` and `I2C4_SCL` each land on 4 endpoints (CC93, pull-up, BME690, MMC5983MA); `MAG_CAP` on 2.
ERC 185, no isolated labels, no `pin_to_pin`. The two unconnected outputs (`INT`, `SPI_SDO`) account
for the rise from 183.

### Bus renamed

`ENV_SDA`/`ENV_SCL` are now **`I2C4_SDA`/`I2C4_SCL`**. Naming a shared bus after one device on it was
misleading once the magnetometer joined, and A2B control is still to come.

## Barometer — U10 Bosch BMP390, 2026-08-22

LGA-10, 2 x 2 x 0.75 mm, +/-3 Pa relative accuracy (~0.25 m). Not in the KiCad libraries; symbol
authored into the existing `kicad/lib/Bosch.kicad_sym` from the datasheet (BST-BMP390-DS002-07),
Table 52.

| Pin | Name | Wired to |
|---|---|---|
| 2 | SCK | `I2C4_SCL` |
| 4 | SDI | `I2C4_SDA` |
| 5 | SDO | `BARO_SA0` -> **R31 10k -> +3V3** (address bit = 1) |
| 6 | CSB | **`+3V3`** — selects I2C |
| 1, 10 | VDDIO, VDD | `+3V3` |
| 3, 8, 9 | VSS | `GND` |
| 7 | INT | left open — polled, no GPIO available |

### ⚠ Address clash avoided deliberately

Bosch pressure sensors default to **0x76 — which the BME690 already occupies on this bus.**
`SDO` is therefore tied **high** for **0x77**: *"Connecting SDO to GND results in slave address
1110110 (0x76); connecting it to VDDIO results in slave address 1110111 (0x77)"*.

The datasheet also warns: *"The SDO pin cannot be left floating; if left floating, the I2C address
will be undefined."* So it is strapped, not left open.

**I2C4 address map — check this before adding anything else to the bus:**

| Address | Device |
|---|---|
| 0x30 | MMC5983MA magnetometer |
| 0x76 | BME690 environmental |
| **0x77** | **BMP390 barometer** |

A2B control is still to be added to this bus; AD242x parts sit around 0x68, so no further conflict is
expected — but verify against the chosen transceiver.

### Why R31 rather than a direct strap

`SDO` is **bidirectional** — an output in SPI mode. Tying it hard to the rail would be a short if the
part ever left I2C. ERC flagged exactly this (`pin_to_pin`: bidirectional against power output), and
the 10k series resistor is the correct fix rather than an exclusion: `SDO` is high-impedance in I2C
mode, so 10k still sets the address cleanly.

**Note for consistency:** the BME690's `SDO` (pin 5) is currently a *direct* tie to GND — the same
pattern, benign while `CSB` holds the part in I2C mode, but it could be given the same 10k treatment
if you want the two to match.

### Interface selection, same trap as the BME690

*"If CSB is pulled down, the SPI interface is activated. After CSB has been pulled down once...
the I2C interface is disabled until the next power-on-reset."* `CSB` is hard-wired to `+3V3`.

Also recorded from the datasheet: *"Holding any interface pin (SDI, SDO, SCK or CSB) at a logical high
level when VDDIO is switched off can permanently damage the device."* Everything here shares `+3V3`,
so the rails collapse together — but this rules out any future scheme that powers the bus from a
different domain than the sensors.

### Verified `[measured]`

`I2C4_SDA` and `I2C4_SCL` each land on **5 endpoints** (CC93, pull-up, BME690, MMC5983MA, BMP390);
`BARO_SA0` on 2. ERC **186**, **no `pin_to_pin`**, no isolated labels.

## Board stackup — 4 layers, 2026-08-22

**Correction.** I previously stated this board needed **8+ layers with via-in-pad**, on the grounds
that it carries a 474-pad LGA at 1.27 mm pitch. **That was wrong**, and it was wrong because I judged
it from the pad count without counting the escape load. Actual census:

| Category | Pads | Escape burden |
|---|---|---|
| GND | 166 | via straight down to the plane — no routing |
| NC / RESERVED | 125 | nothing to connect |
| Power (VSYS/VSYS2/3V3/1V8) | 18 | via to plane |
| Signal pads left unused | 128 | not connected |
| **Signals actually wired** | **37** | **the only real escape** |

**37 signals out of 474 pads — 8%.** At **1.27 mm pitch** that is generous by BGA standards (0.8 mm
and 0.5 mm are routine), so ordinary dogbone vias with 4/4 mil rules will do it. No via-in-pad needed.

**Stackup as set:**

| Layer | Use |
|---|---|
| F.Cu | signal + LGA escape |
| In1.Cu | ground plane |
| In2.Cu | power plane (split: +5V / +3V3 / +1V8) |
| B.Cu | signal + remaining escape |

The 166 GND pads are the reason this works so easily — each is a single via to In1, which also gives
the switching converters a solid return directly beneath them.

## Footprint assignment — 81 of 83 done, 2026-08-22

Passives at 0402 (R and small C), 0603 for 1-10 uF and the LEDs, 0805 for the 47 uF bulk. R22 is
1206 as a 15 mohm/3 A current sense. Inductors: L1 SRN6028 (4.7 uH buck), L2 SRN4018 (1.0 uH charger).

### Two footprints still deliberately left EMPTY

An empty footprint is honest; a wrong land pattern looks finished and is not. These need real work:

| Ref | Part | What is needed |
|---|---|---|
| **U9** | MMC5983MA | `Package_LGA:LGA-16_3x3mm_P0.5mm` is the right envelope but is a *generic* pattern — verify against MEMSIC's land drawing before use. |
| **U10** | BMP390 | No Bosch LGA-10 2 x 2 in stock. `ST_HLGA-10_2x2mm_P0.5mm` matches size and pin count but is **ST's** land pattern, not Bosch's. Verify or author. |

### U7 DAN-F10N — authored, `ublox:ublox_DAN-F10N` [measured]

Authored from scratch; nothing comparable existed in stock. The land pattern is **not in the
datasheet** — u-blox puts it in the Integration Manual (UBXDOC-963802114-13252 R02), Figure 18 /
Table 27 (copper) and Figure 19 / Table 28 (paste). Both figures are bitmaps, so the geometry was
recovered by connected-component analysis of the rendered page and reconciled against the tables.

**Geometry.** 100 pads total: 56 numbered edge pads plus a 44-pad ground array.

| | Value | Source |
|---|---|---|
| Edge pad copper | 1.50 (radial) x 0.80 | Table 27 C, D |
| Edge pad pitch / count | 1.10, 14 per side, innermost at +/-0.55 | Table 27 G, I |
| Edge pad row offset | +/-8.95 from centre | Table 27 J |
| Inner pad copper | 1.10 square | Table 27 E |
| Inner grid | 1.90 pitch at +/-0.95, +/-2.85, +/-4.75, +/-6.65 | Table 27 F, H, K |
| Body / keepout | 20.0 x 20.0 / 21 x 21 | datasheet Fig 4 A; Fig 18 |

Minimum copper gap between pads is **0.300 mm** (1.10 pitch less 0.80 pad) — that is the tightest
feature on the board and it sets the fab class for this part.

**Two traps caught during authoring, both recorded because they nearly shipped:**

1. **Bitmap measurement inflates sizes but not distances.** Blob sizes fitted 130 px/mm exactly and
   self-consistently across three dimensions (1.50 / 1.10 / 0.80) — convincingly, and wrongly. Pitches
   and spans fitted 127.3. The anti-alias fringe inflates every blob by a constant absolute amount
   while leaving centroids untouched, so **distances are trustworthy and sizes are not**. Calibrating
   on distance (Table 27 J) made every remaining dimension land on its spec value and dropped the
   off-grid pad count to zero. The size-based fit was the instrument agreeing with itself.
2. **The two u-blox figures disagree on pin-1 orientation.** Datasheet Figure 3 puts pin 1 at the top
   of the left column; Integration Manual Figure 18's "Pin 1" leader lands on the leftmost pad of the
   *bottom* row — Figure 18 is drawn 90 deg CCW from Figure 3. The inner ground array is 4-fold
   symmetric and gives no orientation clue, so this would not have been caught by inspection. Both
   agree on the *relative* arrangement (CCW, 14/side), so either is buildable; **this footprint uses
   the Figure 3 orientation** (pin 1 top-left) to match the symbol and KiCad convention.

**Numbering** is CCW from top-left: left 1-14 top->bottom, bottom 15-28 L->R, right 29-42 bottom->top,
top 43-56 R->L. Verified against the symbol: 56/56 pins match, no gaps, no extras, zero pad overlaps.

**The 44 inner pads are unnumbered in Figure 3** but carry paste in Figure 19, so they are real module
contacts, not just recommended copper. They are assigned **pad number 1 (GND)** so they tie to the
ground net — the same convention KiCad's own libraries use for QFN thermal pads. Occupancy per row
(top to bottom) is 6/8/4/4/4/4/8/6.

**Paste is a documented approximation.** Table 28 wants edge apertures 1.45 x 0.70 from 1.50 x 0.80
copper — an *asymmetric* absolute reduction that KiCad's single-scalar `solder_paste_margin` cannot
express. Set to -0.05, which gives inner pads exactly 1.00 x 1.00 as specified and edge pads
1.40 x 0.70: the bridging-critical short axis is exact at the 1.10 pitch, and the long axis is 0.05 mm
conservative. Verified live via pcbnew (`GetSolderPasteMargin`) rather than assumed — a footprint-level
margin that KiCad ignored would have silently produced 1:1 paste. u-blox note the paste figures are
recommendations, not specifications.

**Still open:** no 3D model (u-blox does not publish a STEP for DAN-F10N in the assets fetched).
The module has an integrated patch antenna and a 21 x 21 keepout, so placement is constrained by
sky view, not just courtyard.

### Two assigned but provisional

- **Q1** — `SOT-23` is a **placeholder package only.** The OVP pass FET must still be selected on SOA
  (it dissipates (7.3 - 5.0) x I during a clamped surge), and the real part may well not be SOT-23.
- **L1 / L2** — packages chosen for the inductance and expected current, but **saturation current has
  not been checked** against 3 A load plus ripple.

## Not yet settled
- Whether the console UART gets a USB-serial bridge or a bare header.
- Board outline, connector placement, enclosure.
