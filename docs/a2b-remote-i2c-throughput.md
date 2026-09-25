# A2B remote I²C as the DVNC coefficient path — bandwidth, and the thing that actually threatens it

**Date:** 2026-09-25 · **Agent:** LIMA · **Status:** analysis from datasheet + errata. Nothing measured.
**Trigger:** JULIETT `2026-09-25-006` §3, on John's instruction — can A2B remote I²C carry ~14 kB/s of
DVNC coefficients alongside the audio, and is SPI a requirement or an optimisation?

Provenance: `[fetched]` = vendor PDF this session, page cited · `[repo]` = in a repository ·
`[derived]` = arithmetic shown · `[measured]` = run on hardware · `[gap]` = not established.

---

## 1. The mechanism — remote I²C rides the superframe header, not the audio slots

`[fetched]` AD2420/26/27/28/29 datasheet p.4:

> *"The embedded control and response frames allow the host to individually address each slave
> transceiver in the system. The host also enables access to remote peripheral devices … for **I²C to
> I²C communication over distance** between multiple nodes."*

`[fetched]` p.5 and p.32 give the frame structure and the capacity:

| | |
|---|---|
| Superframe | **1024 bits**, one per **20.833 µs** at 48 kHz → 49.152 Mbit/s line rate |
| **SCF** (synchronization control frame, downstream) | **64 bits** |
| **SRF** (synchronization response frame, upstream) | **64 bits** |
| Control mode | *"The superframe only has the 64-bit SCF and SRF in the frame **with the control data embedded in the header bits**"* — activity 64/1024 = 6.3% each way, which ADI states and our arithmetic reproduces |

**So control traffic is carried in a 64-bit header per direction per superframe.** It does not consume
audio slots, which answers the "what does it displace" half of the question: **not audio capacity — it
displaces other control traffic.**

## 2. The bandwidth answer: not the problem, and JULIETT's estimate was pessimistic by ~10×

`[derived]` ceiling on **all** downstream control traffic:

```
64 bits x 48 000 superframes/s = 3.072 Mbit/s = 384 kB/s
```

`[repo]` the coefficient stream is **~14 kB/s** (Rev G, under 10% of a 24-bit slot). That is
**3.6% of the ceiling.**

> **JULIETT's `2026-09-25-006` §2 sized this from the local I²C clock — 400 kHz → ~40 kB/s — and
> called it "plausible, not comfortable." That was the wrong model, in our favour.** The 400 kHz bus is
> only the **last hop** at the node; the constraint is the A2B control channel, and its ceiling is
> **9.6× that estimate.**

**The 64 bits are not all payload** — sync, node addressing and protocol overhead live there too, and
ADI does not publish the split. So the honest form of the answer is a sensitivity table:

| Usable payload per SCF | Throughput | Carries 14 kB/s? |
|---|---|---|
| 64 of 64 bits | 384 kB/s | yes — 27× margin |
| 32 | 192 kB/s | yes — 14× |
| 16 | 96 kB/s | yes — 6.9× |
| 8 (one byte) | 48 kB/s | yes — 3.4× |
| **4** | **24 kB/s** | **yes — 1.7×** |

**Even at four usable bits per superframe it fits.** `[derived]` Bandwidth is not the objection.

`[gap]` **The exact SCF field breakdown and the per-transaction latency are not in the datasheet.**
This is the pointer JULIETT asked for: they are in the **A2B Technical Reference Manual**, which is
registered/NDA access, not the public datasheet. **Anyone quoting a precise remote-I²C throughput from
the datasheet is quoting something that is not in it.**

## 3. ⚠ What actually threatens this path — two errata, and the second is decisive

`[repo]` `reports/chris/aeronode/docs/datasheets/ad2428w-silicon-anomalies.md`, which is Chris's lane's
work, not mine.

### 18000052 — remote I²C and GPIO-over-distance fight over exactly these fields

ADI, quoted there:

