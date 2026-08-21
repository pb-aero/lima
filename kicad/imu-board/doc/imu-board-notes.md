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
