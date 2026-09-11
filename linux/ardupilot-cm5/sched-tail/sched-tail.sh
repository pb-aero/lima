#!/usr/bin/env bash
# sched-tail.sh -- does this host meet the ICM-45686 FIFO deadline at a given
# IMU backend rate, under representative AeroNode load?
#
# The question this answers is NOT "how fast is the machine". It is: can a
# SCHED_FIFO priority-12 thread -- ArduPilot's IMU bus poller, below the UART
# thread at 14 and level with the flight loop -- ever be denied the CPU for
# longer than the sensor's FIFO can absorb? One breach loses delta-angle
# samples, and a lost sample is a permanent hole in an attitude integral.
#
# Deadlines (ICM-45686, 2 KB FIFO, 20-byte HiRes packets -> 105 samples):
#   INS_GYRO_RATE 0 = 1 kHz -> 105 ms   2 = 4 kHz -> 26 ms
#   INS_GYRO_RATE 1 = 2 kHz ->  53 ms   3 = 8 kHz -> 13 ms
#
# Two instruments, deliberately: cyclictest (the standard, comparable number)
# and poller_probe (timerfd+poll, the shape ArduPilot actually uses, and the
# only one that reports consecutive missed periods -- the FIFO's own currency).
# If they disagree, do not average them; find out why.
#
# Usage: sudo ./sched-tail.sh [--rate 4000] [--seconds 300] [--skip-selftest]
set -uo pipefail

RATE=4000
SECONDS_RUN=300
PRIO=12
SKIP_SELFTEST=0
OUT="sched-tail-$(date +%Y%m%d-%H%M%S)"

# Keep argv for the re-exec below. The parse loop shifts it away, and re-execing
# with an emptied "$@" silently reran the whole harness on DEFAULTS -- measured
# 2026-09-10: asked for 8 kHz/20 s, got 4 kHz/300 s, and the report looked
# perfectly plausible. A wrapper that loses its arguments is worse than one that
# fails, because the output does not admit it.
ORIG_ARGS=("$@")

while [ $# -gt 0 ]; do
  case "$1" in
    --rate) RATE="$2"; shift 2;;
    --seconds) SECONDS_RUN="$2"; shift 2;;
    --prio) PRIO="$2"; shift 2;;
    --skip-selftest) SKIP_SELFTEST=1; shift;;
    *) echo "unknown option: $1"; exit 1;;
  esac
done

HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$OUT"
LOG="$OUT/report.txt"
# NOT `exec > >(tee "$LOG")`. Process substitution SETS $! in bash, so a later
# `LOAD_PIDS+=($!)` that runs without an intervening background job captures
# tee's PID -- and teardown then kills the script's own logger, which is
# exactly what happened on 2026-09-10 (the run died mid-teardown at
# `kill -9 <tee>`). Re-exec under an ordinary pipe instead: $! is never
# touched, and every background job below redirects its own fds so nothing
# holds the pipe open at exit.
if [ -z "${SCHED_TAIL_WRAPPED:-}" ]; then
  export SCHED_TAIL_WRAPPED=1
  # NOT `exec "$0" ... | tee`. In a pipeline the exec only replaces the
  # pipeline's SUBSHELL -- the parent then falls through and runs the entire
  # harness a second time, unwrapped. Measured 2026-09-10: two complete runs,
  # two sets of load generators, one log. Run it, then exit explicitly.
  "$0" "${ORIG_ARGS[@]:-}" 2>&1 | tee "$LOG"
  exit "${PIPESTATUS[0]}"
fi

say() { printf '\n=== %s ===\n' "$*"; }
warn() { printf '  !! %s\n' "$*"; }

