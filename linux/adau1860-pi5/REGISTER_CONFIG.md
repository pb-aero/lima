# ADAU1860 register configuration — the transport path

**Date:** 2026-09-02 · **Agent:** LIMA · source: **UG-2257, ADAU186x Hardware Reference Manual,
Rev. 0, 337 pp** (`md5 bcfaed19ba94c51385a0cc0c55b21696`)

## Read this before using any value below

You asked for a register dump for a working config. **What follows is not a dump.** A dump is
captured from silicon that is known to work; this is an init sequence *derived* from the hardware
reference manual, with every write traced to the register table it came from. **It has not been run
on hardware** — I have no route to your Pi. It is a sourced first draft to verify, not known-good
values, and I would rather hand you that with the label on it than something that looks
authoritative and is quietly wrong.

**It also stops at the transport layer, deliberately.** Clocks, power, and the serial port —
enough that data physically moves. It configures **no signal processing at all**. The FastDSP
program and the Tensilica DSP firmware are compiled by LARK Studio from a signal flow and loaded as
program/parameter memory images; there is no register sequence that substitutes for them. If you
want the DSP half, the fastest route by a wide margin is to build the flow in LARK Studio and export
its register sequence — which would also give you a genuine dump to check this against.

`scripts/`: [`adau1860_init.py`](adau1860_init.py) implements everything here, refuses illegal
combinations with the reason, and verifies every write by reading it back.

---

## 1. Control port — how you address anything

`[fetched]` UG-2257: *"The first byte (Byte 0) of a control port write contains the 7-bit IC address
plus R/W bit. The next four bytes (Byte 1 to Byte 4) are the 32-bit subaddress ... All subsequent
bytes (starting with Byte 5) contain the data."*

So a register write is **chip address, then a 4-byte register address, then data** — not the
one-byte subaddress most audio codecs use. Byte 0 comes from the kernel's I2C address, so from
userspace you send 4 address bytes + data.

`[fetched]` **I2C address is 7-bit**, formed as `1 1 0 0 1 ADDR1 ADDR0` (Table 22) giving
**0x64 / 0x65 / 0x66 / 0x67** (Table 23). This confirms the `[derived]` conclusion in
[NOTES.md](NOTES.md) §3 — it is now sourced, not reasoned.

Two things I could not confirm from the manual, both flagged in the script and both settled by the
first successful ID read:

- **`[derived]` Subaddress byte order is big-endian** (MSB first). ADI convention, and consistent
  with the figures labelling SUBADDRESS BYTE1..BYTE4 in descending significance.
- **`[derived]` The `0x4000Cxxx` block is byte-wide.** UG-2257 says registers are 4 bytes wide
  *"except the AON registers which is 1 byte width"*, and every reset value in this block is quoted
  as two hex digits (`0x41`, `0xC8`) where the `0x40000000` DMA block quotes eight (`0x00130000`).

**Prove both at once before anything else:**

| Register | Address | Expect |
|---|---|---|
| `VENDOR_ID` | `0x4000C000` | `0x41` |
| `DEVICE_ID1` | `0x4000C001` | `0x60` |
| `DEVICE_ID2` | `0x4000C002` | `0x18` |
| `REVISION` | `0x4000C003` | `0x01` |

`0x60 0x18` reads as **1860**. If those four come back right, your framing is correct and the two
`[derived]` assumptions above are confirmed. If they don't, suspect the framing before the chip.

```bash
sudo python3 adau1860_init.py --bus 1 --addr 0x64 --probe
```

## 2. The clock menu — this changes the design

**This is the finding that revises my earlier advice.** I told you to set fS equal to your
accelerometer ODR. That only holds if the ODR is on a fixed menu, because the ADAU1860's generators
are not arbitrary:

`[fetched]` **LRCLK** (Table 278, `SPT0_LRCLK_SRC[3:0]`) — `0000` means *take it from outside*;
otherwise you get exactly one of:

> **8, 12, 16, 24, 48, 96, 192, 384, 768 kHz**

`[fetched]` **BCLK** (Table 277, `SPT0_BCLK_SRC[2:0]`) — `000` means external; otherwise exactly:

> **3.072, 6.144, 12.288, 24.576 MHz**

Master mode *is* simply "generate rather than accept" on these two fields. There is no separate
master/slave bit.

Since BCLK must equal `fS × slots × slot_width`, and Linux independently restricts you to 2/4/6/8
slots, only these combinations exist at 32-bit slots — `[derived]`, arithmetic over both menus:

| fS | slots | BCLK/frame | BCLK | `BCLK_SRC` | `LRCLK_SRC` |
|---|---|---|---|---|---|
| 12 kHz | 8 | 256 | 3.072 MHz | `001` | `0100` |
| 16 kHz | 6 | 192 | 3.072 MHz | `001` | `1001` |
| 24 kHz | 4 | 128 | 3.072 MHz | `001` | `0101` |
| 24 kHz | 8 | 256 | 6.144 MHz | `010` | `0101` |
| **48 kHz** | **4** | **128** | **6.144 MHz** | **`010`** | **`0001`** |
| 48 kHz | 2 | 64 | 3.072 MHz | `001` | `0001` |
| 48 kHz | 8 | 256 | 12.288 MHz | `011` | `0001` |
| 96 kHz | 2 / 4 / 8 | 64 / 128 / 256 | 6.144 / 12.288 / 24.576 MHz | `010`/`011`/`100` | `0010` |
| 192 kHz | 2 / 4 | 64 / 128 | 12.288 / 24.576 MHz | `011`/`100` | `0011` |
| 384 kHz | 2 | 64 | 24.576 MHz | `100` | `0110` |

