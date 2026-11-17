#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# mango.py - WiFi-degradation profiles on the GL.iNet Mango 2 (GL-MG1300) test router (DEV-242).
# The brain under test joins the Mango's own 2.4 GHz test SSID; this script changes how good that link is.
# Site facts (address, SSID, access, known state, reservation rules) live in the private bench notes,
# section "GL.iNet Mango 2"; nothing secret is stored here.
#
#   python3 mango.py check                       what the router can do (iw, tc, netem, tbf, AP iface, tx power)
#   python3 mango.py show                        TX power + qdisc + a KNOWN-STATE verdict (exit 0 = known state)
#   python3 mango.py reserve --owner NAME --minutes N [--what TEXT]   take the router-side lock (max 12 h)
#   python3 mango.py release [--owner NAME]      give it back (only the owner, or an expired lock)
#   python3 mango.py set PROFILE [--for S]       apply a profile; needs the lock (MANGO_OWNER = lock owner).
#                                                --for S: the ROUTER restores itself after S s (survives a dead host)
#   python3 mango.py restore                     back to "good" and prove it with show (needs the lock)
#
# Profiles (nothing guarantees a given RSSI: read status.link.rssi on the brain and record it):
#   good    AP radio up, TX power automatic (regulatory maximum), no qdisc         = known state / restore
#   weak    TX power MANGO_WEAK_DBM (default 3 dBm)
#   slow    tbf 256 kbit/s on the AP interface (towards the brain)
#   lossy   netem delay 200 ms +-50 ms, loss 10 %
#   flaky   netem delay 50 ms, loss 30 %
#   down    the test radio only (MANGO_AP_RADIO, default radio0) off: router outage for the brain.
#           The uplink radio (repeater station) is never touched.
#
# Lock: `mkdir /tmp/mango.lock` on the ROUTER (atomic, works across hosts and agents) + an owner file
# "OWNER since EPOCH until EPOCH WHAT". A reboot of the router clears the lock AND the profile (safe).
# Access: SSH as root with a KEY only (BatchMode; never a password). Env: MANGO_HOST (default 192.168.8.1),
# MANGO_USER (root), MANGO_SSID (Agent24Ghz), MANGO_AP_RADIO (radio0), MANGO_OWNER, MANGO_WEAK_DBM.
# Shaping only acts on traffic the router sends to the brain (egress of the AP interface).
import json, os, shlex, subprocess, sys, time

HOST = os.environ.get("MANGO_HOST", "192.168.8.1")
USER = os.environ.get("MANGO_USER", "root")
SSID = os.environ.get("MANGO_SSID", "Agent24Ghz")
AP_RADIO = os.environ.get("MANGO_AP_RADIO", "radio0")
WEAK_DBM = int(os.environ.get("MANGO_WEAK_DBM", "3"))
MIN_GOOD_DBM = 15          # "good" = automatic power; the 2.4 GHz radio reports ~17 dBm there
LOCKDIR = "/tmp/mango.lock"
MAX_LOCK_MIN = 12 * 60


def sh(cmd, timeout=30):
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new",
                        "%s@%s" % (USER, HOST), cmd], capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def ap_iface():
    """The AP interface that serves the test SSID (never the uplink station)."""
    rc, out = sh("iw dev | awk '/Interface/{i=$2} /ssid/{s=$2} /type AP/{print i\" \"s}'")
    if rc:
        raise RuntimeError("iw failed on the Mango (rc=%s): %s" % (rc, out))
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == SSID:
            return parts[0]
    raise RuntimeError("no AP interface with SSID %s on the Mango (is the test radio down?): %r" % (SSID, out))


# -- lock --------------------------------------------------------------------------------------------
def lock_info():
    rc, out = sh("cat %s/owner 2>/dev/null; echo NOW $(date +%%s)" % LOCKDIR)
    now, info = None, None
    for line in out.splitlines():
        if line.startswith("NOW "):
            now = int(line.split()[1])
        elif line.strip():
            p = line.split(None, 5)       # OWNER since EPOCH until EPOCH WHAT
            info = {"owner": p[0], "since": int(p[2]), "until": int(p[4]), "what": p[5] if len(p) > 5 else ""}
    if info:
        info["expired"] = now is not None and now >= info["until"]
    return info


