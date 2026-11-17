#!/bin/sh
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# gate_night.sh BRAIN_IP [RESETS] [SOAK_HOURS] - release-gate overnight run (Bob, v1.3.0 gate 2 Nov 2026;
# committed for DEV-77, was only on Pi4RFID ~/hands/). Standalone, nobody watches:
#   1) DEV-172/179: RESETS software resets (rpc + repl paths, radio off/on alternating), tools/bench/bench_dev172_reset_loop.py
#   2) DEV-67: SOAK_HOURS power-cut soak (ganged hub 2 VBUS cut, USB modules), tools/soak/soak_run.py
# Result: $OUT/verdict.txt (default OUT=~/gate_night/<date>). Removes ~/BENCH_IN_USE at the end if it set it.
# Rig note: on a PD-fed PicoHub (Pi4RFID) a hub-2 cut does NOT reset the Pico - use the noknok-pi rig or
# add the Shelly J1 cut (tools/bench/rig/). sudo: BENCH_SUDO_PW in the environment, never in a file.
IP=${1:?usage: gate_night.sh BRAIN_IP [RESETS] [SOAK_HOURS]}; N=${2:-40}; H=${3:-7}
R=$(cd "$(dirname "$0")/../.." && pwd)              # brain-Pico checkout
OUT=${OUT:-$HOME/gate_night/$(date +%F)}; mkdir -p "$OUT"
[ -n "$BENCH_SUDO_PW" ] || { echo "BENCH_SUDO_PW not set"; exit 1; }
export BENCH_SUDO_PW
MINE=0; [ -e "$HOME/BENCH_IN_USE" ] || { echo "gate_night $(date +%F_%T)" > "$HOME/BENCH_IN_USE"; MINE=1; }
echo "start $(date +%F_%T) ip=$IP resets=$N soak=${H}h repo=$(git -C "$R" rev-parse --short HEAD 2>/dev/null)" > "$OUT/progress.txt"
DEV172_HOW=both DEV172_RADIO=alt DEV172_CUT=1 python3 "$R/tools/bench/bench_dev172_reset_loop.py" "$IP" "$N" "$OUT/reset" > "$OUT/reset.out" 2>&1
echo "reset loop done $(date +%F_%T)" >> "$OUT/progress.txt"
sleep 60                                              # let the brain settle, then the soak
(cd "$R/tools/soak" && python3 soak_run.py --hours "$H" --dir "$OUT/soak" --usb --hub 2) > "$OUT/soak.out" 2>&1
echo "soak done $(date +%F_%T)" >> "$OUT/progress.txt"
(cd "$R/tools/soak" && python3 soak_report.py "$(ls -t "$OUT"/soak/soak_*.jsonl | head -1)") > "$OUT/soak_report.txt" 2>&1
OUT="$OUT" python3 - <<'PY' > "$OUT/verdict.txt" 2>&1
import json, glob, os
out = os.environ["OUT"]
print("GATE NIGHT - " + open(out + "/progress.txt").readline().strip())
recs = []
for p in glob.glob(out + "/reset/cycles.jsonl"):
    recs = [json.loads(l) for l in open(p) if l.strip()]
hang = [r for r in recs if r.get("result") == "HANG"]
print("RESET LOOP (DEV-172/179): %d cycles, %d hang(s)" % (len(recs), len(hang)))
for arm in (True, False):
    sub = [r for r in recs if r.get("radio_off") == arm]
    print("  radio_off=%s: %d cycles, %d hang(s)" % (arm, len(sub), len([r for r in sub if r.get("result") == "HANG"])))
print("--- soak report ---")
p = out + "/soak_report.txt"
print(open(p).read()[:6000] if os.path.exists(p) else "no soak report")
PY
[ "$MINE" = 1 ] && rm -f "$HOME/BENCH_IN_USE"
echo "done $(date +%F_%T)" >> "$OUT/progress.txt"
