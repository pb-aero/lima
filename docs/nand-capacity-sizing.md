# How long can the 1 Gbit SPI NAND record?

**Question (Peter, 2026-09-30):** using recent AHRS logs and audio recordings, what duration can the
1 Gbit SPI NAND capture?

**Answer: between 5.7 and 21 minutes, depending entirely on the format you write.** At the rates the
recorder actually produced on the RV-8 flight it is **5.7 minutes**. The best you can do without
reducing what you capture is **21 minutes**. The part cannot hold a single training sortie in any
configuration.

Provenance: `[fetched]` = Winbond datasheet · `[measured]` = computed from the flight dataset ·
`[derived]` = arithmetic on those two.

---

## 1. The part

`[repo]` `docs/aeronode-cm5-software-rev1.md` §Storage names **W25N01GVZEIG** (alongside a 4 Gbit
F35SQB004G), and the schematic symbol is in `kicad/aeronode-lite-audio/`.

`[fetched]` Winbond W25N01GV datasheet, Revision L (May 2018), §10.1 and the array description:

| Property | Value |
|---|---|
| Array | 65,536 pages × 2,048 B main = **134,217,728 B = 128.00 MiB** |
| Block | 64 pages = 128 KiB; **1,024 blocks** |
| Page spare area | 64 B (2,112 B total/page) — **bad-block marker + ECC, not user data** |
| Valid blocks `Nvb` | **min 1004**, max 1024 — up to 20 bad blocks |
| Worst-case user capacity | 1004 × 128 KiB = **125.50 MiB** |

"1 Gbit" is 128 MiB, not 1 GB. The 64-byte spare area is not extra room — it holds the ECC.
Both figures below are quoted: 128.00 MiB nominal, 125.50 MiB worst-case guaranteed. A flash
filesystem (UBIFS/littlefs) takes a further cut that is not modelled here, so treat 125.50 MiB as
an optimistic floor, not a budget.

## 2. Measured rates — RV-8_CM5_F01, 2026-08-28

Source: `~/Downloads/RV-8_CM5_F01/`, session `20260828T084535Z`, 25.90 min spanning takeoff and two
stalls.

### Audio `[measured]`

Format from the capture sidecar header and all 37 FLAC `STREAMINFO` blocks: **96 kHz, 24-bit,
1 channel** (`S32_LE` container, 32-bit, UMIK capsule, `channels_captured: 1`).

| | KiB/s | Mbit/s |
|---|---|---|
| FLAC as written — **flight** chunks (`20260828T082125Z`, 25.89 min, 121.50 MB) | **76.4** | 0.626 |
| FLAC as written — ground/quiet chunks | 12.0 – 20.7 | 0.10 – 0.17 |
| Raw PCM, 24-bit packed | 281.2 | 2.304 |
| Raw PCM as captured, `S32_LE` | 375.0 | 3.072 |

> **Trap — size on flight audio, never ground audio.** The same rig, same settings, compresses to
> 20.7 KiB/s on the ground and **76.4 KiB/s airborne** — 3.7× worse, because the cabin is loud
> broadband noise. Sizing this part on a bench recording overestimates endurance by nearly 4×.
> (The airborne audio is also hard-clipped — see the dataset README — which if anything makes FLAC
> compress *better* than clean audio would, so 76.4 KiB/s is not a pessimistic figure.)

### AHRS `[measured]`

`session_20260828T084535Z.jsonl` — 489.6 MB, 1,509,220 rows, 50 streams over 25.90 min =
**307.7 KiB/s** as written. The AHRS-class streams (`imu`, `imu2`, `imu3`, `attitude`,
`attitude_q`, `ahrs`, `ahrs2`, `ekf_status`, `vibration`) are 259.4 MB = **53.0%** of that =
163.0 KiB/s. The three IMU streams run at 97.1 Hz each.

`[derived]` The same content packed as binary — float32 per numeric field, 10 B record header,
using the field counts and rates measured in that log — is **27.70 KiB/s** for the AHRS streams and
**43.06 KiB/s** for all 50. That is a **7.1× reduction**, and it is free: the JSONL is spending
most of its bytes on field names and ASCII floats.

## 3. How long until it is full `[derived]`

