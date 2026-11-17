# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# reboot_loop.py IP N - app "reboot" op N times; times to /rpc hello ok + modules back. Host, needs tools/rpc_call.py.
# reboot_loop.py - app "reboot" op N times (radio_off default), time to hello ok + modules after
import os, json, subprocess, sys, time
HOST = sys.argv[1]; N = int(sys.argv[2])
def rpc(op, args=None, t=8):
    cmd = ["python3", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "rpc_call.py"), HOST, op]
    if args is not None: cmd.append(json.dumps(args))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=t)
        return json.loads(r.stdout)
    except Exception as e:
        return None
ok = 0
for n in range(1, N + 1):
    r = rpc("reboot")
    t0 = time.time(); up = None
    time.sleep(6)
    while time.time() - t0 < 120:
        h = rpc("hello")
        if h: up = time.time() - t0; break
        time.sleep(2)
    time.sleep(25)
    st = rpc("status", t=15)
    mods = sorted(m["type"] for m in st["modules"]) if st else None
    good = up is not None and mods and "leds16" in mods and len(mods) == 5
    ok += 1 if good else 0
    print("%d reboot reply=%s up_after=%s mods=%s %s" % (n, str(r)[:80], None if up is None else round(up, 1), mods, "ok" if good else "FAIL"), flush=True)
print("RESULT %d/%d ok" % (ok, N))
