# status — Agent LIMA

**Updated:** 2026-08-21

## Where things stand

Onboarding complete per `aero-ssh-bridge/ONBOARD_PROMPT.md`. Phases A, B and C run. INDIA's
welcome message answered and closed.

- **Phase A** — SSH key created and registered (`~/.ssh/id_ed25519`, `pb-aero`); brain template
  v2.0 installed as `CLAUDE.md`; `.agent/` scaffold from `bootstrap-agent.sh`; WHOAMI filled in.
- **Phase B** — read all five STANDING memos, `WORKFLOW.md`, `ACCESS.md`, `reports/README.md`,
  `reports/REPORT_STATUS_BANNER.md`. No bridge needed — Claude Code is terminal-capable.
- **Phase C** — self-test 15 pass / 1 fail / 1 warn (14 in the landed table; the push that lands
  the report cannot count itself). Report at `reports/peter/LIMA_access_check.md`.

## Repo state, verified at full length

- `pb-aero/lima` — `6dcf33520d05b781d3b3e97c5c83b1f32365d36a` `[measured]`
- `Aerosense-Dev-Team-Sync` main — `8ce92910970dad4e3d8e8895abe6130f692714e8` `[measured]`

## Correspondence

- **IN** `inbox/peter/2026-08-20-001` from INDIA — welcome + two asks. **status: answered.**
- **OUT** `peter/outbox/2026-08-20-001_onboarding-findings-macos.md` — six findings from the cold
  macOS read. Delivered as `inbox/chris/2026-08-20-004`.
- **OUT** `peter/outbox/2026-08-20-002_permission-net-verified.md` — guard proven by positive
  control. Delivered as `inbox/chris/2026-08-20-005`.

## Closed this session

- **Permission net installed and PROVEN.** `lima/.claude/settings.json` per INDIA's spec. All three
  positive controls refused: `git commit -am`, `git add -A`, `git push --force`. Negative control
  passed — plain `git push`, `add <path>`, `commit -m`, `status`, `log`, `ls-remote` all work.
  `[measured]` **It took effect mid-session — no restart needed, contrary to the instruction.**
- **Nothing stranded.** Working tree clean, local == remote on both repos.

## Open

1. **No read access to `aerosense-ops`** — `Repository not found`. Duran grants it. INDIA confirms
   it blocks all three team agents (me, KILO, JULIETT). **Do not start work that depends on ops.**
   This is the one self-test failure; check 7 stays a WARN until it clears, and a skipped check is
   not a pass.
2. **Off-switch gap, raised with INDIA, not yet ruled.** The shipped `settings.json` has no
   `Edit(///...settings.json)` deny, so nothing stops an agent rewriting its own guards — which
   `CLAUDE.md` §6 calls the single most important rule. Left unpatched deliberately: a fleet-wide
   rule beats a local variation. Chase if no answer.
3. **Remit is `[assumed]`** in WHOAMI — Peter has not set one. Narrow it and drop the tag.

## Next session

Read `inbox/peter/` and `memos/` first. Then, while ops is still blocked, the useful work is
reading: start at any `MANIFEST.md`, and `git grep -il '<term>' -- reports/ chris/ john/` before
asking anything — re-derivation is the most expensive failure this project has measured.


---

## 2026-08-21 · ConnectCore 93 footprint — 3D model attached

Peter asked whether a 3D model could go on the CC93 footprint. It can, and doing it found a bug.

- **Done.** Digi's STEP is attached to `Digi_ConnectCore93_Castellated` at offset
  `(-20, -22.5, 1.547)`, verified by headless `kicad-cli pcb render`. Renders committed at
  `kicad/lib/doc/`. STEP is gitignored (13 MB); `scripts/fetch-3d-models.sh` restores it with both
  checksums pinned — tested with positive and negative controls. Commit `23727c9`, push verified.
- **Digi's portal is not gated.** No login, no licence click-through; `/dp/path=/support/asset/...`
  returns the zip. Three assets pulled: SoM 3D model, host-PCB footprint drawing, Altium SchLib/PcbLib.

### Closed later the same day — geometry sourced and fixed (commit `bb463d6`)

1. **Pad geometry FIXED and sourced.** `33,56` is the **host PCB cutout width**, not the pad span —
   that one misread is the whole bug. From HRM 90002549 rev 4P p.83, measured by projection profile
   and cross-checked against four of the drawing's own labels: columns now **x = +/-20.000**, rows
   **y = +/-22.500**, body **40 x 45**. All four runs straddle the edge by exactly 1.000 mm, matching
   DETAIL A's `1` — an agreement I did not aim for. 118 pads, 0 overlaps, DRC 0 violations.
   The earlier `[derived]` guess of +/-19.725 was close but wrong; good thing it was not applied.
2. **Keepout MARKED** on `Dwgs.User`: Digi's dimensioned cutout **33.56 x 20.86 centred** (build to
   this), plus the measured protrusion envelope as a thin reference rect.
3. **Digi's Altium `CC93_DVK.PcbLib` does not cover this part** — 474-pad LGA array, different
   variant. Do not retry it. But noted for reuse: **KiCad ships an Altium importer callable from its
   own Python** (`pcbnew.PCB_IO_MGR.FindPlugin(...ALTIUM_DESIGNER)`), so no OLE parsing needed.

### Open

4. **Digi ships the wrong document** under "ConnectCore 91 and 93 host PCB footprint and cutout" —
   the zip contains ConnectCore **8X** files dated 2022. Worth reporting to Digi.
4. Still outstanding from the earlier session: `NVCC_SD2`/`1V8` typed `bidirectional` should be
   `power_in`; symbol Footprint/Datasheet/Description properties empty.


### Not mine — flagged, untouched

`kicad/imu-board/` and `kicad/lib/TDK.kicad_sym` appeared untracked in the working tree during this
session; they were not there at boot and are not my work. **Left alone, not staged.** Another session
is live in this checkout — check before assuming the tree is yours.

---

## 2026-08-21 · imu-board — two IMUs added (ICM-45686 + BMI088)

Peter asked for an ICM-45686 and a BMI088 on "my kicad schematic". There wasn't one — the only
`.kicad_sch` in the repo was the empty 9-line `_modeltest` stub — so this is a new project.
Peter ruled: new project in lima, SPI with one CS per die, 3V3 for both VDD and VDDIO.

- **Done.** `kicad/imu-board/` created. U1 ICM-45686 (symbol authored at `kicad/lib/TDK.kicad_sym`,
  registered project-scoped), U2 BMI088 (stock `Sensor_Motion:BMI088`), C1-C5 decoupling,
  PWR_FLAGs on both rails. Shared SPI bus, three chip selects, four interrupts brought out to
  labels. Netlist verified per pin — all 30 land correctly. 0 shorts, 0 overlaps.
  Notes at `kicad/imu-board/doc/imu-board-notes.md`.
