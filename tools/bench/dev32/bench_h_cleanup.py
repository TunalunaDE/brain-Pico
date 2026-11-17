# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
import os, microcontroller
microcontroller.nvm[0] = 0xC0
for f in ("product_real.py", "wifi_real.json"):
    try:
        os.remove(f)
    except OSError:
        pass
print("strikes cleared; bench temp files removed")
print("state:", sorted(f for f in os.listdir("/") if f.startswith(("fw_", "product", "wifi", "debug"))))
