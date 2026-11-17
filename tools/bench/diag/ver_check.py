# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# Read-only version check on the rig's Pico (run with pico.py run): brain files + PicoHub power manager.
import os, time, board, busio, microcontroller

print("CircuitPython", os.uname().release, "| reset reason", microcontroller.cpu.reset_reason)
try:
    src = open("/code.py").read(6000)
    i = src.find("CODE_VERSION")
    print("code.py:", src[i:i + 40].split("\n")[0] if i >= 0 else "CODE_VERSION not found in first 6 KB")
except Exception as e:
    print("code.py unreadable:", e)
try:
    import noknok
    print("noknok.py __version__", noknok.__version__)
except Exception as e:
    print("noknok import failed:", repr(e))

i2c = busio.I2C(board.GP11, board.GP10, frequency=100000)
while not i2c.try_lock():
    pass

def crc8(d):
    c = 0
    for b in d:
        c ^= b
        for _ in range(8):
            c = ((c << 1) ^ 0x07) & 0xFF if c & 0x80 else (c << 1) & 0xFF
    return c

found = None
for a in range(0x08, 0x78):
    try:
        i2c.writeto(a, bytes([0x10]))
        b = bytearray(20)
        i2c.readfrom_into(a, b)
        if b[0] == 1 and crc8(b[:19]) == b[19]:
            found = a
            st = b
            break
    except OSError:
        pass
print("scan: power manager at", hex(found) if found else "NOT FOUND")
if found:
    i2c.writeto(found, bytes([0xB1]))
    v = bytearray(4)
    i2c.readfrom_into(found, v)
    print("PicoHub power manager firmware %d.%d.%d (protocol %d)" % (v[1], v[2], v[3], v[0]))
    u16 = lambda i: st[i] | (st[i + 1] << 8)
    t = u16(12)
    t = t - 65536 if t & 0x8000 else t
    print("status: pd_state %d contract %d mV / %d mA, vin %d mV, iin %d mA, v5 %d mV, TH1 %.1f C, rails 0x%02x, faults 0x%02x, notices 0x%02x, reset cause %d"
          % (st[1], u16(2), u16(4), u16(6), u16(8), u16(10), t / 10, st[14], st[16], st[17], st[18]))
# every other module on bus A, for the record
others = []
for a in range(0x08, 0x78):
    if a == found:
        continue
    try:
        i2c.writeto(a, b"")
        others.append(hex(a))
    except OSError:
        pass
print("other devices on bus A:", others if others else "none")
i2c.unlock()
