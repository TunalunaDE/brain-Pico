#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Set the Atorch DL24 over-current (cmd 2c) and over-power (cmd 2d) protections, then read them back (cmd 03).
# usage: dl24_protect.py <amps> <watts> [/dev/hidrawN]     Protocol: PROTOCOL.md of sophusand/atorch-dl24p-python.
import os, select, struct, sys, time
amps, watts = float(sys.argv[1]), float(sys.argv[2])
fd = os.open(sys.argv[3] if len(sys.argv) > 3 else "/dev/hidraw0", os.O_RDWR)

def send(cmd, data=b"\0\0\0\0"):
    os.write(fd, b"\x00" + (bytes([0x55, 0x05, 0x01, cmd]) + data + bytes([0xEE, 0xFF])).ljust(64, b"\0"))

def request(cmd):
    while select.select([fd], [], [], 0)[0]:
        os.read(fd, 64)
    send(cmd)
    t0 = time.time()
    while time.time() - t0 < 0.6:
        if select.select([fd], [], [], 0.05)[0]:
            return os.read(fd, 64)

def show(tag):
    r = request(0x03)
    f = lambda o: struct.unpack(">f", r[o:o + 4])[0]
    print("%s: over-current %.2f A, over-power %.1f W, load mode CC=%d" % (tag, f(32), f(36), r[48] == 0))

show("before")
send(0x2C, struct.pack(">f", amps)); time.sleep(0.3)
send(0x2D, struct.pack(">f", watts)); time.sleep(0.5)
show("after ")
os.close(fd)
