# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# Hardening test part 2: correct the cache sidecar's crc, clear the strike
# count, swap in a benign product.py (real one kept as product_real.py).
# Still offline (wifi.json points at the bogus SSID). Then reset the Pico:
# expect the parked LED Button to be rescued from the cache with no internet.
import json, microcontroller
from module_flasher import crc32

with open("/fw_led_button.bin", "rb") as f:
    img = f.read()
with open("/fw_led_button.json", "w") as f:
    json.dump({"version": "2.4.1", "layout": 2, "size": len(img), "crc32": "%08x" % crc32(img)}, f)
print("sidecar crc corrected to %08x" % crc32(img))

microcontroller.nvm[0] = 0xC0          # strikes = 0
print("strike count cleared")

with open("product.py") as f:
    real = f.read()
with open("product_real.py", "w") as f:
    f.write(real)
with open("product.py", "w") as f:
    f.write("# benign bench product: enumerate once, then idle\n"
            "import time\nfrom noknok import Conductor\n"
            "c = Conductor(); n = c.enumerate()\n"
            "print('[bench-product] running with', n, 'module(s):',\n"
            "      [hex(m.address) for m in c.ledbutton + c.buzzer])\n"
            "while True:\n    time.sleep(1)\n")
print("benign product.py installed (real one saved as product_real.py) - reset now")