# ---------------------------------------------------------------------------
say "0. Identify the box"
echo "  invoked as : rate=${RATE} Hz  duration=${SECONDS_RUN}s  prio=${PRIO}  selftest=$([ "$SKIP_SELFTEST" = 0 ] && echo on || echo off)"
# Hostnames and IPs are both weak identifiers in this fleet -- one box renames
# itself seconds into boot, and the IPs move. Record what cannot be argued with.
echo "  model      : $(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo UNKNOWN)"
echo "  machine-id : $(cat /etc/machine-id 2>/dev/null || echo UNKNOWN)"
echo "  hostname   : $(hostname)  (weak identifier -- do not cite alone)"
echo "  kernel     : $(uname -r)"
echo "  preempt    : $(grep -o 'PREEMPT[_A-Z]*' /proc/version | tr '\n' ' ')"
echo "  cores      : $(nproc)"
echo "  governor   : $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo n/a)"
echo "  isolcpus   : $(cat /sys/devices/system/cpu/isolated 2>/dev/null || echo none)"
echo "  soc ranges : $(od -An -tx1 -N16 /proc/device-tree/soc*/ranges 2>/dev/null | tr -s ' ')"

case "$(grep -o 'PREEMPT_RT' /proc/version)" in
  PREEMPT_RT) echo "  -> PREEMPT_RT: latency is bounded by design.";;
  *) warn "NOT PREEMPT_RT. SCHED_FIFO here does not preempt IRQ handlers or"
     warn "kernel critical sections. There is no worst case to quote, only a"
     warn "tail you have not yet observed.";;
esac
GOV=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo n/a)
[ "$GOV" = "performance" ] || warn "governor is '$GOV', not 'performance' -- frequency ramp on wake adds latency."

# ---------------------------------------------------------------------------
say "1. Preflight"
FAIL=0
if [ "$(id -u)" != "0" ]; then
  warn "not root. SCHED_FIFO will probably be refused; both instruments will abort."
fi
command -v cyclictest >/dev/null || { warn "cyclictest missing -> apt install rt-tests"; FAIL=1; }
command -v cc >/dev/null || command -v gcc >/dev/null || { warn "no C compiler -> apt install build-essential"; FAIL=1; }
[ "$FAIL" = 0 ] || { echo "PREFLIGHT FAILED -- fix the above, nothing was measured."; exit 1; }

CC=$(command -v cc || command -v gcc)
"$CC" -O2 -Wall -o "$OUT/poller_probe" "$HERE/poller_probe.c" -lrt || {
  echo "poller_probe failed to build -- nothing was measured."; exit 1; }
echo "  cyclictest   : $(cyclictest --help 2>&1 | head -1)"
echo "  poller_probe : built"

# ---------------------------------------------------------------------------
# Load generators. Each one reports HONESTLY whether it actually started.
# A load that silently did not run produces a clean result that looks exactly
# like a pass -- that is the failure mode this whole script exists to avoid.
LOAD_PIDS=()
LOAD_STATUS=()

# Every load generator is bounded by WALL CLOCK, not by being killed.
# Learned 2026-09-10: an unbounded `( while :; do :; done ) &` fallback and an
# unbounded `dd` loop both survived teardown and sat at 95% CPU on the target
# for six minutes. The kill is now belt to the self-termination braces, never
# the primary mechanism -- the same lesson as the self-test spinner.
#
# Every background job also gets </dev/null >/dev/null 2>&1. Without it the
# children inherit the script's stdout, which is a pipe into tee, and tee
# cannot exit until the last writer closes -- so the script appears to hang at
# the end even after the work is done. That is what happened on the first run.
LOAD_SECONDS=$((SECONDS_RUN + 30))

