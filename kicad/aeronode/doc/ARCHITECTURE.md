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

## ⚠ Hazard 1 — LiFePO4 charge voltage is 7.2 V, not 8.4 V

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

## Not yet settled

- PD sink target voltage — recommend 9 V (see budget).
- CAN FD or classic.
- Whether the console UART gets a USB-serial bridge or a bare header.
- Board outline, connector placement, enclosure.
