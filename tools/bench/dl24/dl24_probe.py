#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# READ-ONLY probe of an Atorch DL24 (USB HID 0483:5750, firmware V1.1.0). Sends only commands 03 and 05.
# Protocol source: PROTOCOL.md of github.com/sophusand/atorch-dl24p-python (captured from the official app).
import os, select, struct, sys, time

DEV = sys.argv[1] if len(sys.argv) > 1 else "/dev/hidraw0"
fd = os.open(DEV, os.O_RDWR)

def request(cmd, wait=0.5):
    frame = bytes([0x55, 0x05, 0x01, cmd, 0, 0, 0, 0, 0xEE, 0xFF]).ljust(64, b"\x00")
    while select.select([fd], [], [], 0)[0]:          # drop stale replies
        os.read(fd, 64)
    os.write(fd, b"\x00" + frame)                     # leading 0 = "no report id"
    t0 = time.time()
    while time.time() - t0 < wait:
        if select.select([fd], [], [], 0.05)[0]:
            return os.read(fd, 64)
    return None

r = request(0x03)
print("settings reply:", None if r is None else r[:56].hex(" "))
if r and r[0] == 0xAA:
    f = lambda o: struct.unpack(">f", r[o:o + 4])[0]
    print("  set point %.3f | D_Cutoff %.2f V | over-current %.2f A | over-power %.1f W | ext temp limit %.1f C | MOSFET limit %.1f C | mode %s"
          % (f(4), f(20), f(32), f(36), f(40), f(44), ["CC", "CV", "CR", "CP"][r[48]] if r[48] < 4 else r[48]))
for i in range(3):
    r = request(0x05)
    print("measurement reply:", None if r is None else r[:62].hex(" "))
    if r and r[0] == 0xAA:
        w = struct.unpack("<14I", r[4:60])
        st = struct.unpack("<H", r[60:62])[0]
        print("  V %.3f  I %.3f A  P %.3f W  energy %.3f Wh  CPU %.1f C  MOSFET %.1f C  fan %.0f  load_on %d  status 0x%02x"
              % (w[1] / 1000, w[2] / 1000, w[3] / 1000, w[5] / 1000, w[7] / 1000, w[9] / 1000, w[10] / 1000, w[12], st))
    time.sleep(0.4)
os.close(fd)