start_load() {
  say "3. Start representative load"
  echo "  (all generators self-terminate after ${LOAD_SECONDS}s)"
  # (a) Hailo 8L inference over PCIe -- the load unique to AeroNode
  if command -v hailortcli >/dev/null 2>&1; then
    ( e=$((SECONDS+LOAD_SECONDS))
      while [ $SECONDS -lt $e ]; do hailortcli run-benchmark || break; done
    ) </dev/null >/dev/null 2>&1 &
    LOAD_PIDS+=($!)
    LOAD_STATUS+=("hailo: STARTED -- replace 'run-benchmark' with the real .hef before trusting this")
  else
    LOAD_STATUS+=("hailo: *** NOT PRESENT -- PCIe/NPU load is ABSENT from this run ***")
  fi
  # (b) audio: multi-lane I2S through the ALSA card, if one exists.
  #     Addressed as hw:CARD=<name> -- card NUMBERS are not stable on this
  #     fleet (measured: the same box, same kernel, card 0 one day and 1 the
  #     next), so hw:0,0 is never correct.
  local card
  card=$(aplay -l 2>/dev/null | sed -n 's/^card [0-9]*: \([^ ]*\).*/\1/p' | head -1)
  if [ -n "${card:-}" ]; then
    ( timeout "$LOAD_SECONDS" aplay -D "hw:CARD=$card,DEV=0" \
        -f S32_LE -r 48000 -c 8 /dev/zero ) </dev/null >/dev/null 2>&1 &
    LOAD_PIDS+=($!)
    LOAD_STATUS+=("audio: STARTED on hw:CARD=$card -- NOTE: verify this is the I2S/A2B card, not HDMI")
  else
    LOAD_STATUS+=("audio: *** NO ALSA CARD -- I2S load is ABSENT from this run ***")
  fi
  # (c) eMMC/NAND write pressure
  ( e=$((SECONDS+LOAD_SECONDS))
    while [ $SECONDS -lt $e ]; do
      dd if=/dev/zero of="$OUT/.ballast" bs=1M count=64 conv=fsync || break
    done
  ) </dev/null >/dev/null 2>&1 &
  LOAD_PIDS+=($!)
  LOAD_STATUS+=("storage: STARTED (64 MB fsync loop)")
  # (d) CPU + memory
  if command -v stress-ng >/dev/null 2>&1; then
    ( stress-ng --cpu "$(nproc)" --vm 2 --vm-bytes 256M \
        --timeout "${LOAD_SECONDS}s" ) </dev/null >/dev/null 2>&1 &
    LOAD_PIDS+=($!)
    LOAD_STATUS+=("cpu/mem: STARTED (stress-ng, ${LOAD_SECONDS}s)")
  else
    local i
    for i in $(seq 1 "$(nproc)"); do
      ( e=$((SECONDS+LOAD_SECONDS)); while [ $SECONDS -lt $e ]; do :; done ) \
        </dev/null >/dev/null 2>&1 &
      LOAD_PIDS+=($!)
    done
    LOAD_STATUS+=("cpu/mem: STARTED ($(nproc) bounded spinners -- stress-ng absent, MEMORY pressure NOT exercised)")
  fi
  printf '  %s\n' "${LOAD_STATUS[@]}"
}

stop_load() {
  local p
  [ "${#LOAD_PIDS[@]}" = 0 ] || echo "  teardown: load pids ${LOAD_PIDS[*]}"
  # -9 the SUBSHELL FIRST. Measured 2026-09-10: sending TERM to the parent and
  # then removing the ballast file left a fresh 64 MB file behind, timestamped
  # three seconds AFTER the report finished -- the `while ... dd ...` loop was
  # still alive and simply respawned dd after the rm. Kill the respawner before
  # its child, or you are racing a loop you have not stopped.
  for p in "${LOAD_PIDS[@]:-}"; do
    [ -n "$p" ] || continue
    # PROVE it is ours before killing it. A stale or mis-captured $! is how a
    # teardown reaches out and kills something it does not own -- on
    # 2026-09-10 that was this script's own `tee`. A PID is also reusable, so
    # "I recorded it earlier" is not proof it is still the same process.
    # $BASHPID, not $$. Inside a pipeline or subshell $$ still reports the
    # ORIGINAL shell's pid, so comparing a child's ppid against $$ rejects
    # every genuine child. Measured 2026-09-10: the guard refused to kill
    # anything at all, which is the safe direction to fail but still wrong.
    if [ "$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')" != "${BASHPID:-$$}" ]; then
      warn "skipping pid $p: not a child of this script (${BASHPID:-$$}) -- not ours to kill"
      continue
    fi
    kill -9 "$p" 2>/dev/null
    pkill -9 -P "$p" 2>/dev/null    # dd / aplay / timeout / stress-ng
  done
  # deliberately NOT `wait`: if one kill missed, wait hangs forever and the
  # script looks broken when only the teardown is. Every generator is
  # wall-clock bounded anyway, so a survivor exits on its own.
  LOAD_PIDS=()
  sleep 1
  rm -f "$OUT"/.ballast
}
trap 'stop_load; pkill -9 -P $$ -x cyclictest 2>/dev/null; rm -f "$OUT"/.ballast' EXIT

