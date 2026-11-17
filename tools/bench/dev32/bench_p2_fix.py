# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
import json, os
from module_flasher import crc32
img = open("/fw_led_button.bin", "rb").read()
meta = json.load(open("/fw_led_button.json"))
meta["crc32"] = "%08x" % crc32(img)
json.dump(meta, open("/fw_led_button.json", "w"))
print("sidecar crc restored to", meta["crc32"])
with open("product_real.py") as f:
    real = f.read()
with open("product.py", "w") as f:
    f.write(real)
os.remove("product_real.py")
try:
    os.remove("/debug_log")
except OSError:
    pass
print("real product.py restored, debug marker removed - reset now")