| Configuration | KiB/s | 128 MiB | 125.5 MiB |
|---|---|---|---|
| **As flown today** — full JSONL + FLAC audio | 384.1 | **5.7 min** | 5.6 min |
| JSONL, AHRS streams only + FLAC audio | 239.4 | 9.1 min | 8.9 min |
| Packed binary, all 50 streams + FLAC audio | 119.4 | 18.3 min | 17.9 min |
| **Packed binary, AHRS only + FLAC audio** | 104.1 | **21.0 min** | 20.6 min |
| Packed binary, AHRS only + raw 24-bit PCM | 308.9 | 7.1 min | 6.9 min |
| Audio alone (FLAC, flight) | 76.4 | 28.6 min | 28.0 min |
| Packed binary AHRS alone, no audio | 27.7 | 78.9 min | 77.3 min |

**Audio dominates every mixed configuration.** FLAC flight audio at 76.4 KiB/s is 2.8× the packed
AHRS rate of 27.7 KiB/s. Compressing the AHRS log 7× moves the answer from 5.7 to 21 minutes;
after that, nothing but the audio matters.

## 4. What this means

**The RV-8 flight did not fit, by 4.55×.** It produced 489.6 MB of JSONL plus 121.5 MB of audio =
**611.1 MB for 25.9 minutes** — the whole 1 Gbit device, four and a half times over.

**A 2-hour flight at the leanest sane configuration needs 732 MiB — 5.7× this part.**

`[derived]` Endurance is not the constraint: at 104.1 KiB/s the device is fully rewritten every
21 minutes, which against SLC's ~100k P/E cycles is ~4 years of continuous recording.

### Options, in the order I'd consider them

1. **Use the 4 Gbit F35SQB004G** already named alongside it in the software doc. 4× the capacity
   takes the leanest config to ~84 min — still not a 2-hour sortie, but it covers a training flight.
2. **Pack the AHRS log.** 7.1× for no loss of information, and worth doing regardless of the part
   chosen. The JSONL format is for the ground, not the device.
3. **Decide what the audio is for.** 96 kHz mono is the whole budget. If the purpose is prop
   blade-pass and buffet (79–82 Hz and harmonics, per the dataset README), 96 kHz is ~500× the
   Nyquist rate needed. 8 kHz would still carry everything the analysis used and would cut audio
   to roughly a twelfth. That is a signal-purpose question, not a storage one — your call.
4. **Treat the NAND as a ring buffer**, not a flight recorder: keep the last N minutes plus
   event-triggered captures around stalls, and stream the rest off-board.

**`[gap]`** No flash filesystem has been chosen, so its overhead is not in these numbers. Whatever
is chosen, remeasure — the figures above are the raw device, and the filesystem only ever subtracts.
**Superseded for UBIFS specifically by §5 below** — a filesystem that compresses does *not* only
subtract.

## 5. Does UBIFS reduce these durations? (Peter, 2026-09-30)

**No — it increases them, in every configuration, provided compression is left on.** UBIFS costs
~10% of the device in overhead but compresses transparently on write, and the compression wins.

### The overhead `[fetched]`

`[fetched]` linux-mtd UBI documentation, *Flash space overhead* — the formula verbatim:

> UBI overhead = **(B + 4) × S_P + O × (P − B − 4)**

with `P` = 1024 PEBs, `S_P` = 128 KiB, `B` = MAX(B_R, B_B) = **20** (the default reserve is
"20 blocks per 1024 blocks", which matches this part's guaranteed `Nvb` min of 1004 exactly — do
not reduce it), and `O` = **4096 B** (2 NAND pages, the no-sub-page case).

`[derived]` = (20+4) × 131,072 + 4096 × 1000 = **7,241,728 B = 6.91 MiB**, leaving
1000 LEBs × 126,976 B = **121.09 MiB** for volumes.

> **On `O`:** the datasheet allows `NoP = 4` partial page programs, which would in principle permit
> sub-pages and halve `O`. It does not apply here: with the on-die ECC enabled (the normal Linux
> `spinand` mode) the ECC is computed across the buffer at Program Execute, so the EC and VID
> headers cannot share a page. `O = 4096`. Recovering that ~2 MiB would mean software ECC — not
> worth it.