# ---------------------------------------------------------------------------
if [ "$SKIP_SELFTEST" = 0 ]; then
  say "2. POSITIVE CONTROL -- prove the instrument can see a stall"

  # Two earlier designs of this control were wrong, and both are worth knowing:
  #
  # (1) `chrt -f 20 taskset -c 0 timeout 12 sh -c 'while :; do :; done'` WEDGED
  #     CPU0 for four minutes. `timeout` is the parent and inherits the same
  #     SCHED_FIFO priority as the spinner; at equal priority FIFO never
  #     preempts, so the spinner never yielded, `timeout` never ran, and its
  #     SIGALRM never fired. A watchdog that must be scheduled cannot police a
  #     task that will not yield.
  #
  # (2) A self-terminating spinner at PRIO+1 pinned to the probe's CPU was safe
  #     but did not work: measured three times on 6.18.39+rpt-rpi-2712, a
  #     SCHED_FIFO prio-13 hog at 100% on CPU0 did NOT delay a prio-12 timerfd
  #     sleeper pinned to the same CPU by more than ~12 us. Both were confirmed
  #     on CPU0 (psr=0) with affinity mask 1. Unexplained -- see README.
  #
  # So the control is now SIGSTOP: an unarguable, bounded stall that depends on
  # no scheduler policy, cannot wedge a core, and exercises exactly the
  # accounting path the verdict rests on. Verified 2026-09-10: a ~100 ms stop
  # was reported as 436 missed periods and a 109.148 ms worst stall, exit 2.
  echo "  RT throttling (context only): $(cat /proc/sys/kernel/sched_rt_runtime_us 2>/dev/null || echo unknown)/$(cat /proc/sys/kernel/sched_rt_period_us 2>/dev/null || echo unknown) us"

  # Stop for 3x the deadline so the breach is unambiguous at any rate.
  DEADLINE_MS=$(awk -v n=105 -v r="$RATE" 'BEGIN{printf "%.0f", n*1000/r}')
  STOP_MS=$((DEADLINE_MS * 3))
  echo "  Injecting a ${STOP_MS} ms SIGSTOP (3x the ${DEADLINE_MS} ms deadline at ${RATE} Hz)."
  echo "  The probe MUST report it, within 50-200% of the injected duration."

  "$OUT/poller_probe" --rate "$RATE" --seconds 6 --prio "$PRIO" > "$OUT/selftest.txt" 2>&1 &
  PP=$!
  sleep 2
  if ! kill -0 "$PP" 2>/dev/null; then
    echo "  SELF-TEST INCONCLUSIVE: probe exited early. Its output:"
    sed 's/^/    /' "$OUT/selftest.txt"; exit 3
  fi
  # sub-second sleep: GNU coreutils takes a fraction, others do not
  STOP_S=$(awk -v m="$STOP_MS" 'BEGIN{ printf "%.3f", m/1000 }')
  kill -STOP "$PP"
  sleep "$STOP_S" 2>/dev/null || perl -e "select(undef,undef,undef,$STOP_S)" 2>/dev/null || sleep 1
  kill -CONT "$PP"
  wait "$PP"; RC=$?

  grep -E 'max lateness|missed periods|WORST STALL|VERDICT|FATAL' "$OUT/selftest.txt" | sed 's/^/  /'
  if [ "$RC" = 3 ]; then
    echo "  SELF-TEST INCONCLUSIVE: could not obtain SCHED_FIFO. Nothing measured."; exit 3
  fi
  MEASURED_MS=$(awk '/WORST STALL/ {print $4}' "$OUT/selftest.txt")
  OK=$(awk -v m="${MEASURED_MS:-0}" -v want="$STOP_MS" \
        'BEGIN{ print (m >= want*0.5 && m <= want*2.0) ? "yes" : "no" }')
  if [ "$RC" != 2 ] || [ "$OK" != "yes" ]; then
    echo "  *** SELF-TEST FAILED ***"
    echo "  Injected ${STOP_MS} ms; probe reported ${MEASURED_MS:-none} ms, exit $RC."
    echo "  The instrument does not correctly measure a stall it was subjected to."
    echo "  Every clean number below would be meaningless. Do not proceed."
    exit 4
  fi
  echo "  SELF-TEST PASSED -- injected ${STOP_MS} ms, measured ${MEASURED_MS} ms, verdict BREACHED."
