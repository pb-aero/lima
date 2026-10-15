# Cup A board — first-pass schematic

**Status:** preliminary, not reviewed. First attempt at the per-cup ANC/DVNC codec board for
the **left earcup**, per the ruled allocation in `docs/two-adau1860-channel-allocation.md` §2
and `docs/audio-board-decision-record.md` Decision A/B.

## What's in this pass

- **U1 — ADAU1861** (not the 1860; same silicon, solderable package, ruled 2026-09-22).
- **MK1/MK2 — IM73A135V01** differential MEMS mics on AINP0/AINN0 (feed-forward) and
  AINP1/AINN1 (feedback/error), matching John's Rev G per-cup map.
- **J1 — boom mic input** on AINN2, single-ended, biased from the codec's own `CM` pin into
  AINP2 (same convention the existing `audio-board` project uses for its single-ended
  accelerometer inputs).
- **J2 — left earcup driver** on HPOUTP/HPOUTN, direct from the codec DAC.
- **J3 — power in**: 1V8 (digital/analog core), 3V3_MIC (mic bias), GND. Source TBD (open item
  below).
- Decoupling (100 nF ×2 + 10 µF) on the 1V8 rail, REG_EN tied low (external regulation, same
  as `audio-board`), PD tied high, ADDR0/ADDR1/SELFBOOT/ROM_BOOT_MODE tied low.
- SDA/SCL and both serial ports (SPT0/SPT1) are brought out as net labels only — reserved for
  the AD2428W A2B subnode link, not wired to an actual subnode yet (see open items).

ERC: 0 errors. 13 warnings, all expected — single-pin nets on the reserved SDA/SCL/I2S labels,
and three benign bidirectional-into-power-net warnings on the strap pins (SELFBOOT,
ROM_BOOT_MODE, PD), same pattern as the existing `audio-board` schematic.

## Explicitly NOT in this pass — real gaps, not decisions

- **No AD2428W A2B subnode.** This cup has no way to get on the bus yet. The audio board's
  `J3 (A2B_TO_CUPS)` connector needs a counterpart here.
- **No power delivery scheme.** Whether 1V8/3V3_MIC ride in on the A2B cable or a separate
  harness conductor is unresolved — J3 is a placeholder connector, not a decision.
- **Boom mic input is a guess.** Single-ended into AINN2/CM mirrors the codec's documented
  single-ended convention, but the actual source circuit (bias network, DC blocking) for the
  boom capsule isn't established for this cup — only the aircraft-side TX-select relay on
  `audio-board` is designed.
- **Earcup driver interface is direct**, no output network — impedance matching / AC coupling
  for the speaker element TBD.
- **No footprints assigned** — schematic only, nothing sent to PCB yet.

Next real step is probably resolving the A2B subnode + power question, since that gates
everything else about how this board actually gets built.
