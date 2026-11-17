#!/bin/sh
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# dev179_night.sh IP N - DEV-179 night A/B on Pi4RFID (Debug Probe attached). Needs BENCH_SUDO_PW in the env.
# Supply check at start and end, continuous usbmon of bus 1, then the reset loop with alternating arms
# (DEV172_RADIO=alt: even cycles radio off, odd cycles plain reset), app reboots only, SWD dump at every
# wedge/hang, SWD reset at every hang. Output: ~/dev/dev179/night/
IP=$1; N=${2:-440}
D=$(cd "$(dirname "$0")" && pwd); OUT=${OUT:-$HOME/dev/dev179/night}; mkdir -p "$OUT"
# SWD hooks: tools/bench/probe/ (branch dev-172-probe until merged); override with PROBE=dir
PROBE=${PROBE:-$D/../probe}
sudo_() { printf '%s\n' "$BENCH_SUDO_PW" | sudo -S -p '' "$@"; }
supply() {
  echo "== supply $1 $(date '+%F %T')"
  echo "throttled: $(vcgencmd get_throttled 2>&1)"
  echo "undervoltage lines in dmesg: $(sudo_ dmesg | grep -ci undervolt)"
  python3 "$D/rpc_status_power.py" "$IP" 2>&1 | head -3
}
supply START >> "$OUT/supply.txt"
sudo_ modprobe usbmon
sudo_ sh -c "cat /sys/kernel/debug/usb/usbmon/1u > $OUT/usbmon_bus1.txt" &
MON=$!
DEV172_HOW=rpc DEV172_RADIO=alt \
DEV172_DUMP="sh $PROBE/hang_dump.sh" DEV172_RECOVER="sh $PROBE/swd_reset.sh" \
python3 "$D/bench_dev179_night.py" "$IP" "$N" "$OUT" > "$OUT/nohup.out" 2>&1
supply END >> "$OUT/supply.txt"
sudo_ pkill -f '[u]sbmon/1u'
python3 "$D/dev179_report.py" "$OUT/cycles.jsonl" > "$OUT/report.txt" 2>&1
echo "done $(date '+%F %T')" >> "$OUT/supply.txt"
