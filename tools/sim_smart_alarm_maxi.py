# SPDX-License-Identifier: MIT
# sim_smart_alarm_maxi.py - desktop test of poc/scripts/smart_alarm_maxi.py (DEV-236), tier S.
# Needs the poc and module-I2C-1.42-display repos cloned beside brain-Pico.
#   python tools/sim_smart_alarm_maxi.py         (exit code 1 on any FAIL)
# Runs the REAL product script against: the real NoknokDisplay driver on the
# display_sim virtual panel (with SET_ROTATION resizing the panel), fake
# button / knob / buzzer / LEDs, fake settings, and a fake clock.
# A scenario is a generator called from c.sleep(): it moves the clock, presses
# buttons, changes settings "from the app", and asserts.
import sys, os, types, calendar, json, traceback

BP = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(BP, "..", "..", "poc", "scripts", "smart_alarm_maxi.py")
OUT = os.environ.get("SIM_PNG_DIR")   # set it to get PNG screenshots (needs Pillow)
sys.path.insert(0, BP)
import display_sim
from display_sim import VirtualPanel, FakeI2C
display_sim._stub_modules()
import noknok

class RotPanel(VirtualPanel):
    def command(self, cmd):
        if cmd[0] == 0x11:                       # SET_ROTATION: odd = landscape
            self.rot = cmd[1]
            self.resize(160, 80) if cmd[1] & 1 else self.resize(80, 160)
        super().command(cmd)

# ── fake clock ───────────────────────────────────────────────────────────────
class Clock:
    mono = 1000.0
    utc = calendar.timegm((2026, 11, 16, 5, 0, 0))   # 06:00 CET
clk = Clock()
ft = types.ModuleType("time")
ft.monotonic = lambda: clk.mono
ft.time = lambda: clk.utc
import time as _rt
ft.localtime = lambda t=None: _rt.gmtime(clk.utc if t is None else t)
ft.mktime = lambda tup: calendar.timegm(tuple(tup[:6]) + (0, 0, 0))
ft.sleep = lambda s: None
def advance(sec):
    clk.mono += sec; clk.utc += sec

# ── fake modules ─────────────────────────────────────────────────────────────
class Ev:
    def __init__(self, pressed=False, press_event=False, release_event=False, delta=0):
        self.pressed, self.press_event, self.release_event, self.delta = pressed, press_event, release_event, delta

class Button:
    def __init__(self): self.q = []; self.down = False; self.log = []
    def read(self):
        if self.q:
            e = self.q.pop(0); self.down = e.pressed; return e
        return Ev(pressed=self.down)
    def set_color(self, *rgb): self.log.append(("color", rgb))
    def led_off(self): self.log.append(("off",))

class Knob:
    def __init__(self): self.q = []; self.down = False
    def read(self):
        if self.q:
            e = self.q.pop(0); self.down = e.pressed; return e
        return Ev(pressed=self.down)

class Buzzer:
    def __init__(self): self.log = []
    def play(self, f, ms, vol=100): self.log.append((round(clk.mono, 2), f, ms, vol))
    def stop(self): self.log.append((round(clk.mono, 2), "stop"))

class Lamp16:
    PRESET_BREATHE = 2
    def __init__(self): self.log = []; self.level = None; self.isoff = False
    def white(self, *a): pass
    def set_brightness(self, l): self.level = l; self.isoff = False; self.log.append(("bri", l))
    def set_all(self, *c): self.isoff = False; self.log.append(("all", c))
    def off(self): self.isoff = True; self.log.append(("off",))
    def play_preset(self, *a): self.log.append(("preset", a))

class Settings:
    def __init__(self): self.v = {}; self.cbs = []
    def defaults(self, d):
        for k, x in d.items(): self.v.setdefault(k, x)
    def get(self, k, d=None): return self.v.get(k, d)
    def set(self, k, x):
        ch = self.v.get(k) != x; self.v[k] = x; return ch
    def info(self, k, fn): self.infofn = fn
    def on_change(self, cb): self.cbs.append(cb)
    def all(self): return dict(self.v)
    def app(self, **kw):                         # a change from the app
        ch = {k: x for k, x in kw.items() if self.v.get(k) != x}
        self.v.update(kw)
        for cb in self.cbs: cb(ch)

