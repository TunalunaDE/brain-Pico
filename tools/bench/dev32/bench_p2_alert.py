# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# Pass-2 alert test: corrupt the LED Button cache sidecar's crc and park the
# module. On the next (online, not-due) boot the rescue must refuse the cache
# and alert_customer() must play the buzzer error motif before the product.
import json
from noknok import Conductor
from module_flasher import ModuleFlasher

meta = json.load(open("/fw_led_button.json"))
meta["crc32"] = "00000000"
json.dump(meta, open("/fw_led_button.json", "w"))
print("led_button sidecar crc corrupted")

c = Conductor(); c.enumerate()
m = c.ledbutton[0]
f = ModuleFlasher(c.i2c)
f.enter_bootloader(m.address); f.wait_for_bootloader(); f.erase()
print("LED Button parked at 0x7E:", f._read_status())
c.i2c.deinit()
print("reset now and LISTEN for the buzzer error motif")