`[assumed]` UBIFS's own structural overhead (superblock, master, log, LPT, orphan, index) is taken
as **4–8 MiB**, midpoint 6 MiB → **~115 MiB usable**. This cannot be computed exactly from a desk:
the UBIFS documentation states plainly that *"Precise index size is not known"*, and that UBIFS
deliberately reports less free space than it has. Run `mkfs.ubifs` on the real geometry to close this.

### The compression `[measured]`

UBIFS compresses each **4 KiB data node independently**, so it does not achieve whole-file `gzip`
ratios. Measured on the real flight data, compressing in independent 4 KiB blocks:

| Data | zlib-6 | weak-compressor proxy (zlib-1) | whole-file, for contrast |
|---|---|---|---|
| JSONL as written today | **4.11×** | 3.72× | 8.29× |
| Packed binary AHRS (float32) | **1.84×** | 1.76× | — |
| FLAC audio | **1.11×** | 1.11× | — |

`[fetched]` UBIFS "supports only zlib and LZO compressors". LZO is not measurable on this Mac;
zlib-1 is used as a weak-compressor bracket, and the table below shows the choice barely matters —
because audio dominates and FLAC is already incompressible.

### Net effect `[derived]`

| Configuration | raw 128 MiB | UBIFS `compr=none` | UBIFS zlib | UBIFS weak |
|---|---|---|---|---|
| As flown today: JSONL + FLAC | 5.7 min | 5.1 min (−10%) | **13.7 min** | 13.0 min |
| Packed binary AHRS + FLAC | 21.0 min | 18.9 min (−10%) | **23.5 min** | 23.2 min |
| Packed binary AHRS, no audio | 78.9 min | 70.9 min (−10%) | **130.2 min** | 124.9 min |

**The shape of the answer:** with compression off, UBIFS costs a flat 10%. With compression on, it
pays for that many times over on the JSONL (5.7 → 13.7 min, a 2.4× gain) — but only **+12%** on the
packed-binary + FLAC configuration, because there is almost nothing left to compress once you have
packed the log yourself and the audio is already FLAC.

**So the two savings do not stack.** Packing the AHRS log yourself is worth 3.7× on its own; UBIFS
compression is worth 2.4× on its own; doing both is worth 4.1×, not 8.8×. Pack the log because it
also cuts I/O and CPU, and treat UBIFS's compression as insurance rather than budget.

### Practical notes

- **Turn compression off per-inode on the audio** (`chattr +m` on the audio directory). It costs no
  capacity — FLAC is incompressible at 1.11× — and saves the CPU of trying on every 4 KiB node.
- **Do not trim the 20/1024 bad-block reserve** to reclaim space. The datasheet guarantees only
  1004 of 1024 valid blocks over life; the UBI default is sized to exactly that.
- **Expect `df` to under-report.** UBIFS reports minimum free space by design. Do not chase the
  discrepancy or size against `df`.
- UBIFS does not change the conclusion in §4: even at 23.5 min, this part cannot hold a sortie.

---

## Sources

- `[fetched]` Winbond, *W25N01GV 3V 1G-bit Serial SLC NAND Flash Memory*, Revision L, 2018-05-09 —
  array organisation p.9, Table 10.1 Valid Block Number §10.1, spare area map p.12.
  <https://cdn.sparkfun.com/assets/5/a/c/1/3/W25N01GVZEIGIT_datasheet.pdf>
- `[measured]` `~/Downloads/RV-8_CM5_F01/` — `session_20260828T084535Z.jsonl`, `audio/*.flac`,
  `audio/*.sidecar.jsonl`, `README.md`. 59/59 SHA-256 verified per that dataset's MANIFEST.
- `[repo]` `docs/aeronode-cm5-software-rev1.md` (part selection),
  `docs/audio-board-level-shifter.md` §3.1.2 (the board's own 48 kHz / 3-mic audio path — note the
  flight recording above was a single 96 kHz UMIK capsule on the CM5, **not** the ADAU1860 path).
- `[fetched]` linux-mtd, *UBI — Flash space overhead* and *Reserved blocks for bad block handling*:
  <http://www.linux-mtd.infradead.org/doc/ubi.html> (note: HTTPS on this host serves a mismatched
  certificate — fetched over HTTP).
- `[fetched]` linux-mtd, *UBIFS — Flash space accounting issues* ("Precise index size is not known")
  and the compressor list: <http://www.linux-mtd.infradead.org/doc/ubifs.html>
