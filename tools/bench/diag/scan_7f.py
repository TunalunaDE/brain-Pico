# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# scan_7f.py - Pico (pico.py run): scan bus A (GP10/11) and probe 0x7F (unassigned) / 0x7E (parked bootloader).
import board, busio, time
i2c = busio.I2C(board.GP11, board.GP10, frequency=100000)
while not i2c.try_lock(): pass
seen = [hex(a) for a in i2c.scan()]
print("i2c scan:", seen)
for a in (0x7F, 0x7E):
    try:
        b = bytearray(10); i2c.readfrom_into(a, b); print(hex(a), "answers:", b.hex(" "))
    except OSError as e:
        print(hex(a), "no answer")
i2c.unlock()
