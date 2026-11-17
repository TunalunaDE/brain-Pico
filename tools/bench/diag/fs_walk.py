# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# fs_walk.py - Pico (pico.py run), read-only: list the filesystem 3 levels deep with sizes (spots FAT garbage after a power cut).
import os
def walk(p, d=0):
    if d > 3:
        return
    try:
        entries = sorted(os.listdir(p))
    except Exception as e:
        print("  " * d + p + " ERR " + str(e))
        return
    for name in entries:
        if name in (".Trash-1000", ".Trashes", ".fseventsd", "System Volume Information", "lib"):
            continue
        full = p + name if p.endswith("/") else p + "/" + name
        try:
            st = os.stat(full)
        except Exception as e:
            print("  " * d + name + " STATERR " + str(e))
            continue
        isdir = (st[0] & 0x4000) != 0
        if isdir:
            print("  " * d + name + "/")
            walk(full, d + 1)
        else:
            print("  " * d + name + "  " + str(st[6]) + " bytes  mtime=" + str(st[8]))
print("=== FS WALK ===")
walk("/")
print()
print("=== boot_out.txt ===")
try:
    print(open("/boot_out.txt").read())
except Exception as e:
    print("ERR", e)
print("=== noknok_state.json ===")
try:
    print(open("/noknok_state.json").read()[:3000])
except Exception as e:
    print("ERR", e)
