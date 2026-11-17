# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# read_fw_log.py - Pico (pico.py run): /log.txt since the last BOOT marker, without the AP-idle spam (needs /debug_log, see tools/bench README).
d = open("/log.txt").read().split("\n")
# find the last BOOT marker and print everything after it, minus AP-idle spam
start = 0
for i, l in enumerate(d):
    if "===== BOOT =====" in l:
        start = i
for l in d[start:]:
    if "waiting for setup" in l:
        continue
    print(l)
print("=== noknok_events.txt (tail) ===")
try:
    e = open("/noknok_events.txt").read().split("\n")
    print("\n".join(e[-12:]))
except Exception as ex:
    print(repr(ex))
