# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
import os, microcontroller, json
print("cache files:", sorted(f for f in os.listdir("/") if f.startswith("fw_")))
for t in ("buzzer", "knob", "led_button"):
    try:
        print("  ", t, json.load(open("/fw_%s.json" % t)))
    except Exception as e:
        print("  ", t, "no sidecar")
t = int.from_bytes(bytes(microcontroller.nvm[1:5]), "little")
print("nvm last-check:", t, "(unset)" if t == 0 else "")
print("strike byte: 0x%02x" % microcontroller.nvm[0])
d = open("log.txt").read().split("\n")
i = max(k for k, l in enumerate(d) if "===== BOOT =====" in l)
print("=== last boot block (%d lines) ===" % (len(d) - i))
for l in d[i:]:
    if "waiting for setup" not in l and l:
        print(l)
