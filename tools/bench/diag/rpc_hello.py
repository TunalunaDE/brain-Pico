# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# rpc_hello.py IP - host: one raw /rpc hello over a plain socket, prints the reply (no dependencies).
import json, socket, sys
b = json.dumps({"id": 1, "op": "hello", "args": {}}).encode()
c = socket.create_connection((sys.argv[1], 80), timeout=5)
c.sendall(b"POST /rpc HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\nContent-Length: %d\r\n\r\n" % len(b) + b)
d = b""
while True:
    x = c.recv(4096)
    if not x: break
    d += x
print(d.split(b"\r\n\r\n", 1)[1].decode()[:400])
