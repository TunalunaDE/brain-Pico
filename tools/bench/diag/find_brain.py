# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# find_brain.py NAME_PART - host: sweep 192.168.1.0/24 with /rpc hello and print the brain whose name contains NAME_PART (IPs move, DHCP not reserved).
import socket, json, sys, concurrent.futures as f
want = sys.argv[1].lower()
def t(i):
    ip = "192.168.1.%d" % i
    try:
        s = socket.create_connection((ip, 80), timeout=0.8); b = json.dumps({"id": 1, "op": "hello", "args": {}}).encode()
        s.sendall(b"POST /rpc HTTP/1.1\r\nHost: x\r\nConnection: close\r\nContent-Length: %d\r\n\r\n" % len(b) + b); s.settimeout(4); d = b""
        while True:
            c = s.recv(4096)
            if not c: break
            d += c
        j = json.loads(d.split(b"\r\n\r\n", 1)[1]); dev = str(j.get("device", "")); return "%s %s" % (ip, dev) if want in dev.lower() else None
    except Exception: return None
with f.ThreadPoolExecutor(60) as ex:
    for r in ex.map(t, range(2, 255)):
        if r: print(r)
