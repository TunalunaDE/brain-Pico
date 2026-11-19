# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# bench_dev78_parser.py - DEV-78: does the LEDs 16x command parser fall out of step
# when the Pico sends a fast stream of small commands?
#
# Needs the LEDs 16x DIAGNOSTIC build (fw 2.2.90+, -DDIAG_PARSER): 0x3D clears and 0x3E
# reads 12 little-endian uint32 counters (pkts, bytes, n03, n10, n11, nother, unknown,
# timeouts, wait_at_batch_end, last_unknown4, last_timeout, max_pkt). A release build
# does not answer 0x3E; the script then still runs the stream and only reports what it sent.
#
# What it does (the Smart Lamp Maxi "Sundown" pattern that showed the fault):
#   0x3D reset -> 0x11 one colour ONCE -> ONLY 0x03 brightness, sweeping 43 -> 8 -> 43,
#   at >= 10 commands/s for MINUTES. With LOAD = True the noknok Display is redrawn
#   continuously in between (I2C load, like the Maxi loop). Every 0x03 is ONE USB write,
#   exactly like the product driver (noknok_usb.NoknokLEDs._send). The script counts what
#   it sent, short writes and write exceptions, then reads 0x3E and compares.
#
# Run on the bench host (the product code.py is stopped by pico.py's Ctrl-C):
#   ./pico.py run bench_dev78_parser.py 420                       (no I2C load)
#   sed 's/^LOAD = False/LOAD = True/' bench_dev78_parser.py > /tmp/b78l.py
#   ./pico.py run /tmp/b78l.py 420                                (with Display load)
# Once a second it also polls 0x30 GET_STATUS (VBUS, LED budget, cut flags): a governor cut
# switches the LED rail off = a whole-ring flash.
# Verdict line: CLEAN = every counter matches what was sent and no governor cut; else DESYNC/GOVERNOR.
import struct
import time

import noknok_usb

LOAD = False          # True = redraw the Display between commands (I2C load)
MINUTES = 5
GAP_S = 0.08          # pause between commands when LOAD is False (~12/s)
WARM = (160, 80, 0, 95)
SWEEP = list(range(43, 7, -1)) + list(range(8, 44))    # 43..8..43, crosses 0x10/0x11
NAMES = ("pkts", "bytes", "n03", "n10", "n11", "nother", "unknown", "timeouts",
         "wait_at_batch_end", "last_unknown4", "last_timeout", "max_pkt")


gov = {"polls": 0, "vbus_min": 99999, "budget_min": 99999, "temp_max": -999, "cut_or_rail_off": 0, "first_bad": ""}


def poll_status(m):
    """0x30 GET_STATUS once: track VBUS, LED budget and governor cuts (a cut = whole-ring flash)."""
    r = m._query(0x30, 16, timeout=300)
    if not r or len(r) != 16:
        return
    t, vbus, _, _, budget, est, flags = struct.unpack("<hHHHHHB", r[1:14])
    gov["polls"] += 1
    gov["vbus_min"] = min(gov["vbus_min"], vbus)
    gov["budget_min"] = min(gov["budget_min"], budget)
    gov["temp_max"] = max(gov["temp_max"], t)
    if budget == 0 or not (flags & 1) or (flags & 6):
        gov["cut_or_rail_off"] += 1
        if not gov["first_bad"]:
            gov["first_bad"] = "vbus %d budget %d flags 0x%02x" % (vbus, budget, flags)


def counters(m):
    r = m._query(0x3E, 48, timeout=500)
    if not r or len(r) != 48:
        return None
    return dict(zip(NAMES, struct.unpack("<12I", r)))


# -- find the LEDs 16x ------------------------------------------------------------
mods = noknok_usb.discover()
print("usb modules:", [(s, k) for s, k, _ in mods])
hits = [x for x in mods if x[1] in ("leds16", "usb_leds_16x") or getattr(x[2], "MODULE_TYPE", 0) == 0x06]
if not hits:
    raise SystemExit("FAIL no LEDs 16x on the USB host")
serial, kind, m = hits[0]
ver = m.version()
print("leds16", serial, "fw", ver)

