#!/bin/bash
# Catch a 3V3 rail collapse during NAND erase/program, without a scope.
#
# WIRING: one extra wire from the click board's 3V3 pad to Pi header pin 22 (GPIO25).
# 3.3 V into a Pi input is safe. The Pi then acts as a threshold detector: while the rail is
# healthy GPIO25 sits high; if the rail browns out under the charge pump's load it falls below
# the input threshold and gpiomon timestamps the edge. A meter averages such dips away —
# this does not.
#
#   sudo bash ~/aerovault/rail-monitor.sh
#
# Runs the UBI format with the monitor armed, then reports every edge seen.
set -u
exec &> >(tee /home/node/aerovault/rail-monitor.log)

LINE=GPIO25
EVLOG=/home/node/aerovault/rail-events.log

echo "=== steady-state rail level (expect 1 = 3V3 present at the board) ==="
gpioget --numeric -c gpiochip0 "$LINE" 2>/dev/null || gpioget -c gpiochip0 "$LINE" || {
	echo "FAIL: cannot read $LINE — is the monitor wire fitted to pin 22?"; exit 1; }

echo
echo "=== arming edge monitor, then formatting ==="
: > "$EVLOG"
gpiomon --edges=both -c gpiochip0 "$LINE" >> "$EVLOG" 2>&1 &
MON=$!
sleep 1

/usr/sbin/ubiformat /dev/mtd0 -y -q
FMT=$?
echo "ubiformat exit: $FMT"

sleep 1
kill "$MON" 2>/dev/null; wait "$MON" 2>/dev/null

echo
echo "=== rail events during the format ==="
N=$(grep -c . "$EVLOG" 2>/dev/null || echo 0)
if [ "$N" -eq 0 ]; then
	echo "NONE — the rail never crossed the Pi's input threshold."
	echo "That does NOT clear the supply: a droop to 2.0 V still reads high and still"
	echo "browns out the charge pump. It only rules out a collapse to near zero."
else
	echo "$N edges — the rail is collapsing under load. This is the fault."
	head -20 "$EVLOG"
fi
