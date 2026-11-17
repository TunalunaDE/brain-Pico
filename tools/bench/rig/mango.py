#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# mango.py - WiFi-degradation profiles on the GL.iNet Mango 2 (GL-MG1300) test router (DEV-242).
# The brain under test joins the Mango's own 2.4 GHz SSID; this script changes how good that link is.
#
#   python3 mango.py check                 what the router can do (iw, tc, netem, tbf, iface, tx power)
#   python3 mango.py set PROFILE [--for S] apply a profile (with --for: restore to "good" after S seconds,
#                                          done BY THE ROUTER, so it also happens if this host dies)
#   python3 mango.py restore               back to "good" (full TX power, no qdisc, WiFi up)
#   python3 mango.py show                  current TX power + qdisc on the AP interface
#
# Profiles (tune with env MANGO_WEAK_DBM etc.; nothing here is proven on the real Mango yet):
#   good    full TX power (20 dBm), no shaping                       = default / restore
#   weak    TX power MANGO_WEAK_DBM (default 3 dBm): low signal at the brain (RSSI depends on distance)
#   slow    tbf 256 kbit/s on the AP interface (towards the brain)
#   lossy   netem delay 200 ms +-50 ms, loss 10 %
#   flaky   netem loss 30 %, delay 50 ms
#   down    WiFi radio off (router outage; use with --for, e.g. DEV-79 router-off tests)
#
# Access: SSH as root with a KEY only (BatchMode; never a password from a script). Christopher adds the
# bench host's public key to the Mango once (System > Admin or /etc/dropbear/authorized_keys).
# Host: MANGO_HOST (default 192.168.8.1 = the Mango's own LAN; on the home LAN use its DHCP address,
# found by MAC, see tools.md). Nothing secret is stored here.
# Shaping only acts on traffic the router sends to the brain (egress of the AP interface). That is
# enough to degrade TCP both ways (ACKs), but an upload-only shaping needs an ifb (not built).
import json, os, shlex, subprocess, sys

HOST = os.environ.get("MANGO_HOST", "192.168.8.1")
USER = os.environ.get("MANGO_USER", "root")
WEAK_DBM = int(os.environ.get("MANGO_WEAK_DBM", "3"))
FULL_DBM = int(os.environ.get("MANGO_FULL_DBM", "20"))


def sh(cmd, timeout=20):
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new",
                        "%s@%s" % (USER, HOST), cmd], capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def ap_iface():
    rc, out = sh("iw dev | awk '/Interface/{i=$2} /type AP/{print i; exit}'")
    if rc or not out:
        raise RuntimeError("no AP interface found on the Mango (rc=%s): %s" % (rc, out))
    return out.splitlines()[0]


def check():
    rep = {"host": HOST}
    rc, out = sh("cat /etc/glversion 2>/dev/null; cat /etc/openwrt_release 2>/dev/null | grep DISTRIB_RELEASE; uname -r")
    rep["reachable"] = rc == 0
    if rc:
        rep["error"] = out
        return rep
    rep["firmware"] = out.replace("\n", " | ")
    for tool in ("iw", "tc", "wifi", "uci"):
        rep["has_" + tool] = sh("command -v %s" % tool)[0] == 0
    rep["netem"] = sh("tc qdisc add dev lo root netem delay 1ms && tc qdisc del dev lo root")[0] == 0
    rep["tbf"] = sh("tc qdisc add dev lo root tbf rate 1mbit burst 10k latency 50ms && tc qdisc del dev lo root")[0] == 0
    try:
        i = ap_iface()
        rep["ap_iface"] = i
        rep["txpower"] = sh("iw dev %s info | grep -i txpower" % i)[1]
        rep["txpower_settable"] = sh("iw dev %s set txpower fixed %d && iw dev %s set txpower fixed %d"
                                     % (i, WEAK_DBM * 100, i, FULL_DBM * 100))[0] == 0
    except Exception as e:
        rep["ap_iface"] = "ERROR %s" % e
    missing = [k for k in ("has_iw", "has_tc", "netem", "tbf", "txpower_settable") if not rep.get(k)]
    rep["cannot"] = missing          # e.g. netem missing -> opkg install tc kmod-netem (needs internet on the Mango)
    return rep


def _cmds(profile, i):
    clear = "tc qdisc del dev %s root 2>/dev/null; " % i
    full = "iw dev %s set txpower fixed %d; " % (i, FULL_DBM * 100)
    return {
        "good":  "wifi up 2>/dev/null; " + clear + full,
        "weak":  clear + "iw dev %s set txpower fixed %d" % (i, WEAK_DBM * 100),
        "slow":  full + clear + "tc qdisc add dev %s root tbf rate 256kbit burst 16k latency 400ms" % i,
        "lossy": full + clear + "tc qdisc add dev %s root netem delay 200ms 50ms loss 10%%" % i,
        "flaky": full + clear + "tc qdisc add dev %s root netem delay 50ms loss 30%%" % i,
        "down":  clear + "wifi down",
    }[profile]


def set_profile(profile, for_s=None):
    i = ap_iface()
    cmd = _cmds(profile, i)
    if for_s:   # the router restores itself: survives a dead bench host / harness
        cmd += "; (sleep %d; %s) >/dev/null 2>&1 &" % (int(for_s), _cmds("good", i))
        cmd = "sh -c %s" % shlex.quote(cmd)
    rc, out = sh(cmd)
    if rc:
        raise RuntimeError("profile %s failed (rc=%s): %s" % (profile, rc, out))
    return show() if profile != "down" else {"profile": "down", "iface": i}


def restore():
    return set_profile("good")


def show():
    i = ap_iface()
    return {"iface": i, "txpower": sh("iw dev %s info | grep -i txpower" % i)[1],
            "qdisc": sh("tc qdisc show dev %s" % i)[1]}


def ensure_restored():
    try:
        return restore()
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if not a or a[0] == "check":
            print(json.dumps(check(), indent=1))
        elif a[0] == "set" and len(a) > 1:
            f = int(a[a.index("--for") + 1]) if "--for" in a else None
            print(json.dumps(set_profile(a[1], f)))
        elif a[0] == "restore":
            print(json.dumps(restore()))
        elif a[0] == "show":
            print(json.dumps(show()))
        else:
            print("usage: mango.py check | set good|weak|slow|lossy|flaky|down [--for S] | restore | show")
            sys.exit(1)
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(2)
