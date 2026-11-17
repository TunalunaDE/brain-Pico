# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# find_module.py - hunt for a freshly restored noknok module on whichever pins
# the Qwiic cable happens to be wired to. A module waiting at 0x7F does NOT show
# up in a raw i2c.scan(), so only the Conductor's enumeration poll proves it.
import os
import board
from noknok import Conductor

env_sda = os.getenv("NOKNOK_I2C_SDA")
env_scl = os.getenv("NOKNOK_I2C_SCL")
print("settings.toml pins: SDA=%r SCL=%r" % (env_sda, env_scl))

CANDIDATES = [
    ("GP8", "GP9"),
    ("GP18", "GP19"),
    ("GP20", "GP21"),
    ("GP4", "GP5"),
    ("GP0", "GP1"),
    ("GP2", "GP3"),
    ("GP6", "GP7"),
    ("GP10", "GP11"),
]
if env_sda and env_scl and (env_sda, env_scl) not in CANDIDATES:
    CANDIDATES.insert(0, (env_sda, env_scl))

for sda_name, scl_name in CANDIDATES:
    sda = getattr(board, sda_name, None)
    scl = getattr(board, scl_name, None)
    if sda is None or scl is None:
        continue
    c = None
    try:
        c = Conductor(sda=sda, scl=scl)
        n = c.enumerate(total_timeout_sec=5)
        if n:
            print(">>> FOUND on %s/%s: %d module(s)" % (sda_name, scl_name, n))
            for kind in ("buzzer", "knob", "ledbutton", "display"):
                for m in getattr(c, kind, []):
                    print("      %-10s 0x%02X  fw %s  uid %s"
                          % (kind, m.address,
                             getattr(m, "firmware_version", None),
                             getattr(m, "_uid_hex", None)))
            break
        else:
            print("    %s/%s: bus ok, 0 modules" % (sda_name, scl_name))
    except Exception as e:
        print("    %s/%s: %s" % (sda_name, scl_name, type(e).__name__))
    finally:
        if c is not None:
            try:
                c.i2c.deinit()
            except Exception:
                pass
print("== done ==")
