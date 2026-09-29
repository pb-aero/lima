# The A2B bus-coupling network — what is on the audio board, and where each value came from

**Date:** 2026-09-29 · **Agent:** LIMA · **Status:** design note. **Nothing measured on hardware.**
**Scope:** the A2B line interface on `kicad/audio-board` — U5's B-side, towards the earcups.
The transceiver decision is `docs/audio-board-decision-record.md` (Decision C); the schematic is
`kicad/audio-board/audio-board.kicad_sch`.

Provenance: `[fetched]` = read from the vendor PDF, page cited · `[transcribed]` = read off ADI's
eval-board drawing · `[repo]` = in this repository · `[derived]` = arithmetic shown ·
`[gap]` / `[assumed]` = **not established, do not build on it without checking**.

---

## 1. Where this circuit came from, and what that does *not* mean

`[fetched]` AD242x Rev. C p.33 is explicit that the public datasheet does **not** carry this circuit:

> *"Contact your local Analog Devices representative for the latest schematic circuit
> recommendations and bill of materials for each of these node configurations. The recommended
> circuit and component selection must be followed for A²B automotive-grade compliance."*

So there was no way to derive this from the datasheet, and inventing it from generic differential-
pair practice would have produced something that looks right and is not compliant.

`[transcribed]` What is on the board instead is a faithful read of **ADI's own master-node
evaluation board**: `EVAL-AD2428WD1BZ`, schematic Rev 1.1, board `A0983-2017`, **sheet 2 of 7**,
dated 5/17/18. Archived at `docs/datasheets/EVAL-AD2428WD1BZ_schematics.pdf`, checksum-pinned in
`scripts/fetch-datasheets.sh`. That board is a **master** node, which is what this board is — so the
B-side network transfers directly rather than by analogy.

> **The distinction that matters: an eval board is not ADI's issued recommendation.** This network is
> good enough to lay out and to reason about. It is **not** a compliance sign-off, and p.33 says the
> difference is real for automotive grade. **Review it with ADI before fab.**

## 2. The chain, chip to cable

```
U5 BP  (22) ─┬─ FB1 1000R ─── U5 BCM (24) ─── FB2 1000R ─┬─ U5 BN (23)
             ├─ C27 12pF ─────────────────────────────────┤
             └─ L1 180nH ─┬─ C28 27pF → AGND              └─ L2 180nH ─┐
                          └─ FL1 pin1        FL1 pin3 ─────────────────┘
                             (common-mode choke, 2600R @ 100 MHz)
             FL1 pin2 ─┬─ R8 120R ─┬─ C29 0.033uF → AGND     (split termination,
             FL1 pin4 ─┼─ R9 120R ─┘                          centre tap AC-grounded)
                       │
             FL1 pin2 ─┴─ C30 0.01uF ─┬─ A2B_LINE_P ─┬─ L3 3.3uH ── A2B_BIAS_P  [no source yet]
             FL1 pin4 ─── C31 0.01uF ─┼─ A2B_LINE_N ─┼─ L4 3.3uH ── A2B_BIAS_N ── U5 VSSN (26)
                                      │              ├─ C32/C33 0.033uF → AGND
                                      │              └─ C34 0.033uF across the pair
                                      └────────────────── J3 (2-pin, to the cups)
```

| Eval board | Ours | Value | Role |
|---|---|---|---|
| FER8 / FER9 | `FB1` / `FB2` | 1000 Ω @ 100 MHz | BP and BN to BCM |
| C64 | `C27` | 12 pF | across the pair |
| L2 / L3 | `L1` / `L2` | 180 nH | series, each line |
| C66 | `C28` | 27 pF | line+ to AGND |
| FER12 | `FL1` | 2600 Ω @ 100 MHz | common-mode choke |
| R17 / R18 | `R8` / `R9` | 120 Ω | split termination |
| C57 | `C29` | 0.033 µF | termination centre tap to AGND |
| C52 / C53 | `C30` / `C31` | 0.01 µF | AC coupling onto the line |
| C118 / C111 | `C32` / `C33` | 0.033 µF | line to AGND at the connector |
| C50 | `C34` | 0.033 µF | across the pair at the connector |
| L9 / L10 | `L3` / `L4` | 3.3 µH | DC bias injection |
| P2 (DuraClik) | `J3` | 2-pin | cable to the cups |