fi

# ---------------------------------------------------------------------------
say "4. NEGATIVE CONTROL -- idle floor, no load"
cyclictest --policy=fifo --priority="$PRIO" --interval=$((1000000/RATE)) \
  --threads=1 --duration=30 --mlockall --quiet 2>&1 | tail -4 | sed 's/^/  cyclictest /'
"$OUT/poller_probe" --rate "$RATE" --seconds 30 --prio "$PRIO" > "$OUT/idle.txt" 2>&1
IDLE_RC=$?
grep -E 'max lateness|missed periods|WORST STALL|VERDICT' "$OUT/idle.txt" | sed 's/^/  probe /'

# ---------------------------------------------------------------------------
start_load
say "5. LOADED RUN -- ${SECONDS_RUN}s at ${RATE} Hz, SCHED_FIFO ${PRIO}"
cyclictest --policy=fifo --priority="$PRIO" --interval=$((1000000/RATE)) \
  --threads=1 --duration="${SECONDS_RUN}" --mlockall --histogram=100000 \
  > "$OUT/cyclictest.txt" 2>&1
grep -E '^# (Min|Avg|Max)|^T:' "$OUT/cyclictest.txt" | tail -4 | sed 's/^/  cyclictest /'
CYC_MAX=$(awk '/^# Max Latencies/ {print $NF}' "$OUT/cyclictest.txt" | tr -d ' ')

set +e
"$OUT/poller_probe" --rate "$RATE" --seconds "$SECONDS_RUN" --prio "$PRIO" \
    > "$OUT/loaded.txt" 2>&1
LOADED_RC=$?
set -e
sed 's/^/  probe /' "$OUT/loaded.txt"
stop_load

# ---------------------------------------------------------------------------
say "6. Verdict"
printf '  %s\n' "${LOAD_STATUS[@]}"
echo
echo "  cyclictest max latency : ${CYC_MAX:-?} us   (wakeup jitter only)"
grep -E 'WORST STALL|deadline|VERDICT' "$OUT/loaded.txt" | sed 's/^/  probe /'
echo
case "$LOADED_RC" in
  0) echo "  RESULT: INS_GYRO_RATE for ${RATE} Hz is SUPPORTED on this host under this load.";;
  2) echo "  RESULT: DEADLINE BREACHED at ${RATE} Hz. Step INS_GYRO_RATE down and re-run.";;
  3) echo "  RESULT: NOT MEASURED -- SCHED_FIFO refused.";;
  *) echo "  RESULT: probe exited $LOADED_RC -- treat as UNKNOWN, not as a pass.";;
esac
echo
echo "  What this run does NOT establish:"
echo "   - Anything about a load you did not stage. Re-read the load lines above;"
echo "     any marked NOT PRESENT means that contention was absent from the result."
echo "   - A worst case. A tail is not a maximum. A ${SECONDS_RUN}s clean run is"
echo "     evidence, not proof, and the excursion you care about may be hourly."
echo "   - The real thing. cyclictest and this probe both measure an idle poller."
echo "     ArduPilot's poller also performs a SPI transfer and contends with the"
echo "     UART(14), RCIN(13) and timer(15) threads, none of which exist here."
echo "     Both instruments therefore UNDERSTATE the jitter the driver will see."
echo "     The definitive number is ArduPilot's own PM log and IMU error counts."
echo
echo "  Artefacts: $OUT/"
