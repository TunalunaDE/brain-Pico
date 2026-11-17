#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# check_after_cut.py IP [--device ID] [--modules a,b,c] [--max-uptime S] [--expect code=0.44,noknok=1.26]
#                       [--wait S] - bench host: the per-cycle check for power-cut runs (run_night.py `command`).
# Waits until the brain answers /rpc hello again (default up to 400 s), then reads status and checks:
#   * --device: hello's device id / name contains this (the right brain)
#   * --max-uptime: the brain's uptime is below S -> the cut REALLY reset the Pico (not only its data link;
#     a Pico fed from somewhere else keeps running and this is the only way to see it)
#   * --modules: exactly these module types are back (sorted list, e.g. buzzer,display,knob,ledbutton,leds16,picohub)
#   * strikes 0, no PicoHub power faults, optional --expect versions from hello["versions"]
# Prints ONE line (result + the measured values) and exits 0 = PASS, 1 = FAIL. No dependencies besides
# tools/rpc_call.py (found next to this repo checkout).
import argparse, json, os, subprocess, sys, time

RPC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "rpc_call.py")


def call(ip, op):
    for _ in range(4):
        try:
            r = subprocess.run([sys.executable, RPC, ip, op], capture_output=True, text=True, timeout=25)
            return json.loads(r.stdout)
        except Exception:
            time.sleep(3)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ip")
    ap.add_argument("--device", default="")
    ap.add_argument("--modules", default="")
    ap.add_argument("--max-uptime", type=float, default=0)
    ap.add_argument("--expect", default="")
    ap.add_argument("--wait", type=float, default=400)
    a = ap.parse_args()
    t0, h = time.time(), None
    while time.time() - t0 < a.wait:
        h = call(a.ip, "hello")
        if h:
            break
        time.sleep(5)
    if not h:
        print("FAIL no hello within %d s" % a.wait)
        return 1
    back_s = round(time.time() - t0, 1)
    s = call(a.ip, "status")
    if not s:
        print("FAIL hello ok, status not answering")
        return 1
    problems = []
    ident = "%s %s" % (h.get("device", ""), h.get("name", ""))
    if a.device and a.device not in ident:
        problems.append("wrong brain (%s)" % ident.strip())
    up = h.get("uptime") or 0
    if a.max_uptime and up > a.max_uptime:
        problems.append("uptime %.0f s > %.0f: the cut did NOT reset the Pico" % (up, a.max_uptime))
    mods = sorted(m.get("type", "?") for m in s.get("modules", []))
    if a.modules and mods != sorted(a.modules.split(",")):
        problems.append("modules %s, want %s" % (",".join(mods), ",".join(sorted(a.modules.split(",")))))
    if s.get("strikes"):
        problems.append("strikes %s" % s["strikes"])
    pw = s.get("power") or {}
    if pw.get("faults"):
        problems.append("picohub faults %s" % pw["faults"])
    v = h.get("versions") or {}
    for kv in filter(None, a.expect.split(",")):
        k, want = kv.split("=", 1)
        if str(v.get(k)) != want:
            problems.append("%s %s, want %s" % (k, v.get(k), want))
    print("%s back_after_s=%s uptime=%.0f reset_cause=%s modules=%s strikes=%s v5v=%s%s" % (
        "FAIL" if problems else "PASS", back_s, up, pw.get("reset_cause"), ",".join(mods), s.get("strikes"),
        pw.get("v5v"), (" | " + "; ".join(problems)) if problems else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
