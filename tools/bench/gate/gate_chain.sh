#!/bin/bash
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# gate_chain.sh BRAIN_IP - release-gate chain, unattended, on the noknok-pi rig (Bob, v1.3.0 gate 26 Oct 2026;
# committed for DEV-77, was only on the old Pi4 ~/gate/). Runs from this checkout; ~/gate holds only state,
# logs and the published images (~/gate/pub/noknok_stage0.bin, noknok_stage1.bin, keyboard_firmware.bin).
# Env: BENCH_SUDO_PW (uhubctl), MDNS_NAME (default $MDNS_NAME), EXPECT_LEDBUTTON (default
#      'LEDBUTTON fw 2.4.1 bl (1, 1, 2, 0, 2)'), BL_TEST (default ~/dev/ch32fun/noknok_stage0/test, has mk_full.py).
# Restart-proof: ~/gate/state records phases; a phase that was started but not finished when the
# Pi restarted is marked "interrupted" and NOT retried (except the soak, which resumes).
# Phases: restore (published LED Button image) -> S/M tests -> soak until 08:30.
set -u
IP=${1:?usage: gate_chain.sh BRAIN_IP}
R=$(cd "$(dirname "$0")/../../.." && pwd)       # brain-Pico checkout
G=$HOME/gate; L=$G/logs; ST=$G/state; mkdir -p $L; touch $ST
PICO="python3 -u $R/tools/pico.py"
RPC="python3 $R/tools/rpc_call.py"
T=${BL_TEST:-$HOME/dev/ch32fun/noknok_stage0/test}
MDNS_NAME=${MDNS_NAME:-$MDNS_NAME}
EXPECT_LEDBUTTON=${EXPECT_LEDBUTTON:-LEDBUTTON fw 2.4.1 bl (1, 1, 2, 0, 2)}
[ -n "${BENCH_SUDO_PW:-}" ] || { echo "BENCH_SUDO_PW not set"; exit 1; }
M=$HOME/dev/ch32fun/minichlink/minichlink
END="08:30"
# fixed end of the soak: the next 08:30 from the first start; kept in a file so a restart keeps it
[ -s $G/end_epoch ] || { e=$(date -d "today $END" +%s); [ "$(date +%s)" -ge "$e" ] && e=$(date -d "tomorrow $END" +%s); echo $e > $G/end_epoch; }
END_EPOCH=$(cat $G/end_epoch)

