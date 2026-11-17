# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# scan_bus.py - Pico (pico.py run): raw i2c.scan() on the known bus pin pairs (GP8/9, GP20/21, ...). A module at 0x7F waiting for enumeration is NOT visible here: use find_module.py.
import board, busio, time

PAIRS = (("GP8/GP9",   "GP9",  "GP8"),
         ("GP20/GP21", "GP21", "GP20"),
         ("GP4/GP5",   "GP5",  "GP4"),
         ("GP6/GP7",   "GP7",  "GP6"))

for name, scl_n, sda_n in PAIRS:
    try:
        i2c = busio.I2C(getattr(board, scl_n), getattr(board, sda_n), frequency=100000)
    except Exception as e:
        print(name, "init failed:", repr(e))
        continue
    try:
        t0 = time.monotonic()
        locked = False
        while time.monotonic() - t0 < 2:
            if i2c.try_lock():
                locked = True
                break
        if not locked:
            print(name, "could not lock")
        else:
            print(name, "->", [hex(a) for a in i2c.scan()])
            i2c.unlock()
    except Exception as e:
        print(name, "scan failed:", repr(e))
    finally:
        try:
            i2c.deinit()
        except Exception:
            pass
print("scan done")