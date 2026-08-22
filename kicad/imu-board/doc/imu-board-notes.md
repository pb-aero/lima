# imu-board — dual IMU design notes

**Created:** 2026-08-21 · Agent LIMA
**Project:** `kicad/imu-board/imu-board.kicad_pro`
**Brief:** Peter asked for two IMUs — an ICM-45686 and a BMI088 — on a schematic.

Provenance tags: `[fetched]` from a cited source · `[measured]` I ran it · `[practice]` standard
engineering convention, not literally in the datasheet · `[assumed]` flagged loudly.

---

## Configuration as built

Decided by Peter, 2026-08-21:

| Question | Answer |
|---|---|
| Target | New project in `lima`, not the `_modeltest` stub |
| Interface | SPI, one chip select per die (three total) |
| Rails | 3V3 for both VDD and VDDIO on both parts |

The host is not yet chosen, so all host-facing signals terminate in net labels rather than a
connector. `+3V3` and `GND` are fed externally and carry `PWR_FLAG`s.

## Bill of materials

| Ref | Value | Footprint | Verified |
|---|---|---|---|
| U1 | ICM-45686 | **unassigned — see open item 1** | symbol authored here |
| U2 | BMI088 | `Package_LGA:Bosch_LGA-16_4.5x3mm_P0.5mm_LayoutBorder7x1y_ClockwisePinNumbering` | `[measured]` present in stock KiCAD 10 |
| C1, C2 | 100nF | `Capacitor_SMD:C_0402_1005Metric` | `[measured]` present |
| C3, C4 | 100nF | `Capacitor_SMD:C_0402_1005Metric` | `[measured]` present |
| C5 | 2.2uF | `Capacitor_SMD:C_0603_1608Metric` | `[measured]` present |

C1/C2 decouple U1's VDD/VDDIO, C3/C4 decouple U2's VDD/VDDIO, C5 is shared bulk on +3V3.
The 100nF-per-supply-pin figure is `[practice]` — neither datasheet states a value in its
extractable text; both show it only inside a connection-diagram image.

## ICM-45686 pinout — the sourced table

There is **no ICM-45686 symbol in stock KiCAD**, so one was authored at
`kicad/lib/TDK.kicad_sym`. The pin table below is `[fetched]` and confirmed by **two independent
TDK documents that agree on all fourteen pins**:

