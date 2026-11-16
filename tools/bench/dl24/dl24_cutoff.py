# SPDX-License-Identifier: MIT
import os, select, struct, sys, time
fd = os.open("/dev/hidraw0", os.O_RDWR)
volts = float(sys.argv[1])
os.write(fd, b"\x00" + (bytes([0x55, 0x05, 0x01, 0x29]) + struct.pack(">f", volts) + bytes([0xEE, 0xFF])).ljust(64, b"\0")); time.sleep(0.5)
while select.select([fd], [], [], 0)[0]: os.read(fd, 64)
os.write(fd, b"\x00" + bytes([0x55, 5, 1, 3, 0, 0, 0, 0, 0xEE, 0xFF]).ljust(64, b"\0"))
t0 = time.time()
while time.time() - t0 < 0.8:
    if select.select([fd], [], [], 0.05)[0]:
        r = os.read(fd, 64)
        if r[0] == 0xAA and r[3] == 3:
            print("D_Cutoff now %.2f V" % struct.unpack(">f", r[20:24])[0]); break
