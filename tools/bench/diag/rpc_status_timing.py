#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# status_probe.py IP N [load] - DEV-181: are `status` timeouts real? N status calls, 30 s
# client timeout, each timed in phases (connect / first byte / closed) with the reply
# size. With "load": hello 1/s + settings.get 3 s run in a second thread meanwhile.
import json, socket, sys, threading, time

IP, N = sys.argv[1], int(sys.argv[2])
LOAD = len(sys.argv) > 3 and sys.argv[3] == "load"
stop = False


def tcall(op, timeout=30):
    b = json.dumps({"id": 1, "op": op, "args": {}}).encode()
    t0 = time.time()
    r = {"op": op}
    try:
        c = socket.create_connection((IP, 80), timeout=timeout)
        r["conn"] = round((time.time() - t0) * 1000)
        c.sendall(b"POST /rpc HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
                  b"Content-Length: %d\r\n\r\n" % len(b) + b)
        d = c.recv(8192)
        r["first"] = round((time.time() - t0) * 1000)
        while True:
            x = c.recv(8192)
            if not x:
                break
            d += x
        c.close()
        r["done"] = round((time.time() - t0) * 1000)
        r["bytes"] = len(d)
        head, _, body = d.partition(b"\r\n\r\n")
        r["clen"] = next((int(l.split(b":")[1]) for l in head.split(b"\r\n")
                          if l.lower().startswith(b"content-length")), None)
        try:
            j = json.loads(body)
            r["ok"] = True
            r["link"] = j.get("link")
            r["alloc"], r["free"] = j.get("mem_alloc"), j.get("mem_free")
        except Exception:
            r["ok"] = False                  # cut or garbled reply
    except Exception as e:
        r["err"] = repr(e)[:50]
        r["done"] = round((time.time() - t0) * 1000)
    return r


def load():
    n = 0
    while not stop:
        tcall("hello", 4)
        n += 1
        if n % 3 == 0:
            tcall("settings.get", 4)
        time.sleep(1)


if LOAD:
    threading.Thread(target=load, daemon=True).start()
for i in range(N):
    r = tcall("status")
    r["i"], r["t"] = i, time.strftime("%H:%M:%S")
    print(json.dumps(r), flush=True)
    time.sleep(15)
stop = True
