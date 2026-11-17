# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# gate_rpc_settings.py IP - host: settings.get of the product scope, change brightness, read back, restore (gate step "rpc").
import json,urllib.request,sys
IP=sys.argv[1]
def rpc(op,args=None):
    r=urllib.request.Request("http://%s/rpc"%IP,data=json.dumps({"id":1,"op":op,"args":args or {}}).encode(),headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r,timeout=20).read().decode())
g=rpc("settings.get",{"scope":"product"}); print("GET",json.dumps(g)[:400])
vals=g.get("values",{})
b=vals.get("brightness")
print("mixed (brightness+turbo):", rpc("settings.set",{"scope":"product","values":{"brightness":(b+1 if b is not None else 100),"turbo":True}}))
print("odd keys:", rpc("settings.set",{"scope":"product","values":{"":1,"__proto__":1,"x"*80:1,"turbo2":"a"}}))
print("brightness back:", rpc("settings.set",{"scope":"product","values":{"brightness":b}}))
print("GET after:", sorted(rpc("settings.get",{"scope":"product"}).get("values",{}).keys()))
