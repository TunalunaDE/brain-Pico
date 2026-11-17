# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# i2c_scan_pins.py - Pico (pico.py run): I2C scan on every common SDA/SCL pair (GP8/9, 10/11, 18/19, 20/21, 4/5, 0/1). Finds a module on an unknown bus.
import board, busio, time
pairs=[("GP8","GP9"),("GP10","GP11"),("GP18","GP19"),("GP20","GP21"),("GP4","GP5"),("GP0","GP1")]
for sda,scl in pairs:
    try:
        i2c=busio.I2C(getattr(board,scl),getattr(board,sda),frequency=100000)
    except Exception as e:
        print(sda,scl,"open fail",e); continue
    while not i2c.try_lock(): pass
    try:
        found=[hex(a) for a in i2c.scan()]
        extra=[]
        for a in (0x7e,0x7f):
            for _ in range(20):
                try:
                    b=bytearray(10); i2c.readfrom_into(a,b); extra.append((hex(a),bytes(b).hex())); break
                except OSError: time.sleep(0.05)
        print(sda,scl,found,extra)
    finally:
        i2c.unlock(); i2c.deinit()