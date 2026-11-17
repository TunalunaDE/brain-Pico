#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# leakwatch.py IP HOURS OUTFILE - overnight watch of a RUNNING brain (no console access, nothing deployed):
#   every 2 s  : /rpc hello (latency, uptime)         -> catches reply cuts and resets
#   every 3 s  : settings.get like the app's settings page (traffic underneath)
#   every 60 s : status -> mem_free, strikes, status.link (cut_replies, poll_max_ms, drops, rejoins), module count
import json, sys, time, urllib.request

IP = sys.argv[1]; END = time.time() + float(sys.argv[2]) * 3600; OUT = sys.argv[3]


def rpc(op, args=None, t=4):
    t0 = time.time()
    try:
        b = json.dumps({"id": 1, "op": op, "args": args or {}}).encode()
        r = urllib.request.Request("http://%s/rpc" % IP, data=b, headers={"Content-Type": "application/json"})
        raw = urllib.request.urlopen(r, timeout=t).read()
        d = json.loads(raw.decode())
        if isinstance(d, dict):
            d["_bytes"] = len(raw)
        return time.time() - t0, d
    except Exception as e:
        return None, repr(e)[:80]


f = open(OUT, "a", buffering=1)
last_status = 0; last_get = 0
while time.time() < END:
    now = time.time()
    lat, d = rpc("hello")
    rec = {"t": time.strftime("%H:%M:%S"), "hello_s": round(lat, 3) if lat else None,
           "uptime": d.get("uptime") if isinstance(d, dict) else d}
    if now - last_get >= 3:
        l2, _ = rpc("settings.get"); rec["get_s"] = round(l2, 3) if l2 else None; last_get = now
    if now - last_status >= 60:
        l3, s = rpc("status", t=8)
        if isinstance(s, dict):
            rec["status"] = {"mem_free": s.get("mem_free"), "strikes": s.get("strikes"), "link": s.get("link"),
                             "modules": len(s.get("modules", [])), "events": len(s.get("events", [])), "reply_bytes": s.get("_bytes")}
        else:
            rec["status"] = "NONE " + str(s)
        last_status = now
    f.write(json.dumps(rec) + "\n")
    time.sleep(2)
f.write(json.dumps({"end": time.strftime("%H:%M:%S")}) + "\n")
