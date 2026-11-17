# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# Hardening test setup: plant a rescue cache with a WRONG crc, park the LED
# Button (erase its app over I2C), and point wifi.json at a network that does
# not exist. Keeps the real wifi.json as wifi_real.json.
import json, os
from noknok import Conductor
from module_flasher import ModuleFlasher, crc32

# 1. cache with deliberately wrong crc (integrity check must refuse it)
with open("keyboard_firmware.bin", "rb") as f:
    img = f.read()
with open("/fw_led_button.bin", "wb") as f:
    f.write(img)
with open("/fw_led_button.json", "w") as f:
    json.dump({"version": "2.4.1", "layout": 2, "size": len(img), "crc32": "00000000"}, f)
print("cache planted: %d B, real crc %08x, sidecar says 00000000" % (len(img), crc32(img)))

# 2. park the LED Button: into bootloader, erase app, leave it there
c = Conductor(); c.enumerate()
if not c.ledbutton:
    raise SystemExit("no LED Button on the bus")
m = c.ledbutton[0]
f = ModuleFlasher(c.i2c)
f.enter_bootloader(m.address)
f.wait_for_bootloader()
f.erase()
st = f._read_status()
print("LED Button parked at 0x7E, status", st, "(no valid app)")
c.i2c.deinit()

# 3. wrong SSID
with open("wifi.json") as fh:
    real = fh.read()
with open("wifi_real.json", "w") as fh:
    fh.write(real)
w = json.loads(real)
w["ssid"] = "noknok-no-such-network"
with open("wifi.json", "w") as fh:
    json.dump(w, fh)
print("wifi.json now points at a non-existent SSID (real one saved)")
os.remove("/debug_log") if "debug_log" in os.listdir("/") else None
with open("/debug_log", "w") as fh:
    fh.write("")
print("debug_log marker created; ready — reset the Pico")
