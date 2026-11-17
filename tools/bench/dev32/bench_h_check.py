# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# Hardening test part 3 readout: events tail, log.txt size + what kinds of
# lines were appended (only RING FLUSH blocks expected), product.py identity,
# strike count.
import os, microcontroller
e = open("noknok_events.txt").read().split("\n")
print("=== events (tail) ===")
print("\n".join(l for l in e[-9:] if l))
print("=== log.txt ===")
print("size now:", os.stat("log.txt")[6])
d = open("log.txt").read().split("\n")
flushes = [l for l in d if "RING FLUSH" in l]
boots   = [l for l in d if "===== BOOT =====" in l]
print("RING FLUSH blocks in file:", len(flushes), "| last:", flushes[-1] if flushes else None)
print("BOOT separators in file:", len(boots), "| last:", boots[-1] if boots else None)
print("=== product.py ===")
p = open("product.py").read()
print("first line:", p.split("\n")[0][:70])
print("is whack_a_mole:", "hack-a-Mole" in p or "whack" in p.lower())
print("strike byte: 0x%02x" % microcontroller.nvm[0])