- **ICM-45686 pinout is solid** — `[fetched]` from two independent TDK documents that agree on
  all 14 pins (EVB guide AN-000484 Figure 2, and the SM-ICM45686 module datasheet's U1 symbol).

### Open — needs Peter's ruling before layout

1. **U1 has no footprint, deliberately.** DS-000577's package drawing could not be retrieved
   (TDK redirects to marketing; LCSC serves a title-only shell; SnapEDA 403s). The stock
   `LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y` is a **trap** — right size and pin count, but a 3x4
   perimeter pattern from an ST part where the ICM-45686 is dual-row 7+7. Best next lead: the
   ICM-45605 sibling datasheet `DS-000576`, same package, reportedly reachable.
2. **SDO1+SDO2 tied to one MISO is `[practice]`, not proven.** ERC flags output-output. Standard
   in every BMI088 design and implied by the datasheet's shared-SDI/separate-CSB architecture,
   but the tri-state sentence lives only in an image (Figure 8, p53). Held open, not rounded to green.
3. **RESV termination unconfirmed** — U1 pins 2,3,7,10,11 are no-connected; some InvenSense parts
   require RESV tied to GND. DS-000577's pin table settles it.

Four of the five ERC errors are just "input pin not driven" on SCLK/CS — the host doesn't exist
on the sheet yet. They clear when a host or connector is added.

## 2026-09-04 · ArduPilot installed on scopenode — DONE

Peter: *"install ardupilot for linux on the pi"*. Delivered and verified on hardware.

- **Built and running.** `arduplane V4.8.0-dev (ff37fde6)`, native aarch64, at
  `node@scopenode.local:~/ardupilot/build/linux/bin/arduplane`. `./waf configure --board=linux`
  + `./waf plane`, 4m52s. `[measured]`
- **Peter's rulings this session:** bare Pi 5 (no HAT) so `--board=linux`; `plane` only;
  **accept kernel 6.18.39** rather than roll back.
- **Kit:** `linux/ardupilot-pi5/` — `install_ardupilot.sh` (preflight/clone/prereqs/build/verify),
  `NOTES.md` (upstream analysis), `RESULTS-2026-09-04.md` (what actually happened).

### Carried forward — needs action before the ADAU1860 work is trusted again

**`scopenode` will boot kernel 6.18.39+rpt-rpi-2712 at the next restart** (was 6.12.47). Pulled in
as an apt dependency of `g++-arm-linux-gnueabihf`, which the ArduPilot prereqs script installs
unconditionally and which this build never uses. Running kernel is still 6.12.47 — the change is
latent, not active.

Everything in `linux/adau1860-pi5/` — the RP1 I2S clock-direction findings, the 4-lane duplex
bring-up, the register work — was measured on 6.12.47. **Re-verify on 6.18.39 after the next
reboot before building on any of it.** Device-tree node names, `dwc-i2s` behaviour and overlay
compatibility all sit on that version.

### Open

1. `[gap]` The 6.18.39 re-verification above. Not started; needs a reboot Peter chooses.
2. Upstream bug found, not reported: `Util_RPI.cpp:62` uses `strncmp(d_name, "soc", 4)`, an exact
   match where a prefix match was intended, so Pi 5 detection fails on kernels that name the node
   `soc@107c000000`. Harmless for `--board=linux` (GPIO_RPI not compiled) but an `AP_HAL::panic`
   at startup for `navio2`/`pilotpi`/`navigator64`. One-character fix. Worth a PR if Peter wants it.

## 2026-09-04 (later) · ArduPilot: EKF3, upstream PR, published to the shelf

Continued from the entry above. Peter's interest narrowed to **EKF3 as their own AHRS**; he then
left and asked for the findings to be published.

- **PUBLISHED.** `reports/peter/LIMA_ardupilot_pi5.html` + MANIFEST row, landed at
  `Aerosense-Dev-Team-Sync@2d37466`. Banner CURRENT, record `4c2dcad`, source `lima@c57e276`.
  **This closes both open inbox items** — `2026-09-01-001` ("publish your work, the shelf is
  empty") and `2026-08-26-002` ("rule 7a is not yours, you must push to sync"). Neither has been
  answered in `peter/outbox/` yet.
- **Upstream patch ready, PR NOT filed.** `Util_RPI.cpp` strncmp fix, proven on hardware with a
  matched pair (aborts vs runs). Needs a browser session and a fork; no `gh` in this fleet.
  Four commits sit on branch `pi5-board` in `~/ardupilot` on scopenode.
- **Sensors found and declared:** MPU-9250 `i2c-2 0x68`, LPS22HB baro `0x5c`, AK8963 compass.
  A `pi5` board target now exists with a GPS-free EKF3 source set baked into ROMFS.

### Open — blocking, needs hands on the rig

1. **IMU FIFO stall.** ArduPilot startup halts at `MPU: temp reset IMU[0] <n> 0` — the FIFO returns
   zeros — and never reaches `ArduPilot Ready`. Sensor, chip state, bus contention, intermittency
   and bus speed all ruled out by measurement; `defaults.parm` ruled out by bisect; the rotation
   change ruled out by code path. **No software change explains it.** Next: power-cycle the sensor
   rail, inspect the physical I2C wiring. Everything in the EKF3 section is unverified until this
   clears.
2. **Accel + compass calibration** — needs the board physically rotated.
3. **~15 deg residual mounting angle** after the 180 deg flip — bench tilt or real mounting angle,
   needs eyes on it.
4. **Pixhawk 6C never enumerated** — 45-min watch expired, no USB event ever. Likely a charge-only
   cable. Moot for the AHRS path: ArduPilot has no MAVLink IMU input at all.

---

## 2026-09-07 · scopenode rebooted onto 6.18.39 · ADAU1860 is NOT connected

Peter asked "can you connect to the adau1860". Probed the rig; the answer is no, and two facts
changed underneath it.

- **The latent kernel change has landed.** `uname -r` = **`6.18.39+rpt-rpi-2712`** `[measured]`
  (was 6.12.47). `uptime` showed `up 0 min` — the machine had just been powered on. Open item 1
  from 2026-09-04 is no longer *waiting on a reboot Peter chooses*; the reboot happened, so
  **re-verifying `linux/adau1860-pi5/` on 6.18.39 is now due, not blocked.**
- **The ADAU1860 does not answer on I2C.** `i2cdetect -y 1` is completely empty `[measured]`;
  the part's address range is 0x64-0x67 (ADDR1/ADDR0 pins) and nothing is there.
  **Positive control passed:** bus 2 shows `0x5c` (LPS22HB) and `0x68` (MPU-9250), so i2cdetect,
  sudo and the I2C stack are all working. Buses 13/14 answer at every address — HDMI DDC, noise.
- **The Pi is no longer configured for it either.** `dtparam=i2s=on` is commented out in
  `/boot/firmware/config.txt` (line 7) and no `adau1860-pi5-*` overlay is loaded. GPIO18-21 read
  `no` function, pull-down, low `[measured]` — and GPIO19 is **not** self-toggling, unlike the
  2026-09-03 measurement where it was a live `I2S1_WS`. No I2S block is driving those pins.
  `aplay -l` shows only the two vc4hdmi cards.

So the codec is either unwired, unpowered, or absent from the bench. Needs eyes on the rig.
Nothing was written to the Pi — read-only probe.

### Same day, later — CONNECTED. At **0x67**, not 0x64, and in a pristine cold state

Peter reconnected the board. `[measured]`

- **`i2cdetect -y 1` now shows `0x67`.** The address is set by the ADDR1/ADDR0 pins over 0x64-0x67;
  every earlier script and note in `linux/adau1860-pi5/` defaults to **0x64**. **Fix the default to
  0x67 or the next session repeats this.**
- **Identity confirmed, all four ID registers:** `VENDOR_ID=0x41`, `DEVICE_ID1=0x60`,
  `DEVICE_ID2=0x18`, `REVISION=0x01`. That also re-confirms the `[derived]` 32-bit big-endian
  subaddress framing is correct — **on kernel 6.18.39**, so I2C control survives the kernel change.
- **The part is cold and every register is at its reset value.** `ADC_DAC_HP_PWR=0x00`,
  `PLL_PGA_PWR=0x02` (XTAL_EN set, **PLL_EN clear** — this is exactly the 2026-09-02 bug),
  `SAI_CLK_PWR=0x00`, `CHIP_PWR=0x00`, `CLK_CTRL1=0xC8`, `SPT0_CTRL1/2/3=0x00`.
  **`STATUS2=0x00` -> POWER_UP_COMPLETE=0, SPT0_LOCK=0, PLL_LOCK=0.**

**This is the pristine window the 2026-09-02 scar is about.** `CLK_CTRL1`, `PLL_PGA_PWR` and
`CHIP_PWR` go read-only once the power domains come up and only a power cycle clears them. They are
all writable right now. Any bring-up attempt should be made from this state, in the datasheet's
numbered order, with `PLL_EN` set before anything expects a clock.

Still true: `dtparam=i2s=on` is commented out and no overlay is loaded, so there is no I2S path yet
— control only. Nothing has been written to the codec.

### Same day — I2S TESTED AND WORKING on 6.18.39

Peter: *"can you please test I2S to the adau1860"*. Done. Full write-up at
`linux/adau1860-pi5/RESULTS-2026-09-07.md`.

- **PASS.** `aplay` 4ch/S32_LE/48 kHz: requested 3s -> **3006 ms**, 5s -> 5061 ms, 3s -> 3023 ms;
  2ch 3s -> 3017 ms. Exit 0, real time, clean dmesg. Real time is the proof — the Pi is the clock
  consumer, so only the codec can pace it. Card `adau1860-tx` on `1f000a4000.i2s` = `rp1_i2s1`.
- **Codec brought up from cold:** `STATUS2 = 0xF1` — POWER_UP_COMPLETE=1, SPT0_LOCK=1, **PLL_LOCK=1**.
  The 2026-09-02 `PLL_EN` bug does not recur when the numbered order is followed.
- Overlay `adau1860-pi5-tx` installed and enabled in `/boot/firmware/config.txt`; `config.txt`
  backed up first. `dtparam=i2s=on` deliberately left commented — it would enable the producer block
  on the same pins.

**Three corrections that future sessions need:**

1. **The I2C address is 0x67, not 0x64.** Defaults fixed in `adau1860_init.py` and `run_on_pi.sh`.
2. **The machine is `aeronode` (192.168.0.99), not `scopenode`.** Same box — machine-id, `~/ardupilot`
   and my own 3 Sep config backups all match — but `scopenode.local` no longer resolves and the
   journal shows systemd renaming it to `aeronode` two seconds into every boot. All older notes
   saying "scopenode" mean this machine.
3. **A failed framing attempt poisons the whole boot.** After a TDM `EIO` the DMA channel sticks
   (`dma2chan4 is non-idle!`) and even a correct STEREO attempt then fails. **One attempt per boot.**
   The 2026-09-02 line "after a clean reboot" was load-bearing, and I first read it as incidental.

**Instrument scar:** `pinctrl` level-sampling said `GPIO19 hi=0 lo=200` and I nearly reported LRCLK
dead. It was a **narrow frame pulse** — 1 BCLK in 128. `gpiomon` caught falling edges 20.83 us apart
= **48.0 kHz**. Count edges, never sample levels, when the question is "is this pin clocking".

### Still open

- Which slots the codec actually latches in STEREO mode is unverified (no read-back path); use the
  `DAC_ROUTE0` + distinct-DC-per-slot method from `RESULTS-2026-09-02.md`.
- RX / duplex not re-tested on 6.18.39 — only the TX path was exercised.

---

## 2026-09-08 · TTS through the ADAU1860 — two paths, both working

Peter: *"some text to speech through this audio board"*, then *"put piper on the pi"*. Both
delivered. Full write-up `linux/adau1860-pi5/RESULTS-2026-09-08.md`, commits `eb1ae8b`, `478d8c7`.

- **`piper_say.sh`** — Piper 1.8.0 neural TTS **on the Pi**, venv at `~/piper-venv`, voices in
  `~/piper-voices`. RTF **0.371x** including model load, so it streams. `install_piper.sh` is
  idempotent. Three English voices; default `en_GB-alba-medium`.
- **`say_on_codec.sh`** — macOS `say` from the Mac, for voice variety. The Pi has no other engine.
- Both end in `aplay -c 4` with audio in **slots 0 and 2** (`pack_slots.py` / `say_to_slots.py`);
  neither writes a codec register — `bringup.sh` from a cold board still owns that.

**Facts worth carrying:** SSH to the rig is **`node@192.168.0.99`** (no key for `peterbruce`).
Piper's live home is **`OHF-Voice/piper1-gpl`**, not `rhasspy/piper` (read-only since Oct 2025);
its abi3 aarch64 wheel installs on Python 3.13 with no build. ffmpeg is already on the Pi.

**CLOSED — Peter confirms he heard all three voices** (2026-09-08, by ear). Speech is intelligible
out of P30, so the chain is proven end to end: neural synthesis on the Pi -> 48 kHz resample ->
slots 0 and 2 -> I2S -> ADAU1860 DAC -> analog. This is the confirmation the digital-path figures
could never supply from here, and it retires the "audibility is Unknown" caveat that has ridden
every ADAU1860 result since 2026-09-02. Future TTS results may state the analog path works —
but a *new* configuration still needs ears, because a muted DAC reads back perfectly (2026-09-07).

---

## 2026-09-08 (later) · Headset mute relays — design note, nothing wired

Peter: *"start looking at wiring up a relay board to mute the audio left and right going to the
headset and electret mic from the headset when i2s audio path is active."* Note at
`docs/h1-headset-mute-relay.md`.

**Peter's rulings:** bench proof first · design for GA aviation, prototype on the TRRS rig ·
**mute only**, not changeover · **CM5 GPIO software-asserted**, no hardware I2S detector.

- **The signals already exist.** `[repo]` John's AERONODE block diagram carries `GPIO_RLY_SPKR` and
  `GPIO_RLY_MIC` into the `AUDIO` block alongside `I2S1_SDO2/SDI2/SDO3/SDI3`. The audio interface
  sheet holds **only connectors** — no codec, no relays. So the block is agreed, the circuit is not.
- **Part sourced with numbers.** Omron `G6K-2F-Y`, DPDT, **bifurcated crossbar, Ag (Au-alloy)**,
  **min permissible load 10 uA at 10 mV DC**, operate/release 3 ms max, 5 V coil 21.1 mA. `[fetched]`
  from Omron's datasheet. A generic SRD-05VDC relay module is the **wrong part** — silver contacts
  need wetting current and go crackly on dry-circuit audio.
- **Aviation far side, `[fetched]` Bose A20:** earphones **320 ohm stereo**, mic bias **8-16 VDC
  through 220-2200 ohm**, mic output **600 mV at 114 dB SPL**. That last number means an aviation
  mic **overdrives** the ADAU1860's 0.49 V rms full scale — the opposite of the bench problem. Do
  not carry "buy a MAX9814" across from the bench.
- **Topology:** Form C break-and-shunt, `R_MUTE` link picks hard-mute (0R) vs series-break (DNP), so
  Peter's mute-only ruling and John's changeover intent stay compatible. Fail-passive comes from a
  **100k gate pulldown** on the FET — a CM5 GPIO is high-Z through boot, so without it the pilot's
  audio state during a reboot is undefined.

### Open

1. `[gap]` **Mic-node DC operating point** — three meter readings on a real panel + headset close it.
   The mic shunt value cannot be calculated without them; I did not guess one.
2. `[gap]` **PTT interlock.** Mic muted + PTT pressed = transmitting silence, unknowingly. Needs a
   ruling from Peter/John before this flies. Out of scope for the bench.
3. **The mic mute cannot be bench-tested yet.** The bench mic path is already silent (TRRS plug in
   P11's TRS jack, and no bias) — a mute on a dead path passes its positive control for the wrong
   reason. Fix the mic path first.
4. `[assumed]` GPIO23/24 for the relays — verify with `pinctrl get`, keep clear of GPIO18-21 (I2S1).
5. **Requirement reading flagged for correction.** I read "I2S path active" as *AeroNode is
   speaking*. `DATA_OVER_I2S.md` makes a second reading plausible — the same link as a raw sensor
   pipe, in which case this is a hearing-protection interlock and should not be software-asserted.
   Same circuit, different safety argument. One sentence from Peter settles it.

**Rig was unreachable** — `192.168.0.99:22` timed out while this was written. `[measured]` Nothing
was probed, nothing was wired.

### Same day — Peter: "can we use a blocking capacitor to stop the bias affecting the ADAU1860 output"

Answered in `docs/h1-headset-mute-relay.md` section 10. **Yes, and it is mandatory, not optional.**

- `[fetched]` ADAU1860 Rev. 0 abs max: **"Analog Input Voltage (Signal Pins) -0.3 V to AVDD + 0.3 V"**
  and **"Input Current (Except Supply Pins) +/-20 mA"**. AVDD is 1.8 V, so the ceiling is **2.1 V**
  against an 8-16 V mic line. `[derived]` worst-case fault 16 V through a 220 ohm bias resistor =
  **63 mA** against a 20 mA rating. Direct connection destroys the part.
- **Injection circuit (10.1):** `HPOUTP -> C1 220nF film -> R1 10k -> mic node`, BAT54S clamp,
  `HPOUTN` **left open, never grounded** (it is a driven output — the DAC pair is differential,
  1.0 V rms FS). R1 sits after C1 deliberately: if C1 fails short, 16 V/10k = 1.6 mA, inside the
  rating. Corner 69 Hz. **Do not use X7R** — DC-bias derating walks the corner into the voice band.
- **The better answer for the aircraft is a 600:600 transformer** — a cap blocks DC but does not
  break the ground loop, and aircraft audio ground can sit volts off ours.
- **10.2 supersedes part of section 4.** A shunt-leg cap (100 uF NP + 1M bleed to keep it charged)
  mutes the mic **without ever breaking the DC path** — no bias interruption, no thump on either
  edge. `[derived]` -39 dB at 300 Hz against a 470 ohm source. **This closes open item 1** (the
  capsule's DC operating point) by changing the circuit rather than by measuring it.
- **Operational warning recorded:** injecting into the mic line trips the intercom VOX and goes out
  over the air if PTT is pressed. If the intent is a private advisory, the mic line is the wrong
  injection point.

`[gap]` still open: whether the ADAU1860 HP amp is specified to run with one leg unloaded (the
abridged datasheet has no output-stage description), and whether a capsule minds driving a near-short.

### Same day — RULED: transformer isolation on the aircraft side

Peter: *"use the transformer approach for the aircraft side."* Section 11 of
`docs/h1-headset-mute-relay.md`. The section 10.1 capacitor coupling is superseded for anything
facing the aircraft; it survives only as a bench expedient.

- **Part: Bourns `SM-LP-5001`.** `[fetched]` from Bourns' own datasheet — 600 ohm 1:1, **200 Hz-4 kHz
  +/-0.25 dB**, insertion loss 2 dB, **dielectric strength 2000 Vrms/1 min**, DCR 115 ohm/winding,
  **shunt inductance 3.8 H**, power level 10 dBm. `[fetched, search-result]` LCSC `C7503474`, $1.95,
  550 in stock. NOTE `bourns.com/docs/...` 403s; `bourns.com/pdfs/...` serves it.
- **The design rule that decides layout:** attenuator goes on the **SECONDARY**. `[derived]` LF corner
  = R_source/(2*pi*L). 10k on the primary = **419 Hz**, inside the voice band. 10k on the secondary
  leaves ~116 ohm driving the primary = **4.9 Hz**. Getting this backwards ruins the audio.
- **The transformer deletes three problems at once:** no primary blocking cap (DAC DC offset 0.1 mV
  across 115 ohm = 0.87 uA, nothing to a 3.8 H core), the differential-output question is gone
  (both legs drive the winding), and the 16 V fault path is gone. **This CLOSES the section 10.1
  `[gap]`** about running HPOUTN unloaded — the question no longer arises.
- `[derived]` Level: 0.79 Vrms after insertion loss, through 10k into a ~470 ohm mic node = **35 mVrms**.

### CORRECTION made to sections 3 and 10.2 — the mute shunts

Both said "GND". **Wrong once there is an isolation boundary.** Every aircraft-side shunt —
`R_MUTE` on the earphones, the mic-mute cap and its 1M bleed — must return to **headset/aircraft
ground (plug sleeve)**, never AeroNode GND, or the mute bonds the two grounds the transformer just
separated. Separate net, own symbol, own copper island. The likeliest failure of this design is a
ground symbol dropped on the wrong side of the boundary in layout.

**The relays are already part of the barrier** — `[fetched]` G6K is 1500 VAC coil-to-contact for
1 min, 1000 Mohm at 500 VDC, and the **`-Y`** suffix is the wide-creepage variant (3.2 mm, 2.5 kV
impulse, Telcordia). So `G6K-2F-Y` is now justified by a stated reason, not habit. With the
transformer the only signal crossing and the coils the only control, **nothing on the aircraft side
is galvanically connected to AeroNode.**

### Open (new)

6. **`SM-LP-5001` is NOT a flight part.** `[fetched]` operating range **-20 to +85 C** — a GA cockpit
   goes below that — and `UL60950` is an IT-equipment standard, not DO-160. Bourns' own applications
   list is modems and laptops. Right for the bench and a proof-of-concept; a flight article needs a
   qualified transformer and that sourcing has not started. `[gap]`
7. `[gap]` **Confirm the SM-LP-5001 pinout before layout.** Six pins, datasheet says the part is
   symmetrical (implying a centre tap per side), but pin functions are in a schematic **graphic**
   with no extractable text. Render and read it, as with UG-2017 Figure 8. Do not assume 2 and 5.

### Same day — DRAWN into the canonical schematic

Peter: *"draw the transformer and relay block into the audio interface schematic."* Done, in
`~/aerosense/aeronode/aerosense/aeronode-lite/aeronode-audio-interface.kicad_sch`, **through Konnect
MCP only**. Section 12 of `docs/h1-headset-mute-relay.md`.

- **18 components:** K1/K2 (G6K-2F-Y), T1 (SM-LP-5001), Q1/Q2 (2N7002), D1/D2, R1-R8, C1, J10/J11.
- **That tree is NOT under git.** Backed up two ways first: `.bak-LIMA-<stamp>` beside the file, and
  a byte copy at `lima:kicad/aeronode-lite-audio/before/`. Rollback is one `cp` (README documents it).
- **ERC negative control: 41 errors before, 41 after, identical list.** `[measured]` The block adds
  **zero** errors and zero warnings; the 41 are pre-existing decorative block-diagram labels. Running
  ERC on the untouched `before/` copy is what proves that — without it, "41 errors" reads as mine.
- **Netlist verified `[measured]`.** The block **tied into the existing sheet by net name**:
  `GPIO_RLY_SPKR -> J4.2`, `GPIO_RLY_MIC -> J4.1`, `5V_NODE -> J2.8`, `GND -> J1.1/J2.1/J3.1`.
  It is wired into John's sheet, not drawn beside it. 0 floating wire endpoints.
- **Rendered and LOOKED at it.** First render had every relay-pin label colliding into unreadable
  mush. Rotated the contact labels vertical, replaced three redundant gate labels with wires, moved
  the note block. Re-rendered until legible. **A schematic you have not rendered is not checked.**

### Section 11.4 `[gap]` CLOSED — and the caution was right

`[fetched]` Rendered the SM-LP-5001 schematic graphic at 900 dpi and read it:
**pins 2 and 5 are NO-CONNECT, not centre taps.** Windings are **1-3** (dot on 1) and **6-4** (dot
on 6). Section 11.4 had said "do not assume 2 and 5 are the taps" because the datasheet calls the
part symmetrical — that inference would have been **wrong**. Same class as the ICM-45686 footprint
trap. Crop committed at `kicad/aeronode-lite-audio/doc/smlp5001-pinout.png`.

### Open (new)

8. **Symbols are generic and footprints are deliberately unassigned.** `Relay:Relay_DPDT` uses
   EN50005 pin numbers (11/12/14/...) where the G6K package is 1-8; `Device:Transformer_1P_1S` is
   1-4 where the SM-LP-5001 is 1/3/4/6 + 2/5 N/C. A note on the sheet says so. **Author real symbols
   and footprints before layout** — same decision as `kicad/imu-board/` U1.
9. **The block sits on a block-diagram sheet (A4, already full).** Legible, but it belongs on its own
   hierarchical sub-sheet like `cm5.kicad_sch`. Copy-paste when Peter wants it, not a redraw.
10. **J10/J11 are generic 4-pin placeholders** — real GA is a dual plug (PJ-055/PJ-068) or a 6-pin
    panel connector. Waiting on the mechanical interface decision.

## 2026-09-09 · Mute block moved to its own sheet — and an instrument caught lying

Peter: *"can we please put this on its own schematic so no text overlays."* Done. Section 13 of
`docs/h1-headset-mute-relay.md`.

- **`AUDIO MUTE + ISOLATION` is now a hierarchical sub-sheet**, `audio-mute.kicad_sch` (page 3),
  matching the `cm5.kicad_sch` pattern already in the project. Sheet symbol at (115,128), 55x45.
- **Parent restored to original bytes first** (`md5 052f149b996dfdf74993d68451ab7aa5`, verified
  against the pre-edit backup) rather than unpicking ~45 labels by hand. Then only the sheet symbol
  and its 6 pins were added. **Restoring from a verified byte copy beat surgical deletion.**
- **6 sheet pins** via KiCAD's own Import Sheet Pins: `GPIO_RLY_SPKR`/`GPIO_RLY_MIC` (-> J4),
  `5V_NODE` (-> J2.8), `GND` (-> J1/J2/J3), `HPOUTP`/`HPOUTN` (nothing yet, codec unplaced).
  `validate_sheet_pins`: 0 issues. Aircraft-side nets stay **local to the sub-sheet**.
- **No overlays.** The change that did it: **rotate K1/K2 90 deg** so contacts face left/right at
  2.54 mm pitch — horizontal labels then stack like connector pin names.
- **ERC 41 = untouched baseline. Netlist verified on both sides of the boundary.** `[measured]`

### SCAR — Konnect's `validate_wire_connections` said valid; KiCAD's ERC said otherwise

`validate_wire_connections` returned **`0 floating endpoints, valid: true`** on the child sheet.
KiCAD's ERC at the same moment reported **2 wires connected to nothing**, and the netlist confirmed
ERC: **`Q1.G`, `R5.2`, `R7.1` were on NO net at all.** The gate wires were drawn, rendered
convincingly, and passed the friendly check.

Junction dots did **not** fix it; a **net label on the gate node** did (`RLY_SPKR_G`, `RLY_MIC_G`).

Two rules from it:
1. **`validate_wire_connections` is not ERC.** It answers "does every wire end touch something", not
   "does every pin land on a net". **Believe the netlist.**
2. **A render that looks connected is not a connected schematic.** The only proof a node exists is
   its appearance in the netlist with every pin you expect. This is section 3's "a broken instrument
   fails toward the answer you expected" in its purest form -- the check I ran first was the one
   that agreed with me.

### Open

11. `[gap]` **KiCAD is running on this Mac** (`pgrep kicad` -> a process). If Peter has this project
    open in eeschema he must **reload** it, and must not save from a stale in-memory copy or these
    edits are lost.

### Same day — ADAU1860 analog IN + OUT added to `audio-mute.kicad_sch`

Peter: *"add the adau1860 analog out and in connectivity."* Section 14 of the design note.

- **OUT** was already there (`HPOUTP`/`HPOUTN` -> T1 -> R4 -> MIC_LINE); now captioned on the sheet.
- **IN is new and it needed a SECOND transformer.** `MIC_LINE -> R9 (2k2) -> MIC_TAP -> T2 ->
  AINP2/AINN2`. A direct tap would have been a **second galvanic crossing** and would have silently
  destroyed section 11.3's claim that T1 is the only one. Two transformers, boundary intact.
- `[derived]` R9=2k2 costs ~1.3 dB of the pilot's mic level to the radio and puts the LF corner at
  ~92 Hz. Speech arrives ~8.5 mV = -41 dBFS; 114 dB SPL lands near -20 dBFS, so **do not run the
  PGA near maximum**.
- **Codec symbol still NOT placed, deliberately.** `h1-audio-board-codec-selection.md` records the
  ADAU1761-vs-1860 choice as **John's**. Placing a symbol would quietly take it. The interface is
  sheet pins instead — correct either way.
- ERC 41 = baseline. `validate_sheet_pins` 0 issues across 8 pins. Netlist verified.

### Open (new) — a real fork for Peter, not a gap to inherit

12. **As drawn, muting the mic also deafens AeroNode's own capture.** K2 shunts the *shared*
    MIC_LINE node (10.2) and the capture taps that same node. If the wanted behaviour is *"the radio
    cannot hear the pilot but AeroNode can"* — which is what push-to-talk-to-the-assistant needs —
    K2 must become a **series break** with the tap on the headset side, and that **reopens the
    DC-thump question 10.2 closed**. Recorded on the sheet and in the note. **Not taken by me.**
13. `[gap]` Assumes ADAU1860 `AINx` self-bias (EVB Fig 8 shows only 22uF in series, no bias network).
    If not, two bias resistors per T2 secondary leg to CM (0.85 V).

### SCAR CONFIRMED (second occurrence) — label every wire, then read the netlist

The new R9->T2 wire produced one fresh *"Wires not connected to anything"* ERC error until a net
label (`MIC_TAP`) was placed on it. **Same failure, same fix, second time.** It is now a rule:
**a Konnect-drawn wire segment carrying no net label does not reliably form a net.** Konnect's
`validate_wire_connections` passes it regardless — believe KiCAD's ERC and the netlist.

### Same day — RULED: headset mic is PANEL ONLY. Section 14's capture path REMOVED.

Peter: *"the electret mic does not need to go to the aeronode we will use another analog mic via
i2s."* Section 15 of the design note.

- **Deleted from the schematic**, not deprecated: `R9`, `T2`, `MIC_TAP`, the `AINP2`/`AINN2`
  hierarchical labels and their two parent sheet pins. `[measured]` netlist has no `AIN*` net and no
  R9/T2. Both sheets backed up first (`.bak-LIMA-20260909-111922`). ERC 41 = baseline.
- The headset electret now runs **headset -> MIC_LINE -> aircraft panel** only, K2 muting it.
  AeroNode's audio input is a **separate analog mic into the codec over I2S**, not on this sheet.

**Three things the ruling cleans up:** section 11.3's "T1 is the ONLY crossing" is literally true
again (14 had needed a second transformer just to keep it honest); **open item 12 is CLOSED** rather
than carried, because with no capture from this mic the mute-vs-capture conflict cannot arise and
10.2's AC-only shunt stands; and one transformer + one resistor come off the BOM.

### But a MORE serious conflict is now exposed — needs Peter's ruling

With the capture gone, MIC_LINE carries the pilot's mic **and** AeroNode's TTS (injected by R4).
Trace it: `HPOUT -> T1 -> R4 -> MIC_LINE -> panel -> intercom -> AC_L/AC_R -> K1 NC -> pilot`.

**The TTS arrives through the very contact K1 opens to mute.** So energising GPIO_RLY_SPKR to "mute
the headset while AeroNode speaks" cuts the only path AeroNode's voice has — the pilot hears
*nothing*. K2 compounds it: its shunt is on MIC_LINE, so muting the mic also shorts the injected TTS
(`[derived]` ~100uF against R4's 10k is about -66 dB at 300 Hz).

**Fix is what John drew originally: make K1 a CHANGEOVER** — NO contact to AeroNode audio rather
than AC_GND — so muting the intercom *substitutes* AeroNode's voice instead of silence. Two nets.
`[gap]` **Not taken.** Peter ruled mute-only on 2026-09-08 *before* the injection point was chosen,
so this is new information, not grounds to overturn him quietly. On the sheet and in section 15.

### Open

14. **The K1 / mic-line-injection conflict above.** The single most important thing on this design
    now. Nothing else about the block is worth refining until it is ruled.

### Same day — RULED: K1 is a CHANGEOVER to AeroNode audio. Open item 14 CLOSED.

Peter: *"yes make K1 a changeover to the aeronode audio."* Section 16 of the design note. This
supersedes the mute-only ruling **for K1 only**; K2 stays a mute.

- **Two nets changed.** `R1.2`/`R2.2` moved from `AC_GND` to **`AERONODE_AUDIO`** = the T1 secondary
  hot leg (T1.4). R1/R2 are now commoned by a wire and labelled once (two 14-char labels 15 mm apart
  collided; commoning them is both prettier and better practice).
- De-energised: HS_L/HS_R <- AC_L/AC_R (pilot hears the radio). Energised: HS_L/HS_R <-
  AERONODE_AUDIO, intercom side OPEN. Return completes via AC_GND to T1.3.
- **Fail-passive unchanged** — de-energised is still the metal contact to the radio.
- `[measured]` `~/AERONODE_AUDIO -> R1.2, R2.2, R4.1, T1.4`; AC_GND no longer carries R1.2/R2.2.
  ERC 41 = baseline.

### Open (new)

15. **R4 is now redundant AND a transmit hazard — recommend DNP.** AeroNode's voice reaches the
    pilot directly through K1 now; R4 still injects it into MIC_LINE toward the **panel**, so it
    will trip VOX and **be transmitted if PTT is pressed while AeroNode speaks**. Left populated
    pending a ruling only because "AeroNode audible on the radio" might be wanted.
16. `[gap]` **Level needs ears.** `[derived]` T1's 115R per winding against 160R of paralleled
    earphones divides 1.0 Vrms FS to **~0.41 Vrms (~1.05 mW)**. A GA intercom drives 1-2 Vrms, so
    this may be 8-14 dB quiet in a noisy cockpit. **Fix would be a lower-DCR transformer or a gain
    stage after the codec — NOT more digital gain.** Same class as the 2026-09-08 audibility
    caveat: cannot be settled from a desk.

### Same day — RULED: R4 = DNP. Open item 15 closed, with one honest residual.

Peter: *"DNP R4."* Section 18. R4 stays on the sheet so the footprint/option survive.

Marked four ways `[measured]`: custom property `DNP=yes`, a `Note` property giving the reason,
sheet text "R4 = DNP (do not populate)" beside it, and the note block.

**RESIDUAL, not rounded up:** the KiCAD `(dnp ...)` **attribute is still `no`.** Konnect's
`edit_schematic_component` / `batch_edit_schematic_components` set *properties*, not the symbol
attribute, and the konnect rules forbid hand-editing a `.kicad_sch` to reach it. So eeschema will
not cross R4 out, and **a BOM/position export will still list it as fitted.** One click fixes it:
right-click R4 -> Properties -> tick "Do not populate". `[gap]` **Not ticked as of this commit.**

This is precisely CLAUDE.md section 10's pattern — *a control written down, believed and cited but
not actually live*. Four markings on a drawing do not stop a fab populating a part the BOM says to
populate.

`[derived]` Electrically: unfitted, R4 removes the only tie between AERONODE_AUDIO and MIC_LINE, so
**the transmit hazard is gone at circuit level** rather than merely masked by K2's shunt (section
17). MIC_LINE now carries the pilot's mic and nothing else. Earphone level +0.08 dB.

**Cosmetic scar:** setting Value to "10k  DNP" overflowed the resistor body and collided with the
AERONODE_AUDIO and MIC_LINE labels. Reverted to "10k" with the DNP marking as separate sheet text.
**A longer Value string is a layout change — render and look after any field edit.**

### Same day — three analog mics on ADC0/1/2, new sheet `analog-mics.kicad_sch`

Peter asked for boom-voice + ANC feedforward + ANC feedback. Section 19. Page 4 of the project.

- J20 boom voice -> AINP0/N0, J21 ANC feedforward -> AINP1/N1, J22 ANC feedback -> AINP2/N2.
  Per channel: 100R + 1uF supply filter, and 1uF coupling on BOTH legs (OUT and the module's local
  GND) = pseudo-differential, mirroring the EVB's Figure 8 topology.
- **CHANNEL BUDGET IS NOW FULL.** `[fetched]` The ADAU1860 has exactly three ADCs. Zero spare.
- **They are AeroNode's own mics** — our rail, our GND — so they never touch AC_GND and **section
  11.3's "T1 is the only crossing" still stands literally.** No transformers needed here.
- ERC **42**, not 41: the extra is `Label not connected: '3V3_MIC'`, which is ERC correctly saying
  the mic rail has no source. `[gap]` no LDO specified. Tying it to 3V3_CM5 to make the number
  pretty would be the wrong trade — ANC noise is set by the mic supply.
- `validate_sheet_pins` 0 issues across 14 pins; `/GND` now spans all three sheets. `[measured]`

### SCAR — I read a spec band as physics, and caught it only by doing the arithmetic

I wrote on the sheet that T1's **200 Hz-4 kHz** spec would cut ANC off below 200 Hz. **Wrong.**
That band is Bourns' **600R telecom** condition. In this circuit (160R earphones, low-Z drive) the
Thevenin R across the 3.8 H magnetising inductance is 81.6R, so the corner is **3.4 Hz** — -0.020 dB
at 50 Hz, flat across the whole ANC band. Corrected on the sheet before committing.

**A vendor's specified band is the condition they guaranteed, not the physics of your circuit.**
Reading it as a hard limit would have sent someone shopping for a different transformer for nothing.
Compute the corner from your own source and load impedances.

### Open

17. **ANC blocker: K1 is a changeover, so the DAC only reaches the earcup while K1 is energised.**
    ANC anti-noise must be permanently connected. Either K1 sums instead of switching, or ANC needs
    its own always-on output path. **Needs a ruling; not taken.**
18. `[gap]` **Does the target headset already have ANR?** A Bose A20 does. Two ANC systems fighting
    over one earcup is worse than either alone. Decides whether this path is worth building.
19. `[gap]` `3V3_MIC` needs a quiet LDO. `[gap]` T1 LF *distortion* at power unmeasured (separate
    from response). `[gap]` ANC must run on FastDSP at a high rate - 48 kHz gives ~1 ms loop
    latency, too slow for feedforward above a few hundred Hz; datasheet characterises 768 kHz.

### Same day — RULED: ANC only while AeroNode is the active path. K1 STAYS a changeover.

Peter cancelled the summing change mid-edit: *"anc is only active when aeronode is the active audio
path."* **Open item 17 CLOSED** — section 19's "architectural blocker" was the intended behaviour.

- **Reverted byte-exactly.** Three labels had been deleted when the cancel arrived. The timestamped
  backup taken *immediately before the first deletion* restored it: `[measured]` live file `cmp`s
  identical to the copy committed at `c485dde`, and `git diff` on the mirror is empty. Netlist
  re-verified: `~/MUTE_L -> K1.14, R1.1`, `~/MUTE_R -> K1.24, R2.1`. **Backing up before starting,
  not after finishing, is what made the cancel cost nothing.**

### Two findings from the abandoned summing work — KEPT so nobody re-derives them

1. **0R summing resistors would SHORT the panel's L and R together.** Under the changeover, R1/R2 at
   0R tie HS_L and HS_R — harmless *because the intercom is open at the same instant*. Summing keeps
   the intercom connected, so the same 0R becomes a short across its outputs. The kind of fault that
   survives review because no part changed, only the switch behaviour around it.
2. **You cannot passively sum into a node a low-Z amplifier already drives.** `[derived]` AeroNode's
   level at the earphone vs the panel's output impedance: **-27.9 dB into 10R**, -12.1 dB into 100R,
   -6.5 dB into 600R (Rsum=0). Against a stiff panel output AeroNode is ~28 dB down — useless for
   ANC. Making it work would need a series R in the *intercom* path (costing radio level on the
   safety-critical path) or series injection via a second transformer.

So the ruling is also the cheaper engineering: ANC while AeroNode owns the earcup sidesteps the
problem entirely, because the intercom is open exactly when ANC is running.

### Same day — RETRACTED section 20. K1 SUMS after all; ANC is always on.

Peter: *"actually i'm taking rubbish forget my previous statement"* -> clarified as **forget the
cancel**. Section 21. I **asked** rather than guessing: the two readings gave opposite circuits, and
picking wrong would have written a false ruling into the record as well as the wrong copper.

- R1/R2 moved from K1.14/24 to **HS_L/HS_R permanently**; K1's NO contacts unused and no-connected;
  K1 now breaks only the intercom. MUTE_L/MUTE_R nets gone. `[measured]` `~/HS_L -> J11.1, K1.11,
  R1.1`, `~/AERONODE_AUDIO -> R1.2, R2.2, R4.1, T1.4`. ERC 42 (41 + the deliberate 3V3_MIC).
- **R1/R2 changed 0R -> 220R, and had to.** AERONODE_AUDIO ties the two channels, so 0R would
  **short the panel's L and R outputs**. Harmless under the changeover (intercom open at the same
  instant), a fault under summing. **The value had to change because the switch behaviour around it
  changed, not because the part did** - the kind of thing a parts-focused review misses.
  220R gives a 440R L-R path for only 1.4 dB less level than 100R.

### The honest limit: ANC AUTHORITY, not connectivity

`[derived]` A passive sum cannot fight a low-Z source. Intercom live: AeroNode ~**-33 dB** at the
earphone. K1 open: **-7.6 dB** - a free ~26 dB step, because the swamping panel is disconnected.
So **ANC authority in normal flight is set by the panel's headphone output impedance**, `[gap]`
unmeasured. Stiff panel (10R) -> ANC ~33 dB down, useless. Soft (330-600R) -> -13 dB, arguable.

### Open

20. **MEASURE THE PANEL'S HEADPHONE OUTPUT IMPEDANCE.** It decides whether ANC works summed. If it
    is stiff, ANC needs its own path to the transducer instead of sharing the intercom line - a
    bigger change than any resistor value, so worth knowing early.

### Same day — Peter: "how is there stereo if AeroNode goes to both HS_L and HS_R?"

Section 22. Three answers, two of them real limits:

1. **AeroNode is mono and cannot be otherwise.** `[fetched]` ADAU1860 has ONE DAC; T1 has ONE
   secondary. Not a drawing error. Self-consistent with 1 feedforward + 1 feedback mic = **one ANC
   channel driving both earcups**. Per-ear ANC would need 2 DACs + 2 feedback mics = different codec.
2. **R1+R2 bridge the intercom's L to R through 440R.** `[derived]` separation vs panel Z_out:
   -42.5 dB at 5R, -20.4 dB at 100R, **-14.1 dB at 600R**. A stiff panel holds each channel and the
   bridge only sinks current; a soft one lets them pull each other about.
3. **The same impedance pulls the two requirements OPPOSITE ways.** 10R: ANC -33.5 dB (useless),
   separation -36.8 dB (fine). 600R: ANC -11.3 dB (good), separation -14.1 dB (poor). **No panel
   impedance makes both good.** Inherent to summing two sources onto one node through one winding.

**Fix offered, not taken:** a SECOND transformer, one secondary per channel from the same mono DAC.
Kills the L-R bridge entirely, and lets R1/R2 go to 0R safely (no shared node to short) which
recovers **+5.6 dB** of AeroNode level - the cheapest ANC-authority improvement available. ~$2.
`[gap]` needs Peter's ruling; only matters if the panel is soft, so **measuring the panel (open
item 20) decides this too.**

### Same day — T2 added: one transformer per channel. Section 23.

Peter: *"add the second transformer."* Built.
`HPOUTP/N` -> T1 and T2 primaries in parallel; T1 sec -> AERONODE_L -> R1 (0R) -> HS_L;
T2 sec -> AERONODE_R -> R2 (0R) -> HS_R; both returns to AC_GND. `AERONODE_AUDIO` is gone.
`[measured]` HS_L and HS_R now meet **only at AC_GND** - the 440R bridge is gone.

Three wins, `[derived]`:
1. **No L-to-R bridge** - intercom separation is now whatever the panel gives, at any impedance.
2. **R1/R2 back to 0R safely** (no shared secondary to short through) = **+5.6 dB** AeroNode level
   with the intercom live. This is what the change was bought for.
3. **Unplanned +3.0 dB per ear when active** - each secondary drives ONE 320R earphone instead of
   both in parallel, so 0.582 Vrms per ear instead of 0.410 (2.12 mW vs 1.05 mW the pair).
HP amp now drives two primaries in parallel: 275R, 3.6 mA. Trivial.

**Section 11.3 updated: TWO crossings now, T1 and T2**, 2000 Vrms each. Nothing else crosses.

### METHOD NOTE — ERC 42 -> 44 was NOT a regression

The two new errors are `Label not connected: HPOUTP/HPOUTN` on the parent. Before, those nets had
exactly ONE pin (T1.1/T1.2) so ERC reported the *warning* "connected to only one pin". Adding T2 gave
each a second pin, the warning stopped applying, and **the error it had been masking surfaced** - the
codec is not placed, so HPOUTP/HPOUTN have no source.

Count is now **41 baseline + 3 deliberate**, all saying *this net has no source yet*: 3V3_MIC needs
an LDO, HPOUTP/HPOUTN need the codec.

**An error count that goes UP is not automatically a regression, and one that stays flat is not
automatically clean.** ERC reports one rule per item, so changing one condition can reveal another
that was always there. **Read the new entries; do not just diff the number.**
