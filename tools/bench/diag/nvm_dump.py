# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# nvm_dump.py - Pico (pico.py run), read-only: crash counter nvm[0], OTA timestamp nvm[1:5], Store area summary. Never writes.
import microcontroller as mc
n = mc.nvm
print("nvm len:", len(n))
print("nvm[0] =", hex(n[0]), " (0xC0|n = crash counter)")
print("nvm[1:8] =", [hex(b) for b in n[1:8]])
# Store record area 64..~1024 - read only, never write
blk = bytes(n[64:128])
print("store[64:128] =", blk)
tail = bytes(n[3900:4000]) if len(n) >= 4000 else b""
print("notes[3900:] =", tail)
import supervisor
print("run reason:", supervisor.runtime.run_reason)
print("safe mode reason:", supervisor.runtime.safe_mode_reason)
import microcontroller
print("reset reason:", microcontroller.cpu.reset_reason)
import storage
try:
    storage.remount("/", False)
    print("FS: writable by program (remount rw OK)")
    storage.remount("/", True)
except Exception as e:
    print("FS: read-only to program ->", type(e).__name__, e)