def reserve(owner, minutes, what="-"):
    minutes = max(1, min(int(minutes), MAX_LOCK_MIN))
    owner = owner.replace(" ", "_")
    cur = lock_info()
    if cur and cur["owner"] == owner and not cur["expired"]:
        pass                                            # renew our own lock
    elif cur and not cur["expired"]:
        raise RuntimeError("Mango reserved by %s until %s (%s)" % (cur["owner"], time.strftime("%F %T", time.localtime(cur["until"])), cur["what"]))
    elif cur and cur["expired"]:
        if not show()["known_state"]:
            raise RuntimeError("expired lock of %s, but the router is NOT in its known state: restore it by hand first" % cur["owner"])
        sh("rm -rf %s" % LOCKDIR)
    cmd = ("(mkdir %s 2>/dev/null || [ -n \"$RENEW\" ]) && now=$(date +%%s) && "
           "echo \"%s since $now until $((now + %d)) %s\" > %s/owner && cat %s/owner"
           % (LOCKDIR, owner, minutes * 60, what.replace('"', "'").replace("$", ""), LOCKDIR, LOCKDIR))
    if cur and cur["owner"] == owner and not cur["expired"]:
        cmd = "RENEW=1; " + cmd
    rc, out = sh(cmd)
    if rc:
        raise RuntimeError("could not take the Mango lock (someone was faster?): %s" % out)
    return lock_info()


def release(owner=None):
    owner = (owner or os.environ.get("MANGO_OWNER", "")).replace(" ", "_")
    cur = lock_info()
    if not cur:
        return {"released": False, "why": "no lock"}
    if cur["owner"] != owner and not cur["expired"]:
        raise RuntimeError("lock belongs to %s, not %s" % (cur["owner"], owner or "(MANGO_OWNER unset)"))
    sh("rm -rf %s" % LOCKDIR)
    return {"released": True, "was": cur}


def _need_lock():
    owner = os.environ.get("MANGO_OWNER", "").replace(" ", "_")
    cur = lock_info()
    if not cur or cur["expired"]:
        raise PermissionError("Mango not reserved: run `mango.py reserve --owner NAME --minutes N` and set MANGO_OWNER")
    if cur["owner"] != owner:
        raise PermissionError("Mango reserved by %s (MANGO_OWNER=%s)" % (cur["owner"], owner or "unset"))


# -- profiles ----------------------------------------------------------------------------------------
def _clear(i):
    return "tc qdisc del dev %s root 2>/dev/null; " % i


def _radio_up_if_down():
    # `wifi up` on a radio that is already up RESTARTS it (the AP interface is recreated, the brain drops off for
    # 10-20 s; seen 17 Nov 2026). So only when the test radio is really down.
    return ("[ \"$(ubus call network.wireless status | jsonfilter -e '@.%s.up')\" = true ] || "
            "{ wifi up %s; sleep 15; }; " % (AP_RADIO, AP_RADIO))


def _good(i):
    return _radio_up_if_down() + _clear(i) + "iw dev %s set txpower auto" % i


def _cmds(profile, i):
    return {
        "good":  _good(i),
        "weak":  _clear(i) + "iw dev %s set txpower fixed %d" % (i, WEAK_DBM * 100),
        "slow":  _clear(i) + "iw dev %s set txpower auto; tc qdisc add dev %s root tbf rate 256kbit burst 16k latency 400ms" % (i, i),
        "lossy": _clear(i) + "iw dev %s set txpower auto; tc qdisc add dev %s root netem delay 200ms 50ms loss 10%%" % (i, i),
        "flaky": _clear(i) + "iw dev %s set txpower auto; tc qdisc add dev %s root netem delay 50ms loss 30%%" % (i, i),
        "down":  _clear(i) + "wifi down %s" % AP_RADIO,
    }[profile]


