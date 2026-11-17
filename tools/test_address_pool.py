# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# test_address_pool.py - DEV-246 (RDM-13), tier S (host Python, no hardware).
#
# Drives the real Conductor.enumerate() against a fake bus (fakes copied from
# test_foreign_device.py). Proves:
#   pool      - 25 new modules on a fresh brain: none gets a THIRDPARTY_ADDRESSES address,
#               so a Qwiic board plugged in later cannot collide with them.
#   list      - the list has no duplicates and nothing in 0x50-0x57 (brain FRAM).
#   fallback  - more modules than free pool addresses: the extra ones get reserved
#               addresses, all unique, never 0x50-0x57, never past 0x77.
#   keep      - a module saved at a now-reserved address (older brain) keeps it.
#   foreign   - DEV-119 still holds: an answering foreign device's address is skipped.
#
# Run from the repo root:   python -I tools/test_address_pool.py

import io
import os
import sys
import types
import contextlib

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "software"))

board = types.ModuleType("board")
for n in range(29):
    setattr(board, "GP%d" % n, "GP%d" % n)
board.LED = "LED"
sys.modules["board"] = board
mc = types.ModuleType("microcontroller")
mc.nvm = bytearray(4096)
sys.modules["microcontroller"] = mc
for name in ("digitalio", "supervisor"):
    sys.modules[name] = types.ModuleType(name)


def crc8(data):
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


class NoknokDev:
    def __init__(self, uid_hex, mtype):
        self.uid = bytes.fromhex(uid_hex)
        self.type = mtype
        self.address = None          # None = waiting at 0x7F
        self.last_cmd = None
        self.miss_b1 = 0             # GET_VERSION replies to drop (module busy)
        self.armed = False           # a 0xB1 was just written (not a presence ping)
        self.has_bl = True           # answers 0xB0 by going to its bootloader at 0x7E
        self.fw = (2, 3, 0)          # GET_VERSION reply (DEV-204 compares it)

    def reply(self, buf):
        if self.last_cmd == 0xB1:
            if self.miss_b1 and self.armed:
                self.miss_b1 -= 1
                self.armed = False
                raise OSError(19)
            self.armed = False
            buf[:4] = bytes([1] + list(self.fw))[:len(buf)]
        else:
            for i in range(len(buf)):
                buf[i] = 0


class ForeignDev:
    """A non-noknok chip at a fixed address: answers every read with its
    register contents (0x00 / 0x3C...), never the noknok protocol byte."""
    def __init__(self, address, nak_reads=False):
        self.address = address
        self.nak_reads = nak_reads
        self.writes = 0
        self.cmds = []

    def reply(self, buf):
        if self.nak_reads:
            raise OSError(19)
        for i in range(len(buf)):
            buf[i] = 0x3C if i == 0 else 0


PERIPHERAL = {("GP11", "GP10"): 1, ("GP21", "GP20"): 0}
WIRED = {}
OPEN = {}


class FakeBus:
    def __init__(self, scl, sda, frequency=100_000):
        key = (scl, sda)
        if key not in PERIPHERAL:
            raise ValueError("No pull up found on SDA or SCL; check your wiring")
        per = PERIPHERAL[key]
        if per in OPEN:
            raise ValueError("I2C peripheral in use")
        OPEN[per] = self
        self.per = per
        self.devs = WIRED.setdefault(key, [])
        self.pending = None

    def try_lock(self):
        return True

    def unlock(self):
        pass

    def deinit(self):
        OPEN.pop(self.per, None)

    def _at(self, addr):
        for d in self.devs:
            if d.address == addr:
                return d
        return None

    def readfrom_into(self, addr, buf):
        if addr == 0x7E:
            d = self._at(0x7E)
            if d is None:
                raise OSError(19)
            for i in range(len(buf)):
                buf[i] = 0                   # bootloader status: idle, no error
            return
        if addr == 0x7F:
            for d in self.devs:
                if isinstance(d, NoknokDev) and d.address is None:
                    self.pending = d
                    rec = d.uid + bytes([d.type])
                    buf[:10] = rec + bytes([crc8(rec)])
                    return
            raise OSError(19)
        d = self._at(addr)
        if d is None:
            raise OSError(19)
        d.reply(buf)

    def writeto(self, addr, data):
        data = bytes(data)
        if addr == 0x7F:
            if self.pending is None or data[0] != 0x1D:
                raise OSError(19)
            self.pending.address = data[1]
            self.pending = None
            return
        d = self._at(addr)
        if d is None:
            raise OSError(19)
        if addr == 0x7E and isinstance(d, NoknokDev):
            if data and data[0] == 0x05:     # bootloader BOOT: the app restarts at 0x7F
                d.address = None
            return
        if isinstance(d, NoknokDev) and data and data[0] == 0xB0 and d.has_bl:
            d.address = 0x7E                 # app -> bootloader
            return
        if isinstance(d, ForeignDev):
            d.writes += 1
            d.cmds.append(data[0] if data else None)
        else:
            d.last_cmd = data[0] if data else None
            d.armed = d.last_cmd == 0xB1

    def scan(self):
        return sorted(d.address for d in self.devs if d.address and 0x08 <= d.address <= 0x77)


