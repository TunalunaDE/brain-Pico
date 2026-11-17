# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# Hardening test part 3: online + parked (strikes=3) + product.py that differs
# from the published one (the benign bench script). Debug marker REMOVED so
# log.txt must not grow except by crash flushes. Expect on reset:
#   safe_idle(connected=True) -> fetch product.py -> differs -> strikes reset
#   -> reload -> online boot, OTA pass (all current) -> real whack_a_mole runs
#   -> SystemExit (1-button bench) x3 -> parked again, 3 ring flushes.
import os, microcontroller
with open("wifi_real.json") as f:
    real = f.read()
with open("wifi.json", "w") as f:
    f.write(real)
os.remove("wifi_real.json")
print("real wifi.json restored")
microcontroller.nvm[0] = 0xC0 | 3
print("strike count set to 3 (parked)")
try:
    os.remove("/debug_log")
    print("debug_log marker removed")
except OSError:
    print("debug_log marker was not present")
print("log.txt size before:", os.stat("log.txt")[6])
print("reset now")