def set_profile(profile, for_s=None):
    _need_lock()
    i = ap_iface()
    cmd = _cmds(profile, i)
    if for_s:   # the router restores itself: survives a dead bench host / harness
        cmd += "; (sleep %d; %s) >/dev/null 2>&1 &" % (int(for_s), _good(i))
    rc, out = sh("sh -c %s" % shlex.quote(cmd), timeout=60)
    if rc:
        raise RuntimeError("profile %s failed (rc=%s): %s" % (profile, rc, out))
    if profile == "down":
        return {"profile": "down", "radio": AP_RADIO, "restores_after_s": for_s}
    return dict(show(), profile=profile, restores_after_s=for_s)


def restore():
    _need_lock()
    i = None
    try:
        i = ap_iface()
    except RuntimeError:          # test radio down: bring it up first, then find the interface
        sh("sh -c %s" % shlex.quote(_radio_up_if_down()), timeout=60)
        i = _wait_iface(40)
    sh("sh -c %s" % shlex.quote(_good(i)), timeout=60)
    for _ in range(8):                  # the AP can take a few seconds to settle
        s = show()
        if s["known_state"]:
            break
        time.sleep(5)
    if not s["known_state"]:
        raise RuntimeError("restore did not reach the known state: %s" % s["problems"])
    return s


def _wait_iface(secs):
    end = time.time() + secs
    while True:
        try:
            return ap_iface()
        except RuntimeError:
            if time.time() > end:
                raise
            time.sleep(3)


def show():
    s = {"host": HOST, "ssid": SSID, "problems": []}
    try:
        i = ap_iface()
    except RuntimeError as e:
        s["problems"].append(str(e))
        s["known_state"] = False
        return s
    s["iface"] = i
    txp = sh("iw dev %s info | grep -i txpower" % i)[1]
    s["txpower"] = txp
    try:
        dbm = float(txp.split()[1])
        if dbm < MIN_GOOD_DBM:
            s["problems"].append("tx power %.1f dBm below %d" % (dbm, MIN_GOOD_DBM))
    except (IndexError, ValueError):
        s["problems"].append("tx power unreadable: %r" % txp)
    q = sh("tc qdisc show dev %s" % i)[1]
    s["qdisc"] = q
    if "netem" in q or "tbf" in q:
        s["problems"].append("shaping qdisc present")
    s["lock"] = lock_info()
    s["known_state"] = not s["problems"]
    return s


def check():
    rep = {"host": HOST}
    rc, out = sh("cat /etc/glversion 2>/dev/null; grep DISTRIB_RELEASE /etc/openwrt_release 2>/dev/null; uname -r")
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
        rep["ap_iface"] = ap_iface()
    except Exception as e:
        rep["ap_iface"] = "ERROR %s" % e
    rep["cannot"] = [k for k in ("has_iw", "has_tc", "netem", "tbf") if not rep.get(k)]
    rep["show"] = show()
    return rep


def ensure_restored():
    try:
        return restore()
    except Exception as e:
        return {"error": str(e)}


def _arg(a, name, default=None):
    return a[a.index(name) + 1] if name in a else default


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if not a or a[0] == "check":
            print(json.dumps(check(), indent=1))
        elif a[0] == "show":
            s = show()
            print(json.dumps(s, indent=1))
            sys.exit(0 if s["known_state"] else 4)
        elif a[0] == "reserve":
            print(json.dumps(reserve(_arg(a, "--owner") or os.environ["MANGO_OWNER"], _arg(a, "--minutes", "60"), _arg(a, "--what", "-"))))
        elif a[0] == "release":
            print(json.dumps(release(_arg(a, "--owner"))))
        elif a[0] == "set" and len(a) > 1:
            f = _arg(a, "--for")
            print(json.dumps(set_profile(a[1], int(f) if f else None)))
        elif a[0] == "restore":
            print(json.dumps(restore()))
        else:
            print("usage: mango.py check | show | reserve --owner N --minutes M | release | set PROFILE [--for S] | restore")
            sys.exit(1)
    except PermissionError as e:
        print("REFUSED:", e, file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(2)
