#!/bin/sh
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# usb_powercycle.sh [OFF_SECONDS] [HUB] [PORT] - bench host (Pi 4): cold-boot the Pico (and whatever it
# feeds) by cutting USB VBUS with uhubctl, then wait up to 30 s for its serial port to come back.
# Default HUB=2 with no PORT = the Pi 4B's USB 3 hub, the only one that really switches VBUS (ganged:
# ALL USB devices on the Pi lose power, incl. a WCH-LinkE). A per-port cut on hub 1-1 drops only the
# data link on a Pi 4 (no real power-pull). A PicoHub fed from its own charger on J1 is NOT cut by
# this: use the Shelly Testing Plug for J1 (tools/bench/rig/shelly.py).
# sudo: passwordless, or BENCH_SUDO_PW in the environment (never in a file).
OFF=${1:-3}; HUB=${2:-2}; PORT=${3:-}
UHUB=$(command -v uhubctl || ls /usr/sbin/uhubctl 2>/dev/null)
[ -z "$UHUB" ] && { echo "FAIL: uhubctl not found"; exit 1; }
sudo_() { if [ -n "$BENCH_SUDO_PW" ]; then printf '%s\n' "$BENCH_SUDO_PW" | sudo -S -p '' "$@"; else sudo -n "$@"; fi; }
P=""; [ -n "$PORT" ] && P="-p $PORT"
echo "uhubctl -l $HUB $P  off_time=${OFF}s  $(date '+%F %T')"
echo "--- power OFF ---"; sudo_ "$UHUB" -l "$HUB" $P -a off 2>&1 | tail -n 3
sleep "$OFF"
echo "serial during off: $(ls /dev/serial/by-id/ 2>/dev/null | tr '\n' ' ')"
echo "--- power ON ---"; sudo_ "$UHUB" -l "$HUB" $P -a on 2>&1 | tail -n 3
i=0
while [ $i -lt 30 ]; do
  if ls /dev/serial/by-id/usb-Raspberry_Pi_Pico*-if00 >/dev/null 2>&1; then echo "BACK after ${i}s"; exit 0; fi
  i=$((i+1)); sleep 1
done
echo "FAIL: Pico serial port not back after 30 s"; exit 2
