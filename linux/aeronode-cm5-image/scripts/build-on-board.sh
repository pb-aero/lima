#!/usr/bin/env bash
# Stage 1 of 2: make ArduPilot run on the AeroNode rev 0.0.2 CM5.
# RUN ON THE BOARD, as a normal user (NOT root -- the prereqs script refuses root).
#
#   ./build-on-board.sh preflight   # facts only, changes nothing. Run first.
#   ./build-on-board.sh clone
#   ./build-on-board.sh prereqs     # apt + venv. Slow. Needs sudo.
#   ./build-on-board.sh patch       # apply the two MANDATORY upstream patches
#   ./build-on-board.sh hwdef       # install the aeronode-cm5 board target
#   ./build-on-board.sh build
#   ./build-on-board.sh verify      # the part that actually matters
#   ./build-on-board.sh install     # /usr/local/bin + systemd unit
#   ./build-on-board.sh all
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AP_DIR="${AP_DIR:-$HOME/ardupilot}"
BOARD="${BOARD:-aeronode-cm5}"
VEHICLES="${VEHICLES:-plane}"
BRANCH="${BRANCH:-master}"
JOBS="${JOBS:-$(nproc)}"
VENV="$HOME/venv-ardupilot"

say()  { printf '\n=== %s\n' "$*"; }
fail() { printf '\nFATAL: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -ne 0 ] || fail "do not run as root"

preflight() {
  say "machine"
  echo "hostname : $(hostname)"
  echo "arch     : $(uname -m)"
  echo "kernel   : $(uname -r)"
  echo "model    : $(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo unknown)"
  echo "codename : $(lsb_release -c -s 2>/dev/null || echo 'lsb_release missing')"
  echo "cores    : $(nproc)"
  echo "ram      : $(awk '/MemTotal/{printf "%.1f GiB\n", $2/1048576}' /proc/meminfo)"
  case "$(tr -d '\0' < /proc/device-tree/model 2>/dev/null)" in
    *"Compute Module 5"*|*CM5*) echo "verdict  : CM5 confirmed" ;;
    *) echo "WARNING  : this does not look like a CM5. The hwdef assumes one." ;;
  esac

  say "ArduPilot's own board-type test (must say 0x10 -> RPI_5)"
  "$HERE/scripts/discover-buses.sh" 2>/dev/null | sed -n '/1\. is this board/,/^note/p' || true

  say "disk"
  df -h "$(dirname "$AP_DIR")" | tail -1
  avail_kb=$(df -Pk "$(dirname "$AP_DIR")" | tail -1 | awk '{print $4}')
  [ "$avail_kb" -ge 10485760 ] || echo "WARNING: under 10 GiB free (src ~2 GB + build ~2 GB + apt ~1 GB)"

  say "codename must be one install-prereqs-ubuntu.sh accepts"
  case "$(lsb_release -c -s 2>/dev/null)" in
    bookworm|trixie|bullseye) echo "OK" ;;
    *) echo "UNSUPPORTED -- the prereqs script will exit 1. Stop and report." ;;
  esac
}

clone() {
  say "clone"
  if [ -d "$AP_DIR/.git" ]; then
    echo "$AP_DIR exists -- skipping"
  else
    git clone --recurse-submodules -b "$BRANCH" \
      https://github.com/ArduPilot/ardupilot.git "$AP_DIR"
  fi
  git -C "$AP_DIR" rev-parse HEAD | sed 's/^/upstream HEAD: /'
}

prereqs() {
  say "apt + venv"
  ( cd "$AP_DIR" && ./Tools/environment_install/install-prereqs-ubuntu.sh -y )
  [ -d "$VENV" ] || python3 -m venv --system-site-packages "$VENV"
  # shellcheck disable=SC1091
  . "$VENV/bin/activate"
  pip install -q --upgrade pip empy pexpect future pymavlink
  echo "venv ready: $VENV"
}

patch_tree() {
  say "apply the two MANDATORY patches"
  # 0001 Util_RPI soc-node prefix compare.  Verified STILL UNLANDED upstream
  # on 2026-11-05: master has strncmp(entry->d_name,"soc",4).  Without it a
  # 2712 kernel (node soc@107c000000) reports UNKNOWN_BOARD and
  # GPIO_RPI::init() calls AP_HAL::panic() at startup.
  # 0002 adds HAL_BOARD_SUBTYPE_LINUX_PI5 + the generic pi5 board, which the
  # aeronode-cm5 hwdef's CONFIG_HAL_BOARD_SUBTYPE refers to.
  for p in "$HERE"/patches/000*.patch; do
    n=$(basename "$p")
    if git -C "$AP_DIR" apply --check "$p" 2>/dev/null; then
      git -C "$AP_DIR" apply "$p" && echo "applied  $n"
    elif git -C "$AP_DIR" apply --check --reverse "$p" 2>/dev/null; then
      echo "already  $n"
    else
      fail "$n neither applies nor is already applied -- upstream moved. Re-roll it."
    fi
  done
  say "positive control: the fix is in the tree"
  grep -n 'strncmp(entry->d_name, "soc", 3)' \
    "$AP_DIR/libraries/AP_HAL_Linux/Util_RPI.cpp" \
    || fail "soc-node fix NOT present after patching"
}

