# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# bench_dev78_phases.py - DEV-78 step 2 (visual): WHERE do the LEDs 16x glitches come from?
# Works with the LEDs 8x too (DEV-269): the first LEDs module found on the USB host is used.
# bench_dev78_parser.py proved the module receives and executes every command correctly
# while the glitches are visible, so this splits the LED-output side. A person watches the
# ring; the Display shows the phase letter. 60 s per phase, 5 s dark gap between phases:
#   A  SAME brightness (43) resent ~11/s + Display load  -> identical frames, re-transmitted
#   B  NO LED commands, static frame + Display load      -> nothing is transmitted to the LEDs
#   C  sweep 43->8->43 ~12/s, Display static (no load)   -> transmissions without I2C load
#   D  sweep 43->8->43 + Display load (the failing case) -> reference
# Glitches in A but not B = every re-transmission can go wrong (signal path), not the data.
# Glitches in B = the LEDs change without any data being sent (supply / noise on the board).
# The watcher CLICKS THE LED BUTTON at every glitch: each click is logged (phase, command
# number, level, seconds into the phase) and the button lights green ~0.3 s as a receipt.
# The button read is a 2-byte I2C poll per loop, tiny next to the Display redraws.
# Run: ./pico.py run bench_dev78_phases.py 330
import time

import noknok_usb
from noknok import Conductor, BLACK, WHITE

PHASE_S = 60
WARM = (160, 80, 0, 95)
SWEEP = list(range(43, 7, -1)) + list(range(8, 44))

# LEDs 16x (type 0x06, colour = 0x11 RGBW) or LEDs 8x (type 0x04, colour = 0x01 RGB, DEV-269)
mods = [x for x in noknok_usb.discover() if getattr(x[2], "MODULE_TYPE", 0) in (0x06, 0x04)]
m = mods[0][2]
COLOUR = bytes((0x11,) + WARM) if m.MODULE_TYPE == 0x06 else bytes((0x01,) + WARM[:3])
print("module", mods[0][0], "type 0x%02x fw" % m.MODULE_TYPE, m.version())
c = Conductor()
c.enumerate()
d = c.display[0]
d.native_text = False
btn = c.ledbutton[0] if c.ledbutton else None
btn.read() if btn else None                 # clear old edge flags
clicks = []
lit_until = 0
dev, EP = m._dev, m._EP_OUT


def put(b):
    dev.write(EP, bytes(b), timeout=1000)


def phase(letter, levels, load):
    d.clear(BLACK)
    d.text(letter, size=64, color=WHITE, x=0, y=8)
    put((0x03, 43))
    put(COLOUR)
    print("[phase %s] %s" % (letter, time.monotonic()))
    global lit_until
    t0, n, i = time.monotonic(), 0, 0
    lv = 43
    while time.monotonic() - t0 < PHASE_S:
        if btn:
            st = btn.read()
            now = time.monotonic()
            if st and st.press_event:
                clicks.append((letter, n, lv, round(now - t0, 1)))
                print("  CLICK phase %s cmd %d level %d at %.1f s" % clicks[-1])
                btn.set_color(0, 255, 0)
                lit_until = now + 0.3
            elif lit_until and now > lit_until:
                btn.set_color(0, 0, 0)
                lit_until = 0
        if levels:
            lv = levels[i % len(levels)]
            put((0x03, lv))
            i += 1
            n += 1
        if load:
            d.text("%04d" % (i % 10000), size=32, color=WHITE, x=70, y=24)
        else:
            time.sleep(0.08)
    print("  phase %s: %d LED commands in %d s, clicks %d" % (letter, n, PHASE_S, sum(1 for k in clicks if k[0] == letter)))
    put((0x00,))
    time.sleep(5)


phase("A", [43], True)
phase("B", [], True)
phase("C", SWEEP, False)
phase("D", SWEEP, True)
d.clear(BLACK)
d.text("end", size=48, color=WHITE, x=30, y=40)
for L in "ABCD":
    print("SUMMARY phase %s clicks %d" % (L, sum(1 for k in clicks if k[0] == L)))
print("DONE")
