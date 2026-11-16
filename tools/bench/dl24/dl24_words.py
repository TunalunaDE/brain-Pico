#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# READ-ONLY: print all 14 measurement words of an Atorch DL24 (cmd 05) a few times, and the settings (cmd 03) calibration/limits.
import os, select, struct, sys, time
fd = os.open(sys.argv[1] if len(sys.argv) > 1 else "/dev/hidraw0", os.O_RDWR)
def req(cmd):
    while select.select([fd], [], [], 0)[0]:
        os.read(fd, 64)
    os.write(fd, b"\x00" + bytes([0x55, 0x05, 0x01, cmd, 0, 0, 0, 0, 0xEE, 0xFF]).ljust(64, b"\0"))
    t0 = time.time()
    while time.time() - t0 < 0.6:
        if select.select([fd], [], [], 0.05)[0]:
            r = os.read(fd, 64)
            if r[0] == 0xAA and r[3] == cmd:
                return r
for i in range(int(sys.argv[2]) if len(sys.argv) > 2 else 6):
    r = req(0x05)
    w = struct.unpack("<14I", r[4:60])
    print("w1 V=%.3f  w7 CPU=%.1f  w8=%d  w9 FET=%.1f  w10=%d  w11=%d  w13=%d  status=0x%02x" % (w[1] / 1000, w[7] / 1000, w[8], w[9] / 1000, w[10], w[11], w[13], struct.unpack("<H", r[60:62])[0]), flush=True)
    time.sleep(1.5)
s = req(0x03)
print("ext temp calibration factor %.4f | ext over-temp limit %.1f C | MOSFET limit %.1f C" % (struct.unpack(">f", s[8:12])[0], struct.unpack(">f", s[40:44])[0], struct.unpack(">f", s[44:48])[0]))