class Stop(Exception): pass

class World:
    def __init__(self, preset=None):
        self.panel = RotPanel(160, 80)
        self.display = noknok.NoknokDisplay(FakeI2C(self.panel))
        self.button, self.knob, self.buzzer, self.lamp = Button(), Knob(), Buzzer(), Lamp16()
        self.s = Settings()
        if preset: self.s.v.update(preset)
w = None

class FakeConductor:
    def __init__(self):
        self.ledbutton = [w.button]; self.knob = [w.knob]; self.buzzer = [w.buzzer]
        self.display = [w.display]; self.leds16 = [w.lamp]; self.leds = []
        self.settings = w.s
    def enumerate_all(self): pass
    def load_roles(self): pass
    def sleep(self, s):
        advance(s)
        try:
            next(w.scen)
        except StopIteration:
            raise Stop()

# ── scenario helpers (each `yield` = one main-loop pass, 30 ms) ─────────────
def loops(n):
    for _ in range(n): yield
def wait(sec):
    for _ in range(int(sec / 0.03) + 1): yield
def press(dev, hold=0.1):
    dev.q.append(Ev(pressed=True, press_event=True))
    yield from wait(hold)
    dev.q.append(Ev(pressed=False, release_event=True))
    yield
def tap(dev): yield from press(dev, 0.1)
def turn(n):
    w.knob.q.append(Ev(pressed=False, delta=n)); yield

fails = []
def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "   -> " + str(detail)))
    if not cond: fails.append(name)

