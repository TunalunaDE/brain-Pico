# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# Pass-2 test 1: update_all(exclude_uids=...) leaves an outdated module alone.
# Fakes a newer led_button version (same major, so the DEV-3 policy allows it),
# uses a get_image that RAISES so nothing can ever be flashed, and checks who
# was attempted. Also installs the benign bench product for the boot tests.
from noknok import Conductor

c = Conductor(); c.enumerate()
lb = c.ledbutton[0]
uid = lb._uid_hex
fake = {"led_button": {"version": "2.9.9", "url": "x"}}

rep = [r for r in c.firmware_report(fake) if r["needs_update"]]
print("outdated per fake index:", [(r["type"], r["uid"]) for r in rep])
assert any(r["uid"] == uid for r in rep), "FAIL: fake version did not flag the LED Button"

calls = []
def get_image(entry):
    calls.append(entry["uid"])
    raise RuntimeError("no image on purpose")

res = c.update_all(fake, get_image, logfn=lambda *_: None, exclude_uids={uid})
print("with exclude:   attempted", [r["uid"] for r in res], "get_image calls", calls)
assert res == [] and calls == [], "FAIL: excluded module was attempted"

res = c.update_all(fake, get_image, logfn=lambda *_: None)
print("without exclude: attempted", [r["uid"] for r in res], "get_image calls", calls)
assert calls == [uid] and res and res[0]["updated"] is False, "FAIL: unexcluded module not attempted"
print("PASS - exclusion honoured, nothing flashed; LED Button still", lb.firmware_version)

with open("product.py") as f:
    real = f.read()
with open("product_real.py", "w") as f:
    f.write(real)
with open("product.py", "w") as f:
    f.write("import time\nfrom noknok import Conductor\n"
            "c = Conductor(); print('[bench-product]', c.enumerate(), 'module(s)')\n"
            "while True:\n    time.sleep(1)\n")
open("/debug_log", "w").close()
import microcontroller
microcontroller.nvm[0] = 0xC0                    # strikes 0
microcontroller.nvm[1:5] = bytes(4)              # no last OTA check on record
print("benign product installed, debug marker on, strikes + last-check cleared")
c.i2c.deinit()