hwdef() {
  say "install the aeronode-cm5 board target"
  dst="$AP_DIR/libraries/AP_HAL_Linux/hwdef/aeronode-cm5"
  mkdir -p "$dst"
  cp "$HERE/hwdef/aeronode-cm5/hwdef.dat" "$dst/hwdef.dat"
  echo "installed -> $dst/hwdef.dat"
}

build() {
  say "build"
  # [scar] Activate the venv BEFORE configure, not just before the build: waf
  # caches the interpreter it saw at configure time, and a configure run
  # outside the venv produces "ModuleNotFoundError: No module named 'em'"
  # from dronecangen that looks exactly like a missing dependency.
  # shellcheck disable=SC1091
  . "$VENV/bin/activate"
  ( cd "$AP_DIR" && ./waf configure --board="$BOARD" && ./waf "$VEHICLES" -j"$JOBS" )
}

verify() {
  say "VERIFY -- read the generated header, never the exit code"
  # [scar 2026-09-10] `waf configure` printed "finished successfully" while the
  # board was probing the WRONG IMU, because the generator APPENDS sensor lines
  # and `undef` does not remove them. The evidence is build/<board>/hwdef.h.
  h="$AP_DIR/build/$BOARD/hwdef.h"
  [ -f "$h" ] || fail "no $h -- run build first"
  for k in HAL_INS_PROBE_LIST HAL_MAG_PROBE_LIST HAL_BARO_PROBE_LIST \
           HAL_INS_HIGHRES_SAMPLE CONFIG_HAL_BOARD_SUBTYPE; do
    printf '%-26s ' "$k"
    grep -m1 "define $k" "$h" | sed "s/.*define $k//" || echo "(absent)"
  done

  say "it must probe the ICM-45686 and NOTHING ELSE as an IMU"
  if grep -q 'HAL_INS_PROBE_LIST' "$h"; then
    grep -m1 'HAL_INS_PROBE_LIST' "$h" | grep -qiE 'mpu9250|icm20602|lsm9ds|bmi088' \
      && fail "a foreign IMU leaked into the probe list -- you inherited another board's hwdef"
    echo "OK -- no foreign IMU in the probe list"
  fi

  say "binary"
  bin="$AP_DIR/build/$BOARD/bin/arduplane"
  [ -x "$bin" ] || fail "no binary at $bin"
  file "$bin"
  nm -C "$bin" 2>/dev/null | grep -c Invensensev3 | sed 's/^/Invensensev3 symbols: /'
  nm -C "$bin" 2>/dev/null | grep -c 'AP_InertialSensor_Invensense::' \
    | sed 's/^/legacy Invensense symbols (want 0): /'

  say "run it -- it must print 'RPI 5'"
  timeout 12 "$bin" -A udp:127.0.0.1:14550 2>&1 | head -40 | tee /tmp/ap-first-run.txt || true
  if grep -q 'RPI 5' /tmp/ap-first-run.txt; then
    echo "OK -- detected as RPI 5"
  elif grep -q 'Cannot detect board-type' /tmp/ap-first-run.txt; then
    fail "board-type detection FAILED -- GPIO is running blind; patch 0001 did not take"
  else
    echo "INCONCLUSIVE -- neither string printed. Read /tmp/ap-first-run.txt."
  fi
}

install_svc() {
  say "install binary + service"
  sudo install -m755 "$AP_DIR/build/$BOARD/bin/arduplane" /usr/local/bin/arduplane
  sudo mkdir -p /var/lib/ardupilot
  sudo install -m644 "$HERE/service/arduplane.service" \
    /etc/systemd/system/arduplane.service
  sudo install -m755 "$HERE/aerosync/ekf_bridge.py" /usr/local/bin/ekf-bridge
  sudo systemctl daemon-reload
  echo "installed. NOT enabled -- read README section 7 and set the MAVLink"
  echo "endpoint in /etc/systemd/system/arduplane.service first, then:"
  echo "  sudo systemctl enable --now arduplane"
}

case "${1:-}" in
  preflight) preflight ;;
  clone)     clone ;;
  prereqs)   prereqs ;;
  patch)     patch_tree ;;
  hwdef)     hwdef ;;
  build)     build ;;
  verify)    verify ;;
  install)   install_svc ;;
  all)       clone; prereqs; patch_tree; hwdef; build; verify ;;
  *) sed -n '2,14p' "$0"; exit 1 ;;
esac
