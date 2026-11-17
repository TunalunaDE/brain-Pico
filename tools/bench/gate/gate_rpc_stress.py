# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# gate_rpc_stress.py IP N - host: N /rpc hello requests split into headers + body with random gaps (the phone pattern, DEV-34).
import json,socket,time,random,sys,urllib.request
IP=sys.argv[1]; N=int(sys.argv[2])
def post(delay):
    body=json.dumps({"id":7,"op":"hello","args":{}}).encode()
    head=("POST /rpc HTTP/1.1\r\nHost: %s\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n"%(IP,len(body))).encode()
    s=socket.create_connection((IP,80),timeout=15)
    try:
        s.sendall(head); time.sleep(delay); s.sendall(body)
        d=b""
        while True:
            c=s.recv(4096)
            if not c: break
            d+=c
    finally: s.close()
    t=d.decode("utf8","replace")
    return json.loads(t.split("\r\n\r\n",1)[1]) if "\r\n\r\n" in t else {}
ok=bad=0; errs=[]
for i in range(N):
    dl=random.choice([0,0.05,0.2,0.5,0.9,1.2])
    try:
        r=post(dl)
        if r.get("ok") is True: ok+=1
        else: bad+=1; errs.append((dl,r))
    except Exception as e: bad+=1; errs.append((dl,repr(e)))
    time.sleep(0.5)
print("ok",ok,"bad",bad,errs[:5])
r=urllib.request.Request("http://%s/rpc"%IP,data=json.dumps({"id":1,"op":"status"}).encode(),headers={"Content-Type":"application/json"})
st=json.loads(urllib.request.urlopen(r,timeout=20).read().decode()); print("last_bad_request",st.get("last_bad_request"), "uptime?")
