#!/usr/bin/env bash
# Install ArduPilot (Linux HAL) on a Raspberry Pi 5 running Raspberry Pi OS.
# RUN ON THE PI, as a normal user (NOT root, NOT sudo -- the prereqs script refuses root).
#
#   ./install_ardupilot.sh preflight   # facts only, changes nothing. Run this first.
#   ./install_ardupilot.sh clone       # clone ardupilot + submodules (~2 GB)
#   ./install_ardupilot.sh prereqs     # apt + python venv. Slow. Needs sudo password.
#   ./install_ardupilot.sh build       # waf configure + build. Slow.
#   ./install_ardupilot.sh verify      # prove the binary exists, is native, and runs
#   ./install_ardupilot.sh all         # clone -> prereqs -> build -> verify
#
# Knobs (env):
#   AP_DIR    where to clone            default $HOME/ardupilot
#   BOARD     waf --board target        default linux   (generic; see NOTES.md for HATs)
#   VEHICLES  waf targets to build      default plane
#   BRANCH    git branch/tag to check out  default master
#   JOBS      parallel compile jobs     default nproc
set -euo pipefail

AP_DIR="${AP_DIR:-$HOME/ardupilot}"
BOARD="${BOARD:-linux}"
VEHICLES="${VEHICLES:-plane}"
BRANCH="${BRANCH:-master}"
JOBS="${JOBS:-$(nproc)}"
VENV="$HOME/venv-ardupilot"

say()  { printf '\n=== %s\n' "$*"; }
fail() { printf '\nFATAL: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -ne 0 ] || fail "do not run as root -- install-prereqs-ubuntu.sh refuses to run as root"

preflight() {
  say "machine"
  echo "hostname : $(hostname)"
  echo "arch     : $(uname -m)"
  echo "kernel   : $(uname -r)"
  echo "model    : $(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo unknown)"
  echo "codename : $(lsb_release -c -s 2>/dev/null || echo 'lsb_release missing')"
  echo "cores    : $(nproc)"
  echo "ram      : $(awk '/MemTotal/{printf "%.1f GiB\n", $2/1048576}' /proc/meminfo)"

  say "disk on $(dirname "$AP_DIR")"
  df -h "$(dirname "$AP_DIR")" | tail -1
  avail_kb=$(df -Pk "$(dirname "$AP_DIR")" | tail -1 | awk '{print $4}')
  if [ "$avail_kb" -lt 10485760 ]; then
    echo "WARNING: under 10 GiB free. Source ~2 GB + build tree ~2 GB + apt ~1 GB."
  fi

  say "already installed?"
  [ -d "$AP_DIR" ] && echo "$AP_DIR EXISTS -- clone stage will skip it" || echo "$AP_DIR absent (clean install)"
  [ -d "$VENV" ]   && echo "$VENV EXISTS" || echo "$VENV absent"

  say "swap (waf link steps are memory-hungry on 4 GB boards)"
  free -h | sed -n '1,3p'

  say "codename must be one the ArduPilot prereqs script accepts"
  case "$(lsb_release -c -s 2>/dev/null)" in
    bookworm|trixie|bullseye) echo "OK -- supported" ;;
    *) echo "UNSUPPORTED by install-prereqs-ubuntu.sh -- it will exit 1. Stop here and report." ;;
  esac
}

clone() {
  if [ -d "$AP_DIR/.git" ]; then
    say "$AP_DIR already a git repo -- updating instead of cloning"
    git -C "$AP_DIR" fetch --all --tags
    git -C "$AP_DIR" checkout "$BRANCH"
    git -C "$AP_DIR" pull --ff-only || true
  else
    say "cloning ArduPilot ($BRANCH) into $AP_DIR"
    git clone --recurse-submodules -b "$BRANCH" https://github.com/ArduPilot/ardupilot.git "$AP_DIR"
  fi
  say "syncing submodules"
  git -C "$AP_DIR" submodule update --init --recursive
  echo "HEAD: $(git -C "$AP_DIR" rev-parse HEAD)"
}

prereqs() {
  [ -d "$AP_DIR" ] || fail "$AP_DIR missing -- run the clone stage first"
  say "installing prerequisites (apt + pip into $VENV)"
  echo "Skipping the SITL graphics stack, coverage tools and the STM32 cross-toolchain:"
  echo "none of it is needed for a native Linux-HAL build, and wxPython/opencv build"
  echo "from source on ARM and take hours."
  cd "$AP_DIR"
  SKIP_AP_GRAPHIC_ENV=1 \
  SKIP_AP_COV_ENV=1 \
  SKIP_AP_EXT_ENV=1 \
  DO_AP_STM_ENV=0 \
  DO_PYTHON_VENV_ENV=0 \
  Tools/environment_install/install-prereqs-ubuntu.sh -y
  [ -d "$VENV" ] || fail "expected venv at $VENV -- the prereqs script did not create it"
  echo "venv ready: $VENV"
}

build() {
  [ -d "$AP_DIR" ] || fail "$AP_DIR missing -- run the clone stage first"
  [ -d "$VENV" ]   || fail "$VENV missing -- run the prereqs stage first"
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  cd "$AP_DIR"
  say "waf configure --board=$BOARD"
  ./waf configure --board="$BOARD"
  say "waf $VEHICLES  (-j$JOBS)"
  ./waf -j"$JOBS" $VEHICLES
}

verify() {
  cd "$AP_DIR"
  say "artefacts in build/$BOARD/bin"
  ls -la "build/$BOARD/bin/" || fail "no build/$BOARD/bin -- the build did not produce binaries"

  local ok=0
  for b in "build/$BOARD/bin/"*; do
    [ -x "$b" ] || continue
    say "$b"
    file "$b"
    file "$b" | grep -q "aarch64" || echo "WARNING: not an aarch64 binary -- wrong toolchain for this Pi"
    echo "--- it starts and reports the board it thinks it is on ---"
    # HAL_INS_NONE means it will not arm; we only want the startup banner.
    timeout 8 "$b" -h >/tmp/ap_help.$$ 2>&1 || true
    timeout 8 "$b"    >/tmp/ap_run.$$  2>&1 || true
    head -20 /tmp/ap_help.$$ /tmp/ap_run.$$ 2>/dev/null || true
    if grep -qi "RPI 5" /tmp/ap_run.$$ /tmp/ap_help.$$ 2>/dev/null; then
      echo ">>> CONFIRMED: ArduPilot detected LINUX_BOARD_TYPE::RPI_5 (RP1 GPIO backend)"
      ok=1
    fi
    rm -f /tmp/ap_help.$$ /tmp/ap_run.$$
  done
  say "summary"
  echo "board target : $BOARD"
  echo "vehicles     : $VEHICLES"
  echo "source HEAD  : $(git -C "$AP_DIR" rev-parse HEAD)"
  echo "binaries     : $AP_DIR/build/$BOARD/bin/"
  [ "$ok" -eq 1 ] && echo "Pi 5 detection: PROVEN at runtime" \
                  || echo "Pi 5 detection: NOT OBSERVED -- see NOTES.md §4 before trusting this build on hardware"
}

case "${1:-}" in
  preflight) preflight ;;
  clone)     clone ;;
  prereqs)   prereqs ;;
  build)     build ;;
  verify)    verify ;;
  all)       preflight; clone; prereqs; build; verify ;;
  *)         sed -n '2,20p' "$0"; exit 1 ;;
esac