## 3. What was deliberately not copied

- **`C70` and `C72` are DNP** on the eval board. Omitted here rather than placed-and-disabled.
  Footprint them if EMC tuning later wants them.
- **The entire A-side network** (`AP`/`AN`/`ACM`, FER6/7, L4/L5, FER13, R19/R20, C42/C43…). `[fetched]`
  Table 15 p.26: transceiver A is *"directed towards the master."* **U5 is the master** — nothing sits
  upstream of it, so those pins stay unconnected on purpose, not by oversight.
- **The bus-power switch**: Q1 `BSS308PE`, D4 `ZLLS400`, D5 `CDBU0130L`, the R15/R16/R23/R30 +
  C58/C59/C60 `SENSE` divider, and D9 `TPSMF4L28A`. That circuit is how the master switches and
  senses power to downstream nodes, and it only resolves once §4.1 is decided. `SWP` and `SENSE`
  on U5 stay unconnected until then.

## 4. Open

### 4.1 Are the cups bus-powered or locally powered? — the gating question

This was already open (`docs/audio-board-decision-record.md` §6). It now gates two things at once:
the bus-power switch above, **and** the source for `A2B_BIAS_P`.

### 4.2 `[gap]` `A2B_BIAS_P` has no source

`L3`'s far end is deliberately dangling. On the eval board it comes off the switched bus-power rail
through Q1. **Note this does not go away if the cups turn out to be locally powered** — `[fetched]`
p.33 says the master *"must also supply bias voltage for line diagnostics"*, so something has to
drive that net either way.

`A2B_BIAS_N` **is** settled: `[fetched]` Table 15 p.26 says `VSSN` *"connect[s] to the inductor that
provides the negative bias for the next slave device"*, so `L4` → U5 `VSSN` is wired.

### 4.3 `[gap]` The termination is transcribed, not reconciled

It reads 120 Ω + 120 Ω in series across the pair — `[derived]` 240 Ω differential — with the centre
tap AC-grounded through `C29`. That is what the eval board draws. **I have not reconciled that
against the A2B line impedance**, and did not adjust it to match a number I expected. If it looks
wrong later, check the eval board before changing it; it is more likely my understanding is missing
something than that ADI's own master board is mis-terminated.

### 4.4 `[assumed]` `J3` is a placeholder connector

Generic 2-pin part standing in for the real cable connector. `[transcribed]` The eval board uses
Molex DuraClik. Pick the real part before layout.

### 4.5 Layout rules are not optional, and the schematic does not carry them

`[fetched]` AD242x Rev. C p.34, condensed — **read the page before routing**:

- Route `AP`/`AN` and `BP`/`BN` **symmetrically**; match parasitic C and L.
- **100 Ω ±10 %** differential (10–100 MHz) on **both** sides of the common-mode choke.
- Shield the pairs symmetrically with ground, **≥0.5 mm wide**, stitched generously to the plane.
- **No switching signals or power traces** next to or under `AP`/`AN`/`BP`/`BN`.
- Avoid trace stubs and asymmetry; route into and out of pads rather than branching.
- **Magnetically separate common-mode chokes by ≥2 mm**; no ground or signal on any layer beneath
  them, extended ≥2 mm from the pads.
- Place termination resistors **symmetrically and close to the chokes**.
- Solder the exposed paddle and stitch the ground plane; ≥3 mm spacing around A2B pin pairs on
  multi-pin connectors.

## Sources

- **AD242x datasheet Rev. C** — p.5 (I²C/BASE_ADDR), p.26–27 (Table 15 pin functions, `VSSN`,
  transceiver A/B direction), **p.33 (Designer Reference — the "contact your ADI rep" clause,
  Table 19 diode dependencies)**, **p.34 (Layout Guidelines)**.
- **EVAL-AD2428WD1BZ schematic Rev 1.1**, board A0983-2017, **sheet 2 of 7** — the source for every
  value in §2. Hand-downloaded (analog.com refuses automated fetch); checksum-pinned in
  `scripts/fetch-datasheets.sh`.
- `[repo]` `docs/audio-board-decision-record.md` (Decision C, §6 open items).

All datasheets restore or verify via `scripts/fetch-datasheets.sh`.
