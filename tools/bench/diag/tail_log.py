# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# tail_log.py - Pico (pico.py run): last 14 lines of /log.txt.
import os
try:
    d = open("/log.txt").read().split("\n")
    print("\n".join(d[-14:]))
except Exception as e:
    print("log.txt:", repr(e))
print("--- files:", ", ".join(f for f in sorted(os.listdir("/")) if f.endswith((".json", ".py", ".txt", ".bin"))))
