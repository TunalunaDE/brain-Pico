# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# env_check.py - Pico (pico.py run), read-only: the NOKNOK_* settings as CircuitPython parsed them + the first lines of settings.toml.
import os
print("--- os.getenv as CircuitPython parses settings.toml ---")
for k in ("NOKNOK_USB_DRIVE", "NOKNOK_I2C_SDA", "NOKNOK_I2C_SCL",
          "NOKNOK_I2C_FREQ", "NOKNOK_USB_DP", "NOKNOK_USB_DM"):
    print("  %-18s = %r" % (k, os.getenv(k)))
print("--- first 30 lines of settings.toml on device ---")
try:
    with open("/settings.toml") as f:
        for i, line in enumerate(f):
            if i >= 30:
                break
            print("  %2d| %s" % (i + 1, line.rstrip()))
except Exception as e:
    print("  ERR", e)
print("--- boot.py first line ---")
try:
    print("  " + open("/boot.py").readline().rstrip())
except Exception as e:
    print("  ERR", e)