**8 kHz and 768 kHz are unreachable** at 32-bit slots: 8 kHz would need 12 slots and 768 kHz would
need fewer than 2, and Linux caps you at 8. **44.1 kHz and its family do not exist on this part at
all** — the menu is entirely 48 kHz-derived.

**Consequence for you: pick your accelerometer ODR from that first column**, or accept that the
sample rate and the ODR are different numbers and deal with the reconciliation in your framing.
Do not plan around an arbitrary ODR.

## 3. The register writes

For the recommended **TDM4, 32-bit slots, fS = 48 kHz, BCLK 6.144 MHz, codec master**:

| Address | Name | Value | Derivation |
|---|---|---|---|
| `0x4000C00E` | `CHIP_PWR` | `0x07` | `MASTER_BLOCK_EN`=1 (bit 2), `PWR_MODE`=`11` Active (Table 135) |
| `0x4000C007` | `SAI_CLK_PWR` | `0x01` | `SPT0_IN_EN`=1 (bit 0) — the codec's **input** side, because the Pi transmits into it. `0x03` if you also need SPT0 output (Table 128) |
| `0x4000C0E0` | `SPT0_CTRL1` | `0x01` | `SAI_MODE`=1 TDM (bit 0); `SLOT_WIDTH`=`00` 32 BCLK/slot (bits 5:4); `DATA_FORMAT`=`000` I2S delay-by-1 (bits 3:1); `TRI_STATE`=0 (Table 276) |
| `0x4000C0E1` | `SPT0_CTRL2` | `0x02` | `BCLK_SRC`=`010` generate 6.144 MHz → **master**; `BCLK_POL`=0 capture on rising (Table 277) |
| `0x4000C0E2` | `SPT0_CTRL3` | `0x01` | `LRCLK_SRC`=`0001` generate 48 kHz → **master**; `LRCLK_POL`=0 normal (Table 278) |

### Two you must decide, that I will not guess for you

**`CLK_CTRL1` (`0x4000C010`, reset `0xC8`)** carries `XTAL_MODE` at bit 3, and its **reset value has
it set to 1 = crystal oscillator**. If your board feeds MCLKIN a logic-level clock from an
oscillator can — which is what ADI's own eval board does with its 24.576 MHz part — **you must clear
bit 3**, giving `0xC0`. If a crystal is fitted across the pins, leave the reset value alone. I do
not know which your board has, and getting this wrong means no clocks at all. `PLL_SOURCE[2:0]`=`000`
(MCLKIN/XTAL) is already correct at reset.

**`PLL_PGA_PWR` (`0x4000C005`, reset `0x02`)** — **`[gap]`**. I did not extract its bit descriptions.
If the PLL needs explicit enabling for your MCLK ratio, it is here. Running the serial port straight
off a 24.576 MHz MCLK may bypass the PLL entirely, in which case reset is fine. Check Table 126-ish
before you conclude the chip is dead.

## 4. What is deliberately absent

- **Any signal processing.** No FastDSP program, no TDSP firmware, no filters, no gains. See the
  top of this file.
- **Input routing into the DSP.** There is no `FDSP_ROUTE` register — I checked every routing
  register in the manual and the set is `SPT0/1_ROUTE0-15` (serial port *output* slots),
  `FINT_ROUTE0-7`, `FDEC_ROUTE0-7`, `ASRCI/ASRCO_ROUTE*`, `DAC_ROUTE0`, `PDM_ROUTE*`, `EQ_ROUTE`.
  The path from a serial port input into FastDSP goes through an **interpolator or decimator**
  (`FINT_ROUTE*` sources are literally "Serial Port 0 Channel 0..15"), which is a rate-converting
  filter. This is the concrete form of the warning in [DATA_OVER_I2S.md](DATA_OVER_I2S.md) §9, and
  it is the datasheet's own documented path: *"SDATAI_x to Interpolator to FastDSP"*.

  **So getting your samples into the DSP unfiltered is the open engineering question**, not a
  configuration detail. If the interpolator cannot be bypassed when input and DSP rates already
  match, that constrains the whole design and is worth settling early — in LARK Studio, or with ADI
  on EngineerZone.

## 5. Verify, in this order

```bash
sudo python3 adau1860_init.py --bus 1 --addr 0x64 --probe          # framing + chip alive
sudo python3 adau1860_init.py --bus 1 --addr 0x64 --fs 48000 --slots 4          # dry run
sudo python3 adau1860_init.py --bus 1 --addr 0x64 --fs 48000 --slots 4 --apply  # write + read back
```

Then **scope BCLK and FSYNC**. The Pi cannot tell you whether the codec is clocking — in consumer
mode the driver never checks the rate against the wire ([DATA_OVER_I2S.md](DATA_OVER_I2S.md) §7).
Only after the clocks are confirmed does loading the overlay and pushing a ramp mean anything.
