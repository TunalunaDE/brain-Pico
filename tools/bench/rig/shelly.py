#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# shelly.py - Shelly Plug M Gen3 control for bench scripts (DEV-242). Python 3 stdlib only, runs on the
# Pi rigs and agent-hq (port of the Windows helper ~/.claude/scripts/shelly.ps1).
#
#   python3 shelly.py status [Test1|Test2|Overall|MainSupply|all]      read-only, always allowed
#   python3 shelly.py cycle  Test1|Test2 [--seconds 3]                  power-pull, plug restores ITSELF
#   python3 shelly.py on|off Test1|Test2
#
# Safety, baked in:
#   * Only Testing Plug 1 / 2 can be switched. Overall Main Plug and Main Testing Power Supply feed the
#     agent box, the Pis, the scope: this script refuses to switch them (exit 3). Status is fine.
#   * `cycle` uses the plug's own timer (Switch.Set on=false toggle_after=N): the plug turns itself back
#     ON after N s even if this script, the harness or the host dies mid-cut.
#   * `off` also arms a toggle_after (default 600 s) so a forgotten OFF never lasts; --hold-forever
#     skips it (needs a reason; nobody else can restore it).
#   * Every switch reads `output` back and prints it; a mismatch is an error (exit 2).
# Plugs are identified by DEVICE ID (shellyplugmg3-<MAC>), never by IP: the IP is looked up, cached in
# ~/.cache/noknok_shelly.json, and the /24 is rescanned when the cached IP answers with another id.
# No password is set on the plugs (LAN only); if one is ever set, this needs digest auth (not built).
# Library use: import shelly; shelly.cycle("Test2", 5); shelly.status("Test2") -> dict
import concurrent.futures, json, os, sys, time, urllib.request

# Plug names -> device ids are SITE data, kept on each host, not in this public repo:
#   ~/.config/noknok/shelly.json  {"plugs": {"Test1": "shellyplugmg3-<mac>", ...}}  (ids: private bench notes)
# Only the names in SWITCHABLE can ever be switched, whatever the file says.
SWITCHABLE = {"Test1", "Test2"}
CONF = os.environ.get("SHELLY_CONF", os.path.expanduser("~/.config/noknok/shelly.json"))
try:
    PLUGS = json.load(open(CONF))["plugs"]
except Exception:
    PLUGS = {}
SUBNET = os.environ.get("SHELLY_SUBNET", "192.168.1")
CACHE = os.path.expanduser("~/.cache/noknok_shelly.json")


class ShellyError(Exception):
    pass


def _get(ip, path, timeout=3):
    with urllib.request.urlopen("http://%s%s" % (ip, path), timeout=timeout) as r:
        return json.loads(r.read().decode())


def _id_at(ip):
    try:
        return _get(ip, "/shelly", 1.5).get("id")
    except Exception:
        return None


def _load_cache():
    try:
        return json.load(open(CACHE))
    except Exception:
        return {}


def _save_cache(c):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(c, open(CACHE, "w"))


def ip_of(name):
    if name not in PLUGS:
        raise ShellyError("unknown plug %r (known in %s: %s)" % (name, CONF, ", ".join(PLUGS) or "none - create the file"))
    want, c = PLUGS[name], _load_cache()
    if c.get(want) and _id_at(c[want]) == want:
        return c[want]
    found = {}
    with concurrent.futures.ThreadPoolExecutor(64) as ex:  # rescan the /24 once, cache every plug seen
        for ip, i in zip((ip for ip in ["%s.%d" % (SUBNET, n) for n in range(1, 255)]),
                         ex.map(_id_at, ["%s.%d" % (SUBNET, n) for n in range(1, 255)])):
            if i and i.startswith("shellyplug"):
                found[i] = ip
    c.update(found)
    _save_cache(c)
    if want not in found:
        raise ShellyError("plug %s (%s) not found on %s.0/24" % (name, want, SUBNET))
    return found[want]


def status(name):
    ip = ip_of(name)
    s = _get(ip, "/rpc/Switch.GetStatus?id=0")
    return {"plug": name, "ip": ip, "output": s.get("output"), "apower_w": s.get("apower"),
            "current_a": s.get("current"), "voltage_v": s.get("voltage"),
            "timer": s.get("timer_duration"), "t": time.strftime("%F %T")}


def _guard(name):
    if name not in SWITCHABLE:
        raise PermissionError("refused: %s may only be switched by Christopher (agents: Test1/Test2 only)" % name)


def _set(name, on, toggle_after=None):
    _guard(name)
    ip = ip_of(name)
    q = "/rpc/Switch.Set?id=0&on=%s" % ("true" if on else "false")
    if toggle_after:
        q += "&toggle_after=%d" % int(toggle_after)
    _get(ip, q)
    time.sleep(0.3)
    s = status(name)
    if s["output"] is not on:
        raise ShellyError("%s: asked %s, read back output=%s" % (name, on, s["output"]))
    return s


def on(name):
    return _set(name, True)


def off(name, auto_on_after=600):
    return _set(name, False, auto_on_after)


def cycle(name, seconds=3, wait=True):
    """Power-pull: OFF now, the plug itself switches ON after `seconds`. Returns (status_off, status_on)."""
    seconds = max(1, int(seconds))
    s_off = _set(name, False, seconds)
    if not wait:
        return s_off, None
    time.sleep(seconds + 1.5)
    s_on = status(name)
    if s_on["output"] is not True:            # the timer did not fire: restore by hand, then report
        s_on = on(name)
        raise ShellyError("%s did not come back ON by its own timer; forced ON" % name)
    return s_off, s_on


def ensure_on(name):
    """For finally-blocks and crash recovery: ON, whatever happened. Never raises."""
    try:
        s = status(name)
        return s if s["output"] else on(name)
    except Exception as e:
        return {"plug": name, "error": str(e)}


def _main(a):
    if len(a) < 1 or a[0] not in ("status", "on", "off", "cycle"):
        print(__doc__ if __doc__ else "usage: shelly.py status|on|off|cycle PLUG [--seconds N]")
        return 1
    cmd, name = a[0], (a[1] if len(a) > 1 else "all")
    secs = int(a[a.index("--seconds") + 1]) if "--seconds" in a else 3
    try:
        if cmd == "status":
            for n in (PLUGS if name == "all" else [name]):
                print(json.dumps(status(n)))
        elif cmd == "on":
            print(json.dumps(on(name)))
        elif cmd == "off":
            print(json.dumps(off(name, None if "--hold-forever" in a else 600)))
        else:
            s0, s1 = cycle(name, secs)
            print(json.dumps({"off": s0, "on": s1}))
        return 0
    except PermissionError as e:
        print(e, file=sys.stderr)
        return 3
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
