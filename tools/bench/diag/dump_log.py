# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# dump_log.py - Pico (pico.py run): size + last 6 KB of /log.txt.
try:
    d = open("/log.txt").read()
    print("=== log.txt: %d bytes, tail below ===" % len(d))
    print(d[-6000:])
except Exception as e:
    print("log.txt: %r" % (e,))
print("=== files ===")
import os
for f in sorted(os.listdir("/")):
    try:
        print("%-28s %d" % (f, os.stat("/" + f)[6]))
    except Exception:
        print(f)
