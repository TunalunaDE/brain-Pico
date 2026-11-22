# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# list_modules.py - enumerate every module the brain sees and print type, bus, UID, I2C address and the
# installed firmware version (DEV-197: tie a module in the SWD clamp - minichlink UNIID - to the brain's
# view, and check its version after a flash). Writes nothing to the Pico FS, makes no noise, updates nothing.
#   ./pico.py run tools/bench/diag/list_modules.py 60      then ./pico.py reset to start the product again
import time
import noknok
from noknok import Conductor

print("noknok", noknok.__version__)
c = Conductor()
t0 = time.monotonic()
n = c.enumerate_all()
print("enumerate_all: %d modules in %.1f s" % (n, time.monotonic() - t0))
for m in getattr(c, "_registry", {}).values():
    print("MODULE type=%s bus=%s uid=%s addr=%s fw=%s proto=%s" % (
        type(m).__name__, getattr(m, "i2c_bus", "usb"), getattr(m, "_uid_hex", getattr(m, "serial", None)),
        (hex(m.address) if isinstance(getattr(m, "address", None), int) else getattr(m, "address", None)),
        getattr(m, "firmware_version", None), getattr(m, "protocol_version", None)))
print("DONE")