def png(name):
    if not OUT:
        return
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return
    p = w.panel
    im = Image.new("RGB", (p.w, p.h))
    for y in range(p.h):
        for x in range(p.w):
            c = p.px[y][x]
            im.putpixel((x, y), (((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31))
    im = im.resize((p.w * 4, p.h * 4), Image.NEAREST)
    d = ImageDraw.Draw(im)
    d.rectangle([5 * 4, 5 * 4, (p.w - 5) * 4 - 1, (p.h - 5) * 4 - 1], outline=(255, 0, 0))   # safe area
    im.save(os.path.join(OUT, name + ".png"))

def outside_safe():
    """Non-black pixels in the 5 px border."""
    p = w.panel; n = 0
    for y in range(p.h):
        for x in range(p.w):
            if (x < 5 or y < 5 or x >= p.w - 5 or y >= p.h - 5) and p.px[y][x] != 0:
                n += 1
    return n

def run(scenario, preset=None):
    global w
    w = World(preset)
    w.scen = scenario()
    noknok.Conductor = FakeConductor
    real_time = sys.modules["time"]
    sys.modules["time"] = ft
    try:
        src = open(SCRIPT, encoding="utf-8").read()
        g = {"__name__": "product"}
        w.g = g
        try:
            exec(compile(src, SCRIPT, "exec"), g)
        except Stop:
            pass
        except Exception:
            traceback.print_exc(); fails.append("crash")
    finally:
        sys.modules["time"] = real_time
    return g


# ======================================================================
# Tests
# ======================================================================
H = sys.modules[__name__]

def G(): return H.w.g

# 1. Layouts in all four rotations: inside the safe area, home + menu + edit
def layouts():
    for rot in ["0", "90", "180", "270"]:
        H.w.s.app(rotation=rot)
        yield from wait(0.2)
        p = H.w.panel
        land = rot in ("0", "180")
        check("rot %s panel size" % rot, (p.w, p.h) == ((160, 80) if land else (80, 160)), (p.w, p.h))
        # arm both alarms + start a timer so every home element is drawn
        H.w.s.app(alarm_armed="both")
        yield from wait(0.2)
        check("rot %s home inside safe area" % rot, outside_safe() == 0, outside_safe())
        check("rot %s no display error" % rot, p.last_err == 0, p.last_err)
        png("home_%s" % rot)
        # menu: knob hold 2 s
        yield from press(H.w.knob, 2.2)
        yield from wait(0.2)
        check("rot %s menu open" % rot, G()["screen"] == "menu", G()["screen"])
        check("rot %s menu inside safe area" % rot, outside_safe() == 0, outside_safe())
        png("menu_%s" % rot)
        # every menu item and its edit screen
        for i, item in enumerate(G()["MENU"]):
            G()["menu_idx"] = i
            yield from wait(0.1)
            check("rot %s item %r inside" % (rot, item), outside_safe() == 0 and p.last_err == 0, (outside_safe(), p.last_err))
            if item in ("Back",):
                continue
            yield from tap(H.w.knob)
            yield from wait(0.1)
            for _ in range(3):
                yield from turn(1)
                yield from wait(0.1)
                check("rot %s edit %r value %r inside" % (rot, item, G()["edit_value_text"]() if G()["edit"] else None),
                      outside_safe() == 0 and p.last_err == 0, (outside_safe(), p.last_err))
            if item == "Tone":
                png("edit_tone_%s" % rot)
            # back with the LED button
            yield from tap(H.w.button)
            yield from wait(0.1)
            check("rot %s LED button edit -> menu" % rot, G()["screen"] == "menu", G()["screen"])
            if item == "Display":     # the turns must not have changed the rotation
                check("rot %s back = no change" % rot, H.w.s.get("rotation") == rot)
        yield from tap(H.w.button)
        yield from wait(0.1)
        check("rot %s LED button menu -> home" % rot, G()["screen"] == "home", G()["screen"])
        H.w.s.app(alarm_armed="off")
        yield from wait(0.1)
print("== layouts"); H.run(layouts)

# 2. Button mapping on the home screen
def buttons():
    s = H.w.s
    yield from wait(0.5)
    seq = []
    for _ in range(4):
        yield from tap(H.w.button)
        yield from wait(0.5)
        seq.append(s.get("alarm_armed"))
    check("single press cycles 1 -> 2 -> both -> off", seq == ["1", "2", "both", "off"], seq)
    on0 = s.get("on")
    yield from press(H.w.button, 1.3)
    yield from wait(0.6)
    check("hold toggles the lamp", s.get("on") != on0 and s.get("alarm_armed") == "off", (s.get("on"), s.get("alarm_armed")))
    yield from press(H.w.button, 1.3)
    yield from wait(0.6)
    check("hold again toggles back", s.get("on") == on0)
    # double press
    yield from tap(H.w.button); yield from wait(0.1); yield from tap(H.w.button)
    yield from wait(0.6)
    check("double press starts Sundown", G()["sundown_end"] is not None)
    check("double press does not arm", s.get("alarm_armed") == "off", s.get("alarm_armed"))
    # single press acts only after the double window
    yield from tap(H.w.button)
    yield from loops(3)
    check("single press waits for the double window", s.get("alarm_armed") == "off")
    yield from wait(0.5)
    check("then arms", s.get("alarm_armed") == "1")
print("== buttons"); H.run(buttons)

# 3. Two alarms, wake-up light, tones, snooze
def alarms():
    s = H.w.s
    # clock 06:00 CET; alarm 1 at 06:20, alarm 2 at 06:40, sunrise 15 min, tone mozart
    s.app(alarm1_time="06:20", alarm2_time="06:40", alarm_armed="both", alarm_tone="mozart", on=False)
    yield from wait(1)
    check("info shows next alarm", H.w.g["_info_text"](H.w.g["time"].monotonic()) == "Alarm 06:20",
          H.w.g["_info_text"](H.w.g["time"].monotonic()))
    advance(6 * 60); yield from wait(3)                     # 06:06: ramp started for alarm 1
    check("wake-up light ramps before alarm 1", G()["sunrise_level"] is not None and s.get("on"), G()["sunrise_level"])
    advance(14 * 60); yield from wait(0.5)                  # 06:20
    check("alarm 1 rings", G()["ringing"] == "alarm")
    notes = [e[1] for e in H.w.buzzer.log[-8:] if e[1] != "stop"]
    check("mozart notes played", set(notes) <= {784, 587, 988, 1175} and 784 in notes, notes)
    yield from tap(H.w.button); yield from wait(0.5)
    check("press snoozes", G()["ringing"] is None and G()["snooze_until"] is not None)
    advance(5 * 60); yield from wait(0.5)
    check("snooze rings again", G()["ringing"] == "alarm")
    yield from press(H.w.button, 1.3); yield from wait(0.5)
    check("hold stops", G()["ringing"] is None and G()["snooze_until"] is None)
    check("hold while ringing does NOT toggle the lamp", s.get("on"))
    advance(14 * 60); yield from wait(0.5)                  # 06:39 -> alarm 2 ramp
    advance(60); yield from wait(0.5)                       # 06:40
    check("alarm 2 rings", G()["ringing"] == "alarm")
    yield from press(H.w.button, 1.3); yield from wait(0.5)
    # only alarm 2 armed: alarm 1 time must not ring
    s.app(alarm_armed="2", alarm1_time="06:45", alarm2_time="07:30")
    advance(5 * 60); yield from wait(0.5)
    check("disarmed alarm 1 stays silent", G()["ringing"] is None)
print("== alarms"); H.run(alarms)

# 4. Every tone plays (preview) and the menu tone choice is saved
def tones():
    yield from press(H.w.knob, 2.2)
    G()["menu_idx"] = G()["MENU"].index("Tone")
    yield from tap(H.w.knob)
    heard = {}
    for _ in range(6):
        H.w.buzzer.log.clear()
        yield from turn(1)
        yield from wait(4)
        heard[G()["TONE_ORDER"][G()["edit"]["v"]]] = len([e for e in H.w.buzzer.log if e[1] != "stop"])
    check("all six tones preview", len(heard) == 6 and all(v >= 3 for v in heard.values()), heard)
    for _ in range(3): yield from turn(1); yield from wait(0.1)      # -> chiptune
    yield from tap(H.w.knob); yield from wait(0.2)
    check("tone saved", H.w.s.get("alarm_tone") == "chiptune", H.w.s.get("alarm_tone"))
    check("back home after save", G()["screen"] == "home")
print("== tones"); H.run(tones)

# 5. Rotation chosen in the menu, kept across a restart
def rot_menu():
    yield from press(H.w.knob, 2.2)
    G()["menu_idx"] = G()["MENU"].index("Display")
    yield from tap(H.w.knob)
    yield from turn(1); yield from wait(0.1)
    yield from tap(H.w.knob); yield from wait(0.3)
    check("menu sets 90 deg", H.w.s.get("rotation") == "90" and (H.w.panel.w, H.w.panel.h) == (80, 160))
    check("portrait home inside safe area", outside_safe() == 0, outside_safe())
H.run(rot_menu)
def restart():
    yield from wait(0.3)
    check("restart comes up in portrait", (H.w.panel.w, H.w.panel.h) == (80, 160))
print("== rotation via menu + restart"); H.run(restart, preset={"rotation": "90"})

# 6. Reset keeps timezone + rotation
def reset():
    H.w.s.app(timezone="us_e", rotation="180", alarm_armed="both", alarm_tone="birds")
    yield from press(H.w.knob, 2.2)
    G()["menu_idx"] = G()["MENU"].index("Reset")
    yield from tap(H.w.knob); yield from turn(1); yield from tap(H.w.knob); yield from wait(0.2)
    s = H.w.s
    check("reset clears alarms + tone, keeps timezone + rotation",
          s.get("alarm_armed") == "off" and s.get("alarm_tone") == "classic" and s.get("timezone") == "us_e" and s.get("rotation") == "180",
          s.all())
print("== reset"); H.run(reset)

print("\nFAILS:", H.fails if H.fails else "none")
sys.exit(1 if H.fails else 0)
