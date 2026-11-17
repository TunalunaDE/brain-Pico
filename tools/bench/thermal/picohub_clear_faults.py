# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# Run on the rig Pico (pico.py run): clear the PicoHub's latched faults and release the minimum input voltage.
import time, board, busio
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
def status(a):
    try:
        i2c.writeto(a, bytes([0x10])); b = bytearray(20); i2c.readfrom_into(a, b)
        return b if b[0] == 1 and crc8(b[:19]) == b[19] else None
    except OSError:
        return None
addr = None
for a in range(0x08, 0x78):
    if status(a):
        addr = a
        break
if addr is None:
    try:
        b = bytearray(10); i2c.readfrom_into(0x7F, b)
        if b[8] == 0x07 and crc8(b[:9]) == b[9]:
            i2c.writeto(0x7F, bytes([0x1D, 0x60])); addr = 0x60; time.sleep(0.2)
    except OSError:
        pass
print("power manager at", hex(addr) if addr else "NOT FOUND")
if addr:
    s = status(addr); print("before: faults 0x%02x notices 0x%02x inputs 0x%02x" % (s[16], s[17], s[15]))
    i2c.writeto(addr, bytes([0x12])); time.sleep(0.2)
    i2c.writeto(addr, bytes([0x23, 0])); time.sleep(0.3)
    s = status(addr); print("after:  faults 0x%02x notices 0x%02x inputs 0x%02x, contract %d mV" % (s[16], s[17], s[15], s[2] | (s[3] << 8)))
i2c.unlock()
