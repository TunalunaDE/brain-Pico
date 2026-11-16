#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Constant-current run on an Atorch DL24 (USB HID 0483:5750, firmware V1.1.0) with logging and safety.

Protocol: PROTOCOL.md of github.com/sophusand/atorch-dl24p-python (captured from the official app).
usage: dl24_run.py <amps> <baseline_s> <load_s> <logfile> [--dry] [/dev/hidrawN]
  baseline_s : log with the load OFF for this long, then switch ON at <amps> (CC) for load_s seconds, then OFF.
  --dry      : read and log only, never switch on.
Safety (any one switches the load OFF and ends the run):
  input voltage < 3.5 V while ON (the supplied rail collapsed), MOSFET temperature > 75 C, current > amps + 0.5 A,
  no reply from the load for 5 s, any error, SIGTERM/SIGINT.  The load's own time limit is set to load_s + 2 min as
  a backstop in case this script dies (it is cleared again at the end).
Log line: epoch, seconds since start, state, V, I, P, energy Wh, MOSFET C, CPU C.
"""
import os, select, signal, struct, sys, time

args = [a for a in sys.argv[1:] if a != "--dry"]
dry = "--dry" in sys.argv
amps, base_s, load_s, logfile = float(args[0]), float(args[1]), float(args[2]), args[3]
fd = os.open(args[4] if len(args) > 4 else "/dev/hidraw0", os.O_RDWR)
LIMIT_V_MIN, LIMIT_T_MAX = float(os.environ.get("DL24_VMIN", "3.5")), float(os.environ.get("DL24_TMAX", "75"))

def send(cmd, data=b"\0\0\0\0"):
    os.write(fd, b"\x00" + (bytes([0x55, 0x05, 0x01, cmd]) + data + bytes([0xEE, 0xFF])).ljust(64, b"\0"))

def request(cmd, wait=0.6):
    while select.select([fd], [], [], 0)[0]:
        os.read(fd, 64)
    send(cmd)
    t0 = time.time()
    while time.time() - t0 < wait:
        if select.select([fd], [], [], 0.05)[0]:
            r = os.read(fd, 64)
            if r[0] == 0xAA and r[3] == cmd:
                return r
    return None

def measure():
    r = request(0x05)
    if r is None:
        return None
    w = struct.unpack("<14I", r[4:60])
    return dict(v=w[1] / 1000, i=w[2] / 1000, p=w[3] / 1000, wh=w[5] / 1000, cpu=w[7] / 1000, fet=w[9] / 1000, on=w[12])

def load(on):
    send(0x25, bytes([1 if on else 0, 0, 0, 0]))

def time_limit(h, m):
    send(0x31, bytes([h, 0, 0, 1])); time.sleep(0.2)
    send(0x31, bytes([m, 0, 0, 2])); time.sleep(0.2)

stop_reason = None
def on_signal(sig, frm):
    global stop_reason
    stop_reason = "signal %d" % sig
signal.signal(signal.SIGTERM, on_signal)
signal.signal(signal.SIGINT, on_signal)

log = open(logfile, "a", buffering=1)
def out(state, m):
    t = time.time()
    log.write("%.2f %.1f %s %.3f %.3f %.3f %.4f %.1f %.1f\n" % (t, t - t0, state, m["v"], m["i"], m["p"], m["wh"], m["fet"], m["cpu"]))

t0 = time.time()
state = "BASELINE"
turned_on_at = None
last_ok = time.time()
log.write("# start %s amps=%.2f baseline=%.0fs load=%.0fs dry=%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), amps, base_s, load_s, dry))
try:
    s = request(0x03)
    mode = s[48] if s else None
    if mode != 0:
        raise SystemExit("load is not in CC mode (mode byte %r): stopping before doing anything" % mode)
    if not dry:
        time_limit(0, int(load_s / 60) + 2)
    while stop_reason is None:
        now = time.time() - t0
        m = measure()
        if m is None:
            if time.time() - last_ok > 5:
                stop_reason = "no reply from the load for 5 s"
            continue
        last_ok = time.time()
        out(state, m)
        if state == "BASELINE" and now >= base_s and not dry:
            send(0x21, struct.pack(">f", amps)); time.sleep(0.3)
            load(True)
            state, turned_on_at = "LOAD", now
        elif state == "LOAD":
            if m["v"] < LIMIT_V_MIN: stop_reason = "input voltage %.2f V < %.1f V (rail collapsed)" % (m["v"], LIMIT_V_MIN)
            elif m["fet"] > LIMIT_T_MAX: stop_reason = "MOSFET %.1f C > %.0f C" % (m["fet"], LIMIT_T_MAX)
            elif m["i"] > amps + 0.5: stop_reason = "current %.2f A above setpoint + 0.5 A" % m["i"]
            elif now - turned_on_at >= load_s: stop_reason = "done"
        elif dry and now >= base_s:
            stop_reason = "dry run done"
        time.sleep(0.5)
except SystemExit as e:
    stop_reason = str(e)
except Exception as e:
    stop_reason = "error: %r" % (e,)
finally:
    try:
        if not dry:
            load(False); time.sleep(0.4); load(False); time.sleep(0.3)
            time_limit(0, 0)
        m = measure()
        if m: out("END", m)
    except Exception as e:
        print("cleanup error:", repr(e))
    log.write("# end: %s\n" % stop_reason)
    print("end:", stop_reason, "| load on:", m["on"] if m else "?")
    log.close()
    os.close(fd)