busio = types.ModuleType("busio")
busio.I2C = FakeBus
sys.modules["busio"] = busio

import noknok   # noqa: E402
noknok.time.sleep = lambda s: None

MOD0011 = {"NOKNOK_I2C_SDA": "GP10", "NOKNOK_I2C_SCL": "GP11",
           "NOKNOK_I2C_B_SDA": "GP20", "NOKNOK_I2C_B_SCL": "GP21"}
os.environ.update(MOD0011)
A, B = ("GP11", "GP10"), ("GP21", "GP20")
BUZ, KNOB, LEDB = "cdab67a8bcbdf011", "cdabaaa8bcbd3312", "cdab315428be26be"
HUB = "cdab6e273abc758f"

fails = 0
def check(name, cond, extra=""):
    global fails
    print("  %-66s %s %s" % (name, "PASS" if cond else "FAIL", extra if not cond else ""))
    if not cond:
        fails += 1


def boot(keep_store=True):
    """New VM: buses released, Store re-read; modules keep their addresses
    (a brain reload, not a power cycle) unless power_cycle() was called."""
    for b in list(OPEN.values()):
        b.deinit()
    noknok._pin_config = None
    noknok._store = None
    if not keep_store:
        mc.nvm[:] = bytearray(4096)
    c = noknok.Conductor()
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        c.enumerate()
    return c, out.getvalue()


def addrs(c):
    return {m._uid_hex: m.address for m in c._registry.values() if m is not None}


TP = noknok.Conductor.THIRDPARTY_ADDRESSES
FREE = [a for a in range(0x08, 0x78) if a not in TP and not 0x50 <= a <= 0x57]


def mods(n, start=0):
    return [NoknokDev("cdab%012x" % (0x100 + start + i), 0x01) for i in range(n)]


print("list: THIRDPARTY_ADDRESSES is sane")
check("48 addresses, none in 0x50-0x57, all in 0x08-0x77",
      len(TP) == 48 and not any(0x50 <= a <= 0x57 for a in TP)
      and all(0x08 <= a <= 0x77 for a in TP), sorted(TP))
check("56 addresses before the fallback", len(FREE) == 56, len(FREE))

print("pool: 25 new modules avoid the third-party addresses")
WIRED.clear()
WIRED[A] = mods(13)
WIRED[B] = mods(12, start=100)
c, log = boot(keep_store=False)
got = sorted(addrs(c).values())
check("25 modules found", len(got) == 25, got)
check("...none on a third-party address", not set(got) & TP,
      [hex(a) for a in sorted(set(got) & TP)])
check("...they took the first 25 pool addresses", got == FREE[:25],
      " ".join("%02X" % a for a in got))

def power_cycle():
    for devs in WIRED.values():
        for d in devs:
            if isinstance(d, NoknokDev):
                d.address = None


print("keep: a module saved at a now-reserved address keeps it after a power cycle")
WIRED.clear()
old = NoknokDev("cdab0000000000aa", 0x01)
WIRED[A] = [old]
c, log = boot(keep_store=False)
uid = old.uid.hex()
check("fresh brain gives it a pool address", addrs(c).get(uid) in FREE, repr(addrs(c)))
c._registry[uid].address = 0x10                  # as if an older brain had given it 0x10
old.address = 0x10
c._save_state()
power_cycle()                                    # module back at 0x7F, brain remembers 0x10
c, log = boot(keep_store=True)
check("...re-enumerated at its saved 0x10, not moved", addrs(c).get(uid) == 0x10,
      repr(addrs(c)))

print("foreign: DEV-119 skip still holds inside the pool")
WIRED.clear()
WIRED[A] = [ForeignDev(FREE[0])] + mods(3, start=300)
c, log = boot(keep_store=False)
got = sorted(addrs(c).values())
check("first pool address skipped (foreign device answers there)", FREE[0] not in got,
      " ".join("%02X" % a for a in got))
check("...modules took the next pool addresses", got == FREE[1:4],
      " ".join("%02X" % a for a in got))

print("fallback: more modules than pool addresses")
WIRED.clear()
WIRED[A] = mods(len(FREE) + 3, start=500)
c, log = boot(keep_store=False)
got = list(addrs(c).values())
extra = sorted(a for a in got if a in TP)
check("%d modules found, all unique" % (len(FREE) + 3),
      len(got) == len(FREE) + 3 and len(set(got)) == len(got), len(got))
check("...exactly 3 got a third-party address (the fallback)", len(extra) == 3,
      [hex(a) for a in extra])
check("...none in 0x50-0x57 or past 0x77",
      not any(0x50 <= a <= 0x57 or a > 0x77 or a < 0x08 for a in got))

print("PASS (0 failures)" if not fails else "FAIL (%d failures)" % fails)
sys.exit(1 if fails else 0)
