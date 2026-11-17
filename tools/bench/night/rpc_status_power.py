# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# rpc_status_power.py IP - one line of PicoHub power data from /rpc status (supply check for DEV-179)
import os, json, subprocess, sys
out = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "rpc_call.py"), sys.argv[1], "status"],
                     capture_output=True, text=True, timeout=30).stdout
try:
    d = json.loads(out[out.index("{"):]); d = d.get("result", d)
    print("picohub:", json.dumps(d.get("picohub") or d.get("power") or {})[:300])
except Exception as e:
    print("status read failed:", e, out[:200])
