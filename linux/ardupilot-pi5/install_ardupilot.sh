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
  echo
  echo "!! WARNING -- READ THIS ON A MACHINE WHOSE KERNEL MATTERS !!"
  echo "The upstream prereqs script installs g++-arm-linux-gnueabihf unconditionally."
  echo "On Raspberry Pi OS that drags in linux-libc-dev-armhf-cross -> linux-headers-rpi-*"
  echo "-> linux-image-rpi-*, which installs the CURRENT Pi kernel and rewrites"
  echo "/boot/firmware/kernel_2712.img and kernel8.img. The running kernel does not change,"
  echo "but THE NEXT REBOOT BOOTS THE NEW ONE. Measured on scopenode 2026-09-04:"
  echo "6.12.47+rpt-rpi-2712 -> 6.18.39+rpt-rpi-2712 pending reboot."
  echo "That cross-compiler is not used by --board=linux (TOOLCHAIN native). See RESULTS."
  echo "Current kernel : $(uname -r)"
  echo "Boot kernel now: $(ls -l --time-style=+%Y-%m-%d /boot/firmware/kernel_2712.img 2>/dev/null | awk '{print $6}')"
  echo
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

  say "which GPIO backend was compiled in"
  # For BOARD=linux every HAL_LINUX_GPIO_*_ENABLED defaults to 0 (AP_HAL/board/linux.h),
  # so HAL_Linux_Class.cpp falls through to Empty::GPIO. That means GPIO_RPI is NOT compiled,
  # Util_RPI::detect_linux_board_type() is never called, and the binary will NOT print "RPI 5".
  # Absence of that string is therefore EXPECTED here, not a fault. See NOTES.md section 1a.
  local rpi_gpio="no"
  grep -q "HAL_LINUX_GPIO_RPI_ENABLED 1" "build/$BOARD/ap_config.h" 2>/dev/null && rpi_gpio="yes"
  echo "GPIO_RPI compiled in : $rpi_gpio"
  if [ "$rpi_gpio" = "yes" ]; then
    echo "  -> this build DOES call the Pi-5 detector. It must print 'RPI 5' or it will"
    echo "     AP_HAL::panic(\"Unknown rpi_version\"). Watch the startup output below."
  else
    echo "  -> Empty::GPIO. No /dev/mem mapping, no pin claims, no Pi-5 detector call."
  fi

  say "GPIO18-21 BEFORE running the binary (ADAU1860 I2S1 lives here)"
  pinctrl get 18-21 2>/dev/null || sudo pinctrl get 18-21 2>/dev/null || echo "(pinctrl unavailable)"

  for b in "build/$BOARD/bin/"*; do
    [ -x "$b" ] || continue
    say "$b"
    file "$b"
    file "$b" | grep -q "aarch64" \
      && echo "OK -- native aarch64" \
      || echo "WARNING: not an aarch64 binary -- wrong toolchain for this Pi"
    echo "--- startup output (8 s, then killed; HAL_INS_NONE means it cannot arm) ---"
    timeout 8 "$b" 2>&1 | head -25 || true
  done

  say "GPIO18-21 AFTER running the binary"
  pinctrl get 18-21 2>/dev/null || sudo pinctrl get 18-21 2>/dev/null || echo "(pinctrl unavailable)"
  echo "Any change from the BEFORE block above means ArduPilot touched the ADAU1860 pins."

  say "summary"
  echo "board target : $BOARD"
  echo "vehicles     : $VEHICLES"
  echo "source HEAD  : $(git -C "$AP_DIR" rev-parse HEAD)"
  echo "binaries     : $AP_DIR/build/$BOARD/bin/"
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
