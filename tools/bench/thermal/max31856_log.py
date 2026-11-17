#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""MAX31856 thermocouple logger for the Raspberry Pi bench hosts (kernel SPI via spidev).

Setup (Pi4RFID, 9 Nov 2026): enable SPI0 with two chip selects without a reboot:
    sudo dtoverlay spi0-2cs        (undo: sudo dtoverlay -r spi0-2cs)
Wiring (40-pin header): VIN 5 V (pin 2) or 3.3 V (pin 17), GND pin 25, SCK pin 23, SDO pin 21 (MISO),
SDI pin 19 (MOSI), CS pin 24 (CE0 = /dev/spidev0.0) and pin 26 (CE1 = /dev/spidev0.1).
Board pins: VIN 3Vo GND SCK SDO SDI CS FLT DRDY (leave 3Vo, FLT, DRDY open).  K-type probe: red T+, black T- (the
magnetic leg is T-).  A bad solder joint on any of the signal pins gives garbage or a dead chip: the
first two bench boards did exactly that, so every sample is integrity-checked.

Integrity check: each sample is a 16-register burst from address 0. The ten registers CR0..CJTO never change on
their own (81 03 ff 7f c0 7f ff 80 00 00 after start); a burst that differs is rejected and counted, never
logged as a temperature.

Usage: max31856_log.py [seconds_between_samples=10] [number_of_samples=0 (forever)] [bus.dev ...]  (default 0.0)
Line:  <t> s  <name>: probe 21.23 C, board 26.42 C (rejected: 0)   [FAULT 0x40 = out of range, 0x01 = open ...]
"""
import sys
import time
import spidev

EXPECT = [0x81, 0x03, 0xFF, 0x7F, 0xC0, 0x7F, 0xFF, 0x80, 0x00, 0x00]


class Chip:
    def __init__(self, bus, dev):
        self.name = "spi%d.%d" % (bus, dev)
        self.sp = spidev.SpiDev()
        self.sp.open(bus, dev)
        self.sp.max_speed_hz = 500000
        self.sp.mode = 1

    def read(self, reg, n):
        return self.sp.xfer2([reg & 0x7F] + [0] * n)[1:]

    def write(self, reg, val):
        self.sp.xfer2([reg | 0x80, val])

    def start(self):
        """True if a MAX31856 answers (power-up values) and accepts a write; then K type, auto conversion, 50 Hz."""
        if self.read(0x02, 3) != [0xFF, 0x7F, 0xC0]:
            return False
        self.write(0x01, 0x03)                       # CR1: K type, 1 sample
        self.write(0x00, 0x81)                       # CR0: automatic conversion, 50 Hz filter
        if self.read(0x00, 2) != [0x81, 0x03]:       # the write must have arrived
            return False
        time.sleep(0.5)
        return True

    def sample(self):
        """(probe C, board C, fault byte) or None when the integrity check fails."""
        raw = self.read(0x00, 16)
        if raw[:10] != EXPECT:
            return None
        cj = ((raw[0x0A] << 8) | raw[0x0B]) >> 2
        if cj & 0x2000:
            cj -= 0x4000
        tc = ((raw[0x0C] << 16) | (raw[0x0D] << 8) | raw[0x0E]) >> 5
        if tc & 0x40000:
            tc -= 0x80000
        return tc * 0.0078125, cj / 64.0, raw[0x0F]


def main():
    every = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    specs = sys.argv[3:] or ["0.0"]
    chips = []
    for s in specs:
        b, d = s.split(".")
        c = Chip(int(b), int(d))
        if c.start():
            chips.append(c)
        else:
            print("no working MAX31856 on %s - skipped" % c.name)
    if not chips:
        sys.exit("no board found")
    rejected = dict.fromkeys(range(len(chips)), 0)
    t0 = time.time()
    i = 0
    while count == 0 or i < count:
        line = "%7.0f s" % (time.time() - t0)
        for k, c in enumerate(chips):
            s = c.sample()
            if s is None:
                rejected[k] += 1
                line += "  %s: REJECTED (integrity check)" % c.name
            else:
                line += "  %s: probe %.2f C, board %.2f C" % (c.name, s[0], s[1])
                if s[2]:
                    line += ", FAULT 0x%02x" % s[2]
            line += " (rejected: %d)" % rejected[k]
        print(line, flush=True)
        i += 1
        time.sleep(every)


if __name__ == "__main__":
    main()
