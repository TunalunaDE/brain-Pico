# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# pullup_probe.py - raw busio.I2C per pin pair. CircuitPython refuses to build a
# bus with no pull-ups ("No pull up found on SDA or SCL"), so this distinguishes
# "wrong pins / no pull-ups" from "bus fine, module silent".
import board, busio

PAIRS = [("GP8","GP9"), ("GP18","GP19"), ("GP20","GP21"), ("GP4","GP5"),
         ("GP0","GP1"), ("GP2","GP3"), ("GP6","GP7"), ("GP10","GP11")]

for sda_name, scl_name in PAIRS:
    sda = getattr(board, sda_name, None)
    scl = getattr(board, scl_name, None)
    if sda is None or scl is None:
        continue
    i2c = None
    try:
        i2c = busio.I2C(scl, sda, frequency=100000)
        while not i2c.try_lock():
            pass
        found = i2c.scan()
        i2c.unlock()
        print("%-12s PULL-UPS PRESENT  scan=%s"
              % (sda_name + "/" + scl_name, [hex(a) for a in found]))
    except Exception as e:
        print("%-12s %s: %s" % (sda_name + "/" + scl_name, type(e).__name__, e))
    finally:
        if i2c is not None:
            try:
                i2c.deinit()
            except Exception:
                pass
print("== done ==")