# -- optional Display for I2C load --------------------------------------------------
d = None
if LOAD:
    from noknok import Conductor, BLACK, WHITE
    c = Conductor()
    c.enumerate()                      # I2C only; the USB module stays ours
    d = c.display[0] if c.display else None
    if d is None:
        raise SystemExit("FAIL LOAD=True but no Display found")
    d.native_text = False
    d.clear(BLACK)
    print("display found, I2C load ON")

# -- run --------------------------------------------------------------------------
EP = m._EP_OUT
dev = m._dev
dev.write(EP, b"\x3D", timeout=1000)                    # clear counters
time.sleep(0.05)
before = counters(m)
diag = before is not None
print("diag counters:", "yes" if diag else "NO (release build?)", before)

sent = {"n03": 0, "n11": 0, "pkts": 0, "bytes": 0}
short = exc = 0
first_exc = ""
max_send_ms = 0.0


def send(b):
    global short, exc, first_exc, max_send_ms
    t = time.monotonic()
    try:
        n = dev.write(EP, b, timeout=1000)
        if n is not None and n != len(b):
            short += 1
    except Exception as e:                # count it and keep going: we want the whole picture
        exc += 1
        if not first_exc:
            first_exc = repr(e)
        return
    dt = (time.monotonic() - t) * 1000
    if dt > max_send_ms:
        max_send_ms = dt
    sent["pkts"] += 1
    sent["bytes"] += len(b)


send(bytes((0x03, 43)))
sent["n03"] += 1
send(bytes((0x11,) + WARM))
sent["n11"] += 1

t0 = time.monotonic()
last_report = t0
last_poll = t0
redraws = 0
stop = False
while not stop:
    for lv in SWEEP:
        send(bytes((0x03, lv)))
        sent["n03"] += 1
        if d:
            d.text("%02d %04d" % (lv, sent["n03"] % 10000), size=32, color=WHITE, x=0, y=40)
            redraws += 1
        else:
            time.sleep(GAP_S)
        now = time.monotonic()
        if now - last_poll >= 1:
            last_poll = now
            poll_status(m)
        if now - last_report >= 60:
            last_report = now
            print("  %3.0f s  sent %d  (%.1f/s)  exc %d" % (now - t0, sent["n03"], sent["n03"] / (now - t0), exc))
        if now - t0 >= MINUTES * 60:
            stop = True
            break
dur = time.monotonic() - t0
time.sleep(0.2)
after = counters(m)

print("sent: 0x03 x%d, 0x11 x%d in %.0f s = %.1f cmd/s; redraws %d; short writes %d; write exceptions %d %s; max write %.1f ms"
      % (sent["n03"], sent["n11"], dur, sent["n03"] / dur, redraws, short, exc, first_exc, max_send_ms))
if not diag or after is None:
    print("RESULT NO-DIAG (no 0x3E answer) - only the sent side is known")
    raise SystemExit
print("governor: polls %d, VBUS min %d mV, budget min %d mA, temp max %.1f C, cut/rail-off seen %d %s"
      % (gov["polls"], gov["vbus_min"], gov["budget_min"], gov["temp_max"] / 10, gov["cut_or_rail_off"], gov["first_bad"]))
for k in NAMES:
    print("  %-18s %10d  (0x%08x)" % (k, after[k], after[k]))
bad = []
sent["pkts"] += 2 + gov["polls"]       # the two 0x3E queries + the 0x30 polls are counted too
sent["bytes"] += 2 + gov["polls"]
for k in ("n03", "n11", "pkts", "bytes"):
    if after[k] != sent[k]:
        bad.append("%s got %d sent %d" % (k, after[k], sent[k]))
if after["nother"] != gov["polls"]:      # 0x30 is the only "other" command sent
    bad.append("nother %d, 0x30 polls %d" % (after["nother"], gov["polls"]))
for k in ("n10", "unknown", "timeouts", "wait_at_batch_end"):
    if after[k]:
        bad.append("%s=%d" % (k, after[k]))
if gov["cut_or_rail_off"]:
    bad.append("GOVERNOR cut/rail off %d x (%s)" % (gov["cut_or_rail_off"], gov["first_bad"]))
print("RESULT", "DESYNC: " + "; ".join(bad) if bad else "CLEAN", "| LOAD", LOAD)
dev.write(EP, b"\x00", timeout=1000)                    # LEDs off
