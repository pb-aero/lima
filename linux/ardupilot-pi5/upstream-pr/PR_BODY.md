### Summary

Fix Raspberry Pi 5 board detection when the device tree names the SoC node `soc@<addr>` rather than plain `soc`. One character: `strncmp(entry->d_name, "soc", 4)` -> `3`.

### Classification & Testing (check all that apply and add your own)

- [x] Checked by a human programmer
- [ ] Non-functional change
- [ ] No-binary change
- [ ] Infrastructure change (e.g. unit tests, helper scripts)
- [ ] Automated test(s) verify changes (e.g. unit test, autotest)
- [x] Tested manually, description below
- [x] Tested on hardware
- [ ] Logs attached
- [ ] Logs available on request

Tested on a Raspberry Pi 5 Model B Rev 1.1, Raspberry Pi OS trixie, kernel `6.12.47+rpt-rpi-2712`, aarch64.

### Description

`UtilRPI::_get_board_type_using_peripheral_base()` first tries `/proc/device-tree/soc/ranges`. When that path is absent it falls back to scanning `/proc/device-tree` for the SoC node — a fallback added, per its own comment, precisely because *"RPi 5 and RPi Z2 have different soc folder names."*

The scan compares with:

```c
if (strncmp(entry->d_name, "soc", 4) == 0) {
```

A length of 4 includes the NUL terminator, so this is an **exact match for `"soc"`, not the prefix match the surrounding code intends**. On this Pi 5 the node is:

```
$ ls -1d /proc/device-tree/soc*
/proc/device-tree/soc@107c000000
```

`"soc@107c000000"` differs from `"soc"` at byte 3 (`'@'` vs `'\0'`), so nothing matches, `ranges_path` stays empty, and the function reports `"ranges" file not found` and returns `UNKNOWN_BOARD`.

### Why it matters

This is not cosmetic. With `HAL_LINUX_GPIO_RPI_ENABLED`, `GPIO_RPI::init()` reaches its `default:` case:

```c
AP_HAL::panic("Unknown rpi_version, cannot locate peripheral base address");
```

so any board using the RPi GPIO backend — `navio2`, `pilotpi`, `navigator64`, `bhat`, `canzero`, `dark`, `erlebrain2`, `obal`, `pxfmini` — aborts at startup on a kernel that names the node this way. Boards built with `--board=linux` are unaffected, since `GPIO_RPI` is not compiled in there.

### Testing

I extracted the scan into a standalone program (identical logic, `N` parameterised) and ran it against the live `/proc/device-tree` on the Pi 5, as a matched pair of controls:

```
strncmp(d_name, "soc", 4):
    "ranges" file not found
    base = 0x0 -> UNKNOWN_BOARD  ("Cannot detect board-type")

strncmp(d_name, "soc", 3):
    matched node -> /proc/device-tree/soc@107c000000/ranges
    base = 0x10 -> RPI_5
```

The address arithmetic downstream was already correct — reading the file by hand gives:

```
$ od -A d -t x1 -N 16 /proc/device-tree/soc@107c000000/ranges
0000000 00 00 00 00 00 00 00 10 00 00 00 00 80 00 00 00
```

`buf[4..7] = 0x10`, which is exactly the `case 0x10: RPI_5` arm. **The bug is only in finding the file.**

Comparing three characters still matches a plain `soc` node, so boards that already work are unaffected.

### End-to-end verification on hardware

Since first writing this I added a minimal `pi5` board (generic `linux` hwdef plus
`HAL_LINUX_GPIO_RPI_ENABLED`, no sensors declared) so the RP1 GPIO path could be exercised on a
bare Pi 5 without a HAT firmware probing unrelated buses. That makes the panic directly
observable. Same binary, same machine, only the one character differing:

**Without the fix** (`strncmp(..., 4)`):

```
$ ./build/pi5/bin/arduplane
"ranges" file not found
Unknown rpi_version, cannot locate peripheral base address
$ echo $?
1
```

**With the fix** (`strncmp(..., 3)`):

```
$ timeout 8 ./build/pi5/bin/arduplane
RPI 5
AP_Logger_File: buffer size=204800
Config Error: Baro: unable to initialise driver
$ echo $?
124        # still running when the timeout killed it
```

(The `Config Error` is just `HAL_INS_NONE` on a board with no sensors declared; unrelated to this
change. Note the detection line is only visible with `stdbuf -o0` — stdout is fully buffered when
redirected, so the print is otherwise lost if the process is killed before it flushes.)

The `pi5` board itself is not part of this PR. I am happy to submit it separately if it would be
useful; it is the only way I found to run ArduPilot on a bare Pi 5 with the RP1 GPIO backend live.
