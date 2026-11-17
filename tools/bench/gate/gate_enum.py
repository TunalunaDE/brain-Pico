# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# gate_enum.py - Pico side: enumerate both I2C buses + USB, print versions, assert the gate rig's set.
import noknok
from noknok import Conductor
c = Conductor(); c.enumerate_all()
missing = []
for name, lst in (("picohub", [c.picohub] if c.picohub else []), ("knob", c.knob), ("ledbutton", c.ledbutton), ("display", c.display)):
    if not lst: missing.append(name)
usb = list(getattr(c, "leds16", None) or []) + list(getattr(c, "leds", None) or [])
print("noknok", noknok.__version__)
for m in c.knob + c.ledbutton + c.display + c.buzzer:
    e = {"type": {"NoknokKnob": "knob", "NoknokLedButton": "led_button", "NoknokDisplay": "display", "NoknokBuzzer": "buzzer"}[type(m).__name__],
         "bus": "i2c", "i2c_bus": getattr(m, "i2c_bus", "A"), "address": m.address, "uid": m._uid_hex}
    try:
        bl = c.bootloader_version(e)
    except Exception as ex:
        bl = repr(ex)
    tag = type(m).__name__.replace("Noknok", "").upper()
    print("%s fw %s bl %s uid %s bus %s" % (tag, getattr(m, "firmware_version", None), bl, m._uid_hex, getattr(m, "i2c_bus", "A")))
print("PICOHUB", c.picohub)
print("USB modules:", len(usb))
if not usb: missing.append("usb_leds")
print("MISSING:", missing)
print("GATE_ENUM_OK" if not missing else "GATE_ENUM_FAIL")
