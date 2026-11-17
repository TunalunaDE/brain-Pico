# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# probe_bus.py - Pico (pico.py run): Conductor enumerate, prints the address of every module per type.
from noknok import Conductor
c = Conductor()
c.enumerate()
print("buzzer   :", [hex(m.address) for m in c.buzzer])
print("knob     :", [hex(m.address) for m in c.knob])
print("ledbutton:", [hex(m.address) for m in c.ledbutton])
print("display  :", [hex(m.address) for m in c.display])
if c.display:
    d = c.display[0]
    try:
        print("display info:", d.info(refresh=True))
        print("display fw  :", d.version() if hasattr(d, "version") else "n/a")
    except Exception as e:
        print("display info error:", repr(e))