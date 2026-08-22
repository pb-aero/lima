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

**The real cost is the PCB.** A 474-pad LGA on 1.27 mm pitch needs escape routing under the module —
realistically 8+ layers, likely via-in-pad — where the castellated part escapes around its perimeter
on 4. That is a board-cost and fabrication-capability decision, not a schematic one.

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

### Still to do on this sheet

- BQ25798 switching components: inductor, `BTST1`/`BTST2`, `SW1`/`SW2`, `PMID`, input/output bulk.
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

## Not yet settled
- Whether the console UART gets a USB-serial bridge or a bare header.
- Board outline, connector placement, enclosure.