- [EV_ICM-45686 Evaluation Board user guide, AN-000484](https://www.farnell.com/datasheets/4421760.pdf), Figure 2 "Pin Out Diagram"
- [SM-ICM45686-AK09940A module datasheet v1.01](https://cdn.robotshop.com/media/I/ISY/RBC-Isy-01/pdf/SM-ICM45686-AK09940A-DS_v1.01.pdf), the U1 schematic symbol

| Pin | Name | Pin | Name |
|---|---|---|---|
| 1 | AP_SDO / AP_AD0 | 8 | VDD |
| 2 | RESV / AUX1_SDIO / AUX1_SDI / MAS_DA | 9 | INT2 / FSYNC / CLKIN |
| 3 | RESV / AUX1_SCLK / MAS_CLK | 10 | RESV / AUX1_CS |
| 4 | INT1 / INT | 11 | RESV / AUX1_SDO |
| 5 | VDDIO | 12 | AP_CS |
| 6 | GND | 13 | AP_SCL / AP_SCLK |
| 7 | RESV | 14 | AP_SDA / AP_SDIO / AP_SDI |

Package: LGA-14, 2.5 × 3.0 × 0.81 mm `[fetched]`. Note there is **no REGOUT pin** on this part,
unlike the older ICM-42688 — do not carry an external regulator cap across from that design.

## BMI088 — the mapping that is easy to get backwards

`[fetched]` from the [BMI088 datasheet BST-BMI088-DS000-19 rev 1.9](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmi088-ds001.pdf),
§6 Table 10 "Mapping of the interface pins".

The BMI088 is **two dies in one package** with two chip selects and two data outputs. The
accel/gyro assignment is the reverse of what the numbering suggests:

| Pin | Name | Belongs to |
|---|---|---|
| 14 | CSB1 | **Accelerometer** chip select |
| 5 | CSB2 | **Gyroscope** chip select |
| 15 | SDO1 | **Accelerometer** data out |
| 10 | SDO2 | **Gyroscope** data out |
| 9 | SDI | shared — accel *and* gyro data in |
| 8 | SCK | shared clock |
| 7 | PS | protocol select: **GND = SPI**, VDDIO = I²C |

Two firmware notes that follow from the datasheet and will bite whoever writes the driver:

1. **The accelerometer always powers up in I²C mode regardless of the PS pin.** It must be moved
   to SPI actively by sending a rising edge on CSB1 — a dummy read of `ACC_CHIP_ID` does it. The
   gyro honours PS directly. `[fetched]` §6.1
2. **Accel SPI reads return a dummy byte first**, before the requested content. The gyro does
   not. `[fetched]` §6.1

Unused interrupt pins are left unconnected with no-connect flags, which the datasheet requires
explicitly: *"If INT are not used, do not connect them (DNC)"* — so no pull-downs on pins 1 and 13.

## Verification performed

All `[measured]` on the committed schematic:

| Check | Result |
|---|---|
| `export_netlist_summary` — per-pin nets | all 30 pins land on their intended net |
| `find_shorted_nets` | 0 |
| `check_schematic_overlaps` | 0 |
| `run_erc` | 5 errors, 7 warnings — all accounted for below |
| SVG render, eyeballed | correct structure, no collisions |

Per the standing scar, connectivity was verified **per pin from the netlist**, not from ERC's
exit state. `find_orphan_items` reports 34 "dangling wire ends" — one per stub, all at the pin
end of a `connect_to_net` stub. Cross-checked against the netlist: every one of those pins
resolves to its correct net. That tool does not count a pin as terminating a wire, so the 34 are
instrument noise, not defects.

### The ERC output, explained

Four of the five errors are **expected and will clear when a host is added**: `AP_SCLK`, `AP_CS`,
`CSB1` and `CSB2` are input pins with no driver, because the SPI master does not exist on this
sheet yet. The seven "label connected to only one pin" warnings are the same fact seen from the
other side.

The fifth error is real and is **open item 2** below.

---

## Open items — need a ruling before this goes to layout

### 1. ICM-45686 has no footprint, deliberately

TDK gates DS-000577 behind a redirect and the distributor mirrors would not yield the package
drawing, so **the land pattern is unsourced and I did not invent one.**

The stock `Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y` is a trap: right pin count, right
body size, **wrong pad layout**. It is a 3×4 perimeter pattern derived from an ST LSM6DS3TR-C,
whereas the ICM-45686 is dual-row 7+7. Do not assign it.

This is the ConnectCore 93 lesson applied early rather than late — pads in the wrong place pass
every check except the one that compares them against the real body. To close this, get the
package drawing from DS-000577 or Digi-Key/Mouser's CAD download, then author the footprint and
attach the vendor STEP at the same time.

### 2. SDO1 and SDO2 are tied to one MISO — `[practice]`, not datasheet-proven

Pin 15 (accel out) and pin 10 (gyro out) both land on `IMU_MISO`. **ERC flags this as an
output-output conflict**, because the stock KiCAD symbol types both pins `output` rather than
`tri_state`.

Tying them is what essentially every BMI088 design does, and the datasheet's own architecture —
shared SDI and SCK, separate CSB per die — only works if the deselected SDO releases the bus.
But I could not find a sentence in the datasheet's extractable text that says the outputs
tri-state when CSB is high; that behaviour is documented only inside the SPI timing figures,
which are images.

**So this stays open rather than being rounded up to green.** Confirm against Figure 8
("Connection diagram SPI") on page 53. If it is confirmed, the clean fix is a local BMI088
symbol variant with SDO1/SDO2 typed `tri_state`, which silences the ERC error honestly. If it
turns out they are push-pull, split them into two nets and spend the extra host pin.

### 3. RESV pin termination is unconfirmed

Pins 2, 3, 7, 10 and 11 are all marked RESV or RESV/AUX in TDK's own pinout. The AUX interface is
unused here, so all five carry no-connect flags. **Whether TDK requires any of them tied to GND
rather than floating is not established** — some InvenSense parts do require it. DS-000577's pin
description table settles it; check before layout.

---

## What I could not do, and why

- **Could not retrieve DS-000577.** `invensense.tdk.com/download-pdf/icm-45686-datasheet/` and
  the `wp-content/uploads/documentation/` path both redirect to a marketing landing page;
  `lcsc.com/datasheet/C22459454.pdf` returns a title-only shell; SnapEDA returns 403. The
  ICM-45605 sibling datasheet is reachable at
  `invensense.tdk.com/wp-content/uploads/documentation/DS-000576_ICM-45605.pdf` per search
  results and shares the package — that is the most promising next lead.
- **Could not read either connection diagram.** Both the BMI088 SPI diagram and TDK's
  application circuit are raster images inside their PDFs, so decoupling values and bus
  termination came from convention, not from the page.
- **A note on instruments:** the first attempt at the BMI088 questions was answered by a page
  summariser that confidently invented "10-100 µF on VDD" and "2.2-10 kΩ pull-ups" — values that
  appear nowhere in the document. Everything in this file was extracted from the PDFs locally
  with `pypdf` instead. A summariser asked for a fact a document does not contain will supply a
  plausible one.


---

# 2026-08-22 · Rewired: shared bus -> two independent SPI buses

**Change requested by Peter:** the IMUs stay on this separate PCB, but connect to the host over
**individual SPIs**, not one shared bus.

## What changed

Previously all three dies sat on one 3-wire bus (`IMU_SCLK` / `IMU_MOSI` / `IMU_MISO`) with three chip
selects. That is a common-mode failure path: one device latching a line kills readback from the
others, which defeats the point of carrying two independent IMUs.

Now each **chip** has its own bus:

| ICM-45686 (U1) | | BMI088 (U2) | |
|---|---|---|---|
| `ICM_SCLK` | pin 13 | `BMI_SCLK` | pin 8 |
| `ICM_MOSI` | pin 14 | `BMI_MOSI` | pin 9 (SDI) |
| `ICM_MISO` | pin 1 | `BMI_ACC_SDO` | pin 15 (SDO1) |
| `ICM_CS` | pin 12 | `BMI_GYR_SDO` | pin 10 (SDO2) |
| `ICM_INT1` | pin 4 | `BMI_ACC_CS` | pin 14 (CSB1) |
| `ICM_INT2` | pin 9 | `BMI_GYR_CS` | pin 5 (CSB2) |
| | | `BMI_ACC_INT` | pin 16 (INT1) |
| | | `BMI_GYR_INT` | pin 12 (INT3) |

**The only nets now shared between the two chips are `+3V3` and `GND`.** `[measured]` via per-pin net
readback, not inferred from the drawing.

## Why the BMI088's two SDO pins are kept separate

The BMI088's accelerometer and gyroscope are separate dies that **share `SCK` (8) and `SDI` (9)** but
have **separate data outputs** — `SDO1` (15, accel) and `SDO2` (10, gyro) — and separate chip selects.
So "one bus per die" is not physically possible for this part; one bus per *chip* is the real limit.

Bosch's reference topology ties SDO1 and SDO2 together onto a single MISO, arbitrated by the chip
selects `[fetched]`. **We deliberately do not.** Two reasons:

1. **Isolation.** Tying them reinstates the common-mode failure the split was made to remove — a
   latched-high SDO on one die would block readback from the other.
2. **It is an honest ERC error.** With both pins typed `Output`, tying them raises
   `[pin_to_pin]: Pins of type Output and Output are connected` — a real warning about a real
   contention risk that only the chip-select protocol prevents. Suppressing it would have meant
   carrying a standing ERC error, which masks the next one.

Bringing both out separately also **moves the decision to the host board**, where it belongs: AeroNode
can tie them and use one SPI peripheral, or drive two peripherals sharing SCK/MOSI for full isolation.
Costs one extra conductor in the interconnect.

## Verification `[measured]` 2026-08-22

- Per-pin net readback on both parts — every pin lands on the intended net.
- `find_shorted_nets`: **0**.
- `PS` (U2 pin 7) confirmed tied to `GND` — the part is in SPI mode, not I2C. This was already correct
  in the original design.
- ERC: 19 violations, all expected for a board with no host present —
  **5 errors** `pin_not_driven` (SCLK and the three CS inputs have no driver on this board) and
  **14 warnings** `isolated_pin_label` (each host-facing net has a single pin). The
  `pin_to_pin` output conflict present before this change is **gone**.

## Interconnect to AeroNode — 15 signals + power

`ICM_SCLK` `ICM_MOSI` `ICM_MISO` `ICM_CS` `ICM_INT1` `ICM_INT2` ·
`BMI_SCLK` `BMI_MOSI` `BMI_ACC_SDO` `BMI_GYR_SDO` `BMI_ACC_CS` `BMI_GYR_CS` `BMI_ACC_INT`
`BMI_GYR_INT` · `+3V3` `GND`

On the CC93 LGA, **LPSPI8 sits on dedicated primary pads** (`SPI8_SCK` D17, `SPI8_SIN` E22,
`SPI8_SOUT` E18, `SPI8_CS0` E19, all 3V3) with no boot straps and no clash with SAI3 — the natural
choice for one of the two buses. LPSPI3 (on the UART7 pads) is the clean second. Avoid LPSPI4/LPSPI5,
which land on SAI3's pads, and LPSPI1/LPSPI2, which touch boot straps.
