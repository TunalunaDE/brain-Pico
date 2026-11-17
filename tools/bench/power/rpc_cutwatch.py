# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# rpc_cutwatch.py IP SECONDS [STATUS_AFTER_S] - DEV-169: after a brain reset, hello every 1 s (status every 5 s); logs cut replies and whether ping answers. Host.
# cutwatch.py IP SECONDS - after a brain reset: hello every 1 s, status every 5 s; logs when
# replies start arriving cut (header only / no FIN) and whether ping still answers.
import json, socket, subprocess, sys, time
IP, DUR = sys.argv[1], float(sys.argv[2])
STAT_AT = float(sys.argv[3]) if len(sys.argv) > 3 else 1e9
T00 = time.time()
OPS = lambda n: "status" if time.time() - T00 > STAT_AT and n % 5 == 0 else "hello"


def call(op):
    b = json.dumps({"id": 1, "op": op, "args": {}}).encode()
    try:
        c = socket.create_connection((IP, 80), timeout=4)
        c.sendall(b"POST /rpc HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
                  b"Content-Length: %d\r\n\r\n" % len(b) + b)
        d = b""
        while True:
            x = c.recv(4096)
            if not x:
                break
            d += x
        c.close()
    except Exception as e:
        return "ERR " + type(e).__name__ + (" hdr" if 'd' in dir() and d else "")
    head, _, body = d.partition(b"\r\n\r\n")
    want = int(head.lower().split(b"content-length:")[1].split(b"\r\n")[0]) if b"content-length" in head.lower() else -1
    return "ok" if len(body) == want else "CUT %d/%d" % (len(body), want)


ping = lambda: subprocess.run(["ping", "-c", "1", "-W", "1", IP], capture_output=True).returncode == 0
t0 = time.time()
up = None
last = None
bad = 0
n = 0
while time.time() - t0 < DUR:
    r = call(OPS(n))
    n += 1
    if up is None:
        if r == "ok":
            up = time.time() - t0
            print("%6.1f first ok" % up, flush=True)
        time.sleep(2)
        continue
    st = r.split()[0]
    if st != last:
        print("%6.1f %s (ping %s)" % (time.time() - t0, r, ping()), flush=True)
        last = st
    bad += r != "ok"
    time.sleep(1)
if up is not None and (last == "ok" or last is None):
    st = call("status")
print("done: calls %d bad %d, final %s" % (n, bad, last), flush=True)
