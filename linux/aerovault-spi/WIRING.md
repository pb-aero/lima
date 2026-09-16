# Flash 5 Click → Pi 5, wired direct (no mikroBUS socket)

`[fetched]` mikroBUS signal order, from Zephyr's `dts/bindings/gpio/mikro-bus.yaml`. Both headers
are 8 pins, counted from the notched/top end of the board:

```
LEFT header                      RIGHT header
 1  AN                            1  PWM
 2  RST                           2  INT
 3  CS      <- Pi pin 24 (GPIO8)  3  RX
 4  SCK     <- Pi pin 23 (GPIO11) 4  TX
 5  MISO    -> Pi pin 21 (GPIO9)  5  SCL
 6  MOSI    <- Pi pin 19 (GPIO10) 6  SDA
 7  +3.3V   <- Pi pin 1 or 17     7  +5V      ** NOT this one **
 8  GND     <- Pi pin 6/9/20/25   8  GND
```

**The two headers look identical and their bottom two pins are both power+ground — but the left
pair is 3.3 V and the right pair is 5 V.** Taking power from the right-hand header puts 5 V on a
board whose own specification says it "is designed to be operated only with 3.3V logic level".
If that has happened, the part may be damaged and no amount of re-wiring will bring it back.

**mikroBUS names its data lines from the HOST's point of view** — the binding spells them out as
"MISO (Master Input Slave Output)" and "MOSI (Master Output Slave Input)". So they go **straight
through**, not crossed: click `MISO` → Pi `MISO` (GPIO9), click `MOSI` → Pi `MOSI` (GPIO10).
Boards silkscreened `SDI`/`SDO` instead use the *board's* point of view, where `SDI` is the input
and takes the Pi's MOSI. Same wire, opposite-looking label — which is why it is worth checking
which of the two naming schemes is printed on the board in hand.

**Six wires are needed, not four.** CS, SCK, MISO, MOSI **and** 3V3 **and** GND. A four-wire hookup
with no supply and no ground reads exactly like the failure measured on 2026-09-16: clean bus,
asserting chip select, and `00 00 00` forever.
