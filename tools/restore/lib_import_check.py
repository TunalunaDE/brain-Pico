# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# lib_import_check.py - Pico (pico.py run): prints IMPORT_OK when the network libraries code.py needs import from /lib.
import os, adafruit_httpserver, adafruit_requests, adafruit_ntp
print("IMPORT_OK", sorted(os.listdir("/lib")), len(os.listdir("/lib/adafruit_httpserver")))