log() { echo "$(date '+%F %T') $*" | tee -a $L/chain.log; }
cut() { printf '%s
' "$BENCH_SUDO_PW" | sudo -S -p "" /usr/sbin/uhubctl -l 2 -a off >/dev/null 2>&1; sleep "${1:-6}"
        printf '%s
' "$BENCH_SUDO_PW" | sudo -S -p "" /usr/sbin/uhubctl -l 2 -a on >/dev/null 2>&1; }
online() { for i in $(seq 1 "$1"); do curl -s -m 4 http://$IP/rpc -d '{"op":"hello"}' 2>/dev/null | grep -q '"product"' && return 0; sleep 4; done; return 1; }
past_end() { [ "$(date +%s)" -ge "$END_EPOCH" ]; }
prep() { cut 6; online 45; }
phase() { local name=$1; shift
  if grep -q "^$name done" $ST; then return; fi
  if grep -q "^$name started" $ST; then echo "$name interrupted" >> $ST; log "$name INTERRUPTED by a restart - not retried"; return; fi
  echo "$name started" >> $ST; log "=== $name start"
  "$@" > $L/$name.log 2>&1; local rc=$?
  echo "$name done rc=$rc" >> $ST; log "=== $name end rc=$rc"; }

# ---- helpers -------------------------------------------------------------------------
capture() {  # capture <seconds> <outfile>: passive console capture from power-on
  python3 - "$1" "$2" <<'PY'
import serial, time, os, sys, glob
secs = float(sys.argv[1]); out = sys.argv[2]
t = time.time(); p = None
while time.time() - t < 60:
    g = glob.glob('/dev/serial/by-id/usb-Raspberry_Pi_Pico_2_W_*-if00')
    if g: p = g[0]; break
    time.sleep(0.2)
s = serial.Serial(p, 115200, timeout=1); t = time.time(); o = b''
while time.time() - t < secs: o += s.read(4096)
open(out, 'wb').write(o)
PY
}

p_restore() {   # SWD: published stage-0 + stage-1 + LED Button app (the L tier left test builds on the module)
  cd $T
  python3 mk_full.py $G/pub/noknok_stage0.bin $G/pub/noknok_stage1.bin $G/pub/keyboard_firmware.bin $G/pub/full_published.bin || return 1
  $M -w $G/pub/full_published.bin flash -b >/dev/null 2>&1 && echo flashed || return 1
  sleep 6
  $PICO run $R/tools/bench/gate/gate_enum.py 90 | tee $L/restore_enum.out
  grep -q "GATE_ENUM_OK" $L/restore_enum.out && grep -qF "$EXPECT_LEDBUTTON" $L/restore_enum.out
}
p_enum() { $PICO run $R/tools/bench/gate/gate_enum.py 90 | tee $L/enum.out; grep -q "GATE_ENUM_OK" $L/enum.out; }
p_fspolicy() { cut 6; sleep 45; $PICO run $R/software/bench_fs_policy.py 90; }
p_store() { $PICO run $R/software/bench_store.py 120; }
p_dev65() { $PICO run $R/software/bench_dev65.py 280; }
p_safemode() { prep || return 1; bash $R/tools/bench/bench_dev154_safemode.sh $IP; }
p_wdt() { prep || return 1; bash $R/tools/bench/bench_dev93_wdt_rejoin.sh 3 $IP; }
p_rpc() { cut 6; online 40 || return 1; python3 $R/tools/bench/bench_dev109_110.py $IP; echo; python3 $R/tools/bench/gate/gate_rpc_settings.py $IP; echo; python3 $R/tools/bench/gate/gate_rpc_stress.py $IP 60; }
p_mdns() {
  cd $G
  $PICO get settings.toml $G/settings_orig.toml >/dev/null 2>&1 || return 1
  grep -v NOKNOK_MDNS $G/settings_orig.toml > $G/settings_unset.toml
  (cat $G/settings_unset.toml; echo "NOKNOK_MDNS = 0") > $G/settings_off.toml
  for case in unset off; do
    $PICO put $G/settings_$case.toml settings.toml >/dev/null 2>&1
    cut 6; capture 60 $L/mdns_$case.log
    echo "--- $case: $(grep -a -i '\[mdns\]' $L/mdns_$case.log | head -2)"
    getent hosts $MDNS_NAME || echo "(no resolve)"
  done
  $PICO put $G/settings_orig.toml settings.toml >/dev/null 2>&1
  cut 6; capture 60 $L/mdns_restored.log
  echo "--- restored: $(grep -a -i '\[mdns\]' $L/mdns_restored.log | head -2)"; getent hosts $MDNS_NAME || echo "(no resolve)"
}
p_dueboot() {   # DEV-147/106/155: a due boot's stage-1 pass with all modules (legacy Knob included)
  timeout 40 $PICO exec "import microcontroller as m; m.nvm[1:5]=bytes(4); m.reset()" >/dev/null 2>&1
  capture 150 $L/dueboot.log
  grep -a -E '\[bl\]|\[fw\]|BLOCKED|refus|alert|Traceback|CRASH' $L/dueboot.log | head -30
}
p_dev130() { timeout 200 $PICO run $R/tools/bench/bench_dev130_scan_then_ap.py 150; cut 6; online 40; }
p_final() { cut 6; online 40 && echo "brain online after final cut" && $RPC $IP status | head -c 600; }

# ---- soak ------------------------------------------------------------------------------
p_soak() {
  cd $R/tools/soak
  while ! past_end; do
    if ! pgrep -f "soak_run.py" >/dev/null; then
      log "soak: (re)starting soak_run until $END"
      python3 soak_run.py --hours 14 --until $END --dir $G/soak_run --usb --hub 2 >> $G/soak_run.console 2>&1 &
    fi
    sleep 120
  done
  pkill -f "soak_run.py" 2>/dev/null; sleep 3
  python3 soak_report.py $(ls -t $G/soak_run/soak_*.jsonl | head -1) | head -90
}

# ---- run -----------------------------------------------------------------------------------
log "chain start (pid $$)"
phase restore   p_restore
phase enum      p_enum
phase fspolicy  p_fspolicy
phase store     p_store
phase dev65     p_dev65
phase safemode  p_safemode
phase wdt       p_wdt
phase rpc       p_rpc
phase mdns      p_mdns
phase dueboot   p_dueboot
phase dev130    p_dev130
phase final     p_final
# the soak resumes after a restart: clear a stale "started"
grep -q "^soak done" $ST || { sed -i '/^soak started/d' $ST; phase soak p_soak; }
log "chain end"