> *"When host processor performs a remote I2C peripheral access (read/write) … and a
> GPIO-over-Distance (GPIOD) communication happens concurrently, then there will be an arbitration
> conflict … as both would compete for the **SCF and SRF fields** of A2B superframes."*

**Failure modes ADI list: GPIOD request dropped · remote I²C access timeout · remote access
corruption.** `[repo]` Chris's lane has already established that our design uses both **concurrently by
construction, permanently** — cup events arrive by GPIOD while the CM5 is the only I²C master doing
discovery, status polling and configuration through the tunnel.

**Adding a continuous coefficient stream to that contention makes an existing conflict worse.** It does
not create it — Chris's note predates this question — but it is the heaviest new user of the contended
resource.

### 18000075 — a failed coefficient write may not report an error

> **`I2CERR`/NACK may not be reported for remote I²C peripheral access** (affects rev 0.0–0.1).

**This is the one that matters, and it is worse for a coefficient stream than for anything else the
tunnel currently carries.** Configuration writes happen once at startup and are read back. A
coefficient stream is continuous and unattended, so:

> **A dropped coefficient write is silent, and the cup goes on running the previous coefficients with
> nothing raised anywhere.** The ANC does not fail loudly; it quietly stops tracking. That is this
> repo's oldest failure shape — *a silent no-op looks exactly like success* — on the one path whose
> whole purpose is to keep the canceller current.

## 4. So: requirement or optimisation?

**On bandwidth, SPI is an optimisation.** 14 kB/s against a 384 kB/s ceiling, fitting even at four
usable bits per frame. "Faster than necessary" is JULIETT's own test and remote I²C passes it.

**On error detection, the honest answer is that it depends on a fix we have not tried** — and the fix
is cheap and needs no new silicon:

> **Read-back verification.** Write the coefficient block, then read back a checksum over it through
> the same tunnel. `[derived]` that doubles the traffic to **28 kB/s = 7.3% of the SCF ceiling**, still
> comfortable, and it **converts erratum 18000075 from a silent failure into a detected one.** Cost is
> latency and a modest increase in contention with GPIOD; benefit is that the coefficient path becomes
> self-checking rather than trusted.

**Recommendation: prove remote I²C on the boards we own before buying AD243x.** The measurement is
available this month on the AD2428 master/slave/lite set plus 2× EVAL-ADAU1860-1 — which is exactly
what JULIETT said was worth more than the headroom SPI buys. What to measure, with the discriminators
stated first:

| # | Measurement | Pass condition |
|---|---|---|
| 1 | Sustained coefficient throughput through the tunnel | ≥ 14 kB/s sustained, with the audio running |
| 2 | Per-transaction latency, and its **jitter** | jitter matters more than the mean for a periodic push |
| 3 | **Error injection** — force a NACK and see whether it is reported | if it is silent on our silicon rev, read-back verification is mandatory, not optional |
| 4 | Throughput **with GPIOD active concurrently** | this is 18000052's scenario; the negative control is the same run with GPIOD disabled |
| 5 | Does the superframe stay locked under sustained control load | no audio dropout, no re-discovery |

**Measurement 3 is the one that decides the part.** If NACKs are reported on the rev we hold, remote
I²C is sufficient and the AD243x case rests on convenience. If they are not, we need either read-back
verification or SPI — and read-back should be tried first because it costs nothing but code.

## 5. One line in the datasheet that will be used to reopen a settled question

`[fetched]` p.4 says remote peripherals are reached *"via the I²C **or SPI** ports."* **Read in
isolation that contradicts John's correction that the AD2428W has no SPI.**

**It does not, and I checked before repeating it.** `[measured]` that phrase is the **only** occurrence
of "SPI" in the entire AD2420/26/27/28/29 datasheet — there is no SPI pin in the pin table, no SPI
register, no SPI timing specification, nothing. One stray phrase against zero supporting content in
thirty-odd pages is family boilerplate, not a feature.

**So it corroborates the correction rather than undermining it** — and it is recorded here because it
is precisely the kind of line someone finds in three months and reopens the decision with.
