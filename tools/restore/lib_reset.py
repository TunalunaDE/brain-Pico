# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# lib_reset.py - Pico (pico.py run): ONLY /lib is broken (ImportError adafruit_httpserver after yank tests): park it as /lib_bad, make an empty /lib. Then lib_push.sh. No reformat.
import os, noknok
with noknok.writable():
    os.rename("/lib", "/lib_bad")
    os.mkdir("/lib")
print("root:", os.listdir("/"))
print("lib:", os.listdir("/lib"))