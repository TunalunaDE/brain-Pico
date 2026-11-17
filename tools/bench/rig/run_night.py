#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# run_night.py CONFIG.toml [--dry-run] | --recover [RUN_DIR] - unattended rig run harness (DEV-242).
# One command starts a run; the harness reserves the rig, checks the supply, (optionally) degrades WiFi on
# the Mango 2, runs the test, cuts power with a Shelly testing plug if asked, stops safely on failure,
# timeout or a STOP file, restores everything and writes ONE morning report. See RUNBOOK.md (same folder).
#
# Two modes (config key `mode`):
#   loop  every `cycle_every_s`: [Shelly cut `cut_seconds`] -> wait `settle_s` -> run `command`
#         (exit 0 = PASS). Stops after `stop_after_fails` consecutive FAILs.
#   once  run `command` once (a script that runs the whole night itself, e.g. tools/soak/gate_night.sh)
#         with `max_hours` as its time limit; exit 0 = PASS. The harness only watches and reports.
# Safety, always on:
#   * hard time limit `max_hours` (<= 12); cuts limited to `max_cuts_per_hour` (<= 60, default 20)
#   * only Shelly Test1/Test2 can be switched (shelly.py refuses the others); every cut uses the plug's own
#     timer, so the plug comes back ON even if this process is killed; the finally-block and --recover
#     force it ON again and record its state
#   * the Mango profile is restored at the end, on a crash (finally) and by --recover; with
#     `wifi_hold_router_timer = true` the router restores itself after max_hours too
#   * rig reservation ~/BENCH_IN_USE: refuses to start if someone else holds it (development first)
#   * supply check (vcgencmd get_throttled + dmesg undervoltage count) at start, every
#     `supply_check_every_s` and at the end; a NEW undervoltage stops the run (result INVALID-SUPPLY)
#   * never runs regress_all.sh (refused in `command`)
# Output: RUN_DIR = ~/runs/<date>_<test_id>_<rig>/ : REPORT.md (read this in the morning),
#   results.csv (QA-Testing format: id,result,duration_s,reason,log), cycles.jsonl, harness.log,
#   environment.txt (start/end supply, plug, WiFi profile, git revision), logs/cycle_NNNN.log.
#   ~/runs/LAST -> the newest run dir. Copy RUN_DIR into QA-Testing runs/ to keep it.
# sudo (dmesg): passwordless, or BENCH_SUDO_PW in the environment - never in the config file.
import argparse, csv, datetime, json, os, re, signal, subprocess, sys, time

try:
    import tomllib
except ImportError:                       # Python < 3.11: allow a JSON config instead
    tomllib = None

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shelly, mango                        # noqa: E402

LOCK = os.path.expanduser("~/BENCH_IN_USE")
DEFAULTS = dict(mode="loop", rig="unknown", test_id="T-UNSET", max_hours=8.0, plug="", cut_seconds=5,
                max_cuts_per_hour=20, cycle_every_s=300, settle_s=60, command="", command_timeout_s=600,
                stop_after_fails=3, wifi_profile="", wifi_hold_router_timer=False, supply_check_every_s=1800,
                brain_ip="", fail_marker="", env={})
STOP = {"why": None}


def load(path):
    raw = open(path, "rb").read()
    cfg = tomllib.loads(raw.decode()) if (tomllib and path.endswith(".toml")) else json.loads(raw)
    c = dict(DEFAULTS, **cfg)
    bad = [k for k in cfg if k not in DEFAULTS]
    if bad:
        raise SystemExit("unknown config keys: %s" % bad)
    if not c["command"]:
        raise SystemExit("config: `command` is required")
    if "regress_all" in c["command"]:
        raise SystemExit("refused: regress_all.sh is only run by Christopher")
    c["max_hours"] = min(float(c["max_hours"]), 12.0)
    c["max_cuts_per_hour"] = min(int(c["max_cuts_per_hour"]), 60)
    if c["plug"] and c["plug"] not in shelly.SWITCHABLE:
        raise SystemExit("config: plug must be Test1 or Test2")
    if c["mode"] not in ("loop", "once"):
        raise SystemExit("config: mode must be loop or once")
    return c


def sudo(cmd):
    pw = os.environ.get("BENCH_SUDO_PW")
    if pw:
        return subprocess.run(["sudo", "-S", "-p", ""] + cmd, input=pw + "\n", capture_output=True, text=True, timeout=30)
    return subprocess.run(["sudo", "-n"] + cmd, capture_output=True, text=True, timeout=30)


def supply():
    s = {"t": time.strftime("%F %T")}
    try:
        s["throttled"] = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception as e:
        s["throttled"] = "n/a (%s)" % e.__class__.__name__     # not a Pi (agent-hq)
    try:
        d = sudo(["dmesg"]).stdout
        s["undervoltage_lines"] = len(re.findall(r"(?i)under-?voltage", d))
    except Exception as e:
        s["undervoltage_lines"] = None
        s["dmesg_error"] = str(e)
    return s


class Run:
    def __init__(self, c, dry):
        self.c, self.dry = c, dry
        self.t0 = time.time()
        stamp = datetime.date.today().isoformat()
        self.dir = os.path.expanduser("~/runs/%s_%s_%s" % (stamp, c["test_id"], c["rig"]))
        if os.path.exists(self.dir):
            self.dir += time.strftime("_%H%M")
        os.makedirs(os.path.join(self.dir, "logs"), exist_ok=True)
        self.cycles, self.cuts, self.fails_in_row = [], [], 0
        self.result, self.reason, self.first_fail = None, "", None
        self.supply0 = self.supply1 = None
        self.plug_end = self.wifi_end = None
        self.lock_mine = False
        self.state = os.path.join(self.dir, "state.json")
        self._save_state("starting")
        self._point_last()                       # at START, so --recover finds a run that was killed

    def _point_last(self):
        last = os.path.expanduser("~/runs/LAST")
        try:
            if os.path.islink(last) or os.path.exists(last):
                os.remove(last)
            os.symlink(self.dir, last)
        except OSError:
            pass

    def log(self, msg):
        line = "%s %s" % (time.strftime("%F %T"), msg)
        print(line, flush=True)
        open(os.path.join(self.dir, "harness.log"), "a").write(line + "\n")

    def _save_state(self, phase):
        json.dump({"pid": os.getpid(), "phase": phase, "plug": self.c["plug"], "wifi": self.c["wifi_profile"],
                   "lock_mine": getattr(self, "lock_mine", False)}, open(self.state, "w"))

    # -- reservation -------------------------------------------------------------------------------------
    def reserve(self):
        if os.path.exists(LOCK):
            who = open(LOCK).read().strip()[:200]
            raise SystemExit("rig busy (~/BENCH_IN_USE: %r): not starting (development has priority)" % who)
        open(LOCK, "w").write("run_night %s %s pid %d until %s\n" % (
            self.c["test_id"], self.dir, os.getpid(),
            time.strftime("%F %T", time.localtime(self.t0 + self.c["max_hours"] * 3600))))
        self.lock_mine = True
        self._save_state("reserved")

    # -- one loop cycle ----------------------------------------------------------------------------------
    def _cut_allowed(self):
        now = time.time()
        self.cuts = [t for t in self.cuts if now - t < 3600]
        return len(self.cuts) < self.c["max_cuts_per_hour"]

    def cycle(self, n):
        c, rec = self.c, {"n": n, "t": time.strftime("%F %T")}
        if c["plug"]:
            if not self._cut_allowed():
                rec["cut"] = "skipped (max_cuts_per_hour)"
            else:
                s_off, s_on = shelly.cycle(c["plug"], c["cut_seconds"])
                self.cuts.append(time.time())
                rec["cut"] = {"plug": c["plug"], "seconds": c["cut_seconds"], "w_before_off": s_off.get("apower_w"),
                              "w_after_on": s_on.get("apower_w") if s_on else None}
            self._sleep(c["settle_s"])
        rec.update(self._run_cmd(c["command"], c["command_timeout_s"], "cycle_%04d.log" % n))
        return rec

    def _run_cmd(self, cmd, timeout, logname):
        env = dict(os.environ, BRAIN_IP=self.c["brain_ip"], RUN_DIR=self.dir, **{k: str(v) for k, v in self.c["env"].items()})
        logp = os.path.join(self.dir, "logs", logname)
        t = time.time()
        try:
            with open(logp, "w") as f:
                p = subprocess.Popen(cmd, shell=True, stdout=f, stderr=subprocess.STDOUT, env=env, start_new_session=True)
                self._child = p
                rc = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGTERM)
            time.sleep(3)
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)
            rc = "timeout"
        finally:
            self._child = None
        ok = rc == 0
        if ok and self.c["fail_marker"]:
            if re.search(self.c["fail_marker"], open(logp, errors="replace").read()):
                ok, rc = False, "fail_marker"
        return {"rc": rc, "result": "PASS" if ok else "FAIL", "secs": round(time.time() - t, 1), "log": "logs/" + logname}

    def _sleep(self, s):
        end = time.time() + s
        while time.time() < end and not self._should_stop():
            time.sleep(min(5, max(0, end - time.time())))

    def _should_stop(self):
        if STOP["why"]:
            return True
        if os.path.exists(os.path.join(self.dir, "STOP")) or os.path.exists(os.path.expanduser("~/runs/STOP")):
            STOP["why"] = "STOP file found"
        elif time.time() - self.t0 > self.c["max_hours"] * 3600:
            STOP["why"] = "max_hours reached"
        return bool(STOP["why"])

    def _supply_ok(self):
        s = supply()
        self.log("supply %s" % json.dumps(s))
        u0 = (self.supply0 or {}).get("undervoltage_lines")
        if u0 is not None and s.get("undervoltage_lines") is not None and s["undervoltage_lines"] > u0:
            STOP["why"] = "new undervoltage on the bench host (%d -> %d)" % (u0, s["undervoltage_lines"])
            self.result = "INVALID-SUPPLY"
            return False
        return True

    # -- main --------------------------------------------------------------------------------------------
    def go(self):
        c = self.c
        self.log("run %s on %s, mode %s, max %.2f h, plug %s, wifi %s, dir %s" % (
            c["test_id"], c["rig"], c["mode"], c["max_hours"], c["plug"] or "-", c["wifi_profile"] or "-", self.dir))
        if self.dry:
            self.log("dry run: config OK; plug/wifi/command NOT touched")
            if c["plug"]:
                self.log("plug %s now: %s" % (c["plug"], json.dumps(shelly.status(c["plug"]))))
            self.result, self.reason = "DRY-RUN", "config checked only"
            return
        self.reserve()
        self.supply0 = supply()
        self.log("supply start %s" % json.dumps(self.supply0))
        if c["plug"]:
            self.log("plug start %s" % json.dumps(shelly.ensure_on(c["plug"])))
        if c["wifi_profile"]:
            hold = int(c["max_hours"] * 3600) + 600 if c["wifi_hold_router_timer"] else None
            self.log("wifi profile %s: %s" % (c["wifi_profile"], json.dumps(mango.set_profile(c["wifi_profile"], hold))))
        self._save_state("running")
        last_supply = time.time()
        if c["mode"] == "once":
            rec = self._run_cmd(c["command"], int(c["max_hours"] * 3600), "once.log")
            self.cycles.append(rec)
            self._write_cycle(rec)
            if rec["result"] == "FAIL":
                self.first_fail = rec
        else:
            n = 0
            while not self._should_stop():
                n += 1
                t_cycle = time.time()
                rec = self.cycle(n)
                self.cycles.append(rec)
                self._write_cycle(rec)
                if rec["result"] == "FAIL":
                    self.fails_in_row += 1
                    self.first_fail = self.first_fail or rec
                    self.log("cycle %d FAIL rc=%s (%d in a row)" % (n, rec["rc"], self.fails_in_row))
                    if self.fails_in_row >= c["stop_after_fails"]:
                        STOP["why"] = "%d consecutive FAILs (cycle %d)" % (self.fails_in_row, n)
                        break
                else:
                    self.fails_in_row = 0
                    self.log("cycle %d PASS (%.1f s)" % (n, rec["secs"]))
                if time.time() - last_supply > c["supply_check_every_s"]:
                    last_supply = time.time()
                    if not self._supply_ok():
                        break
                self._sleep(max(0, c["cycle_every_s"] - (time.time() - t_cycle)))

    def _write_cycle(self, rec):
        open(os.path.join(self.dir, "cycles.jsonl"), "a").write(json.dumps(rec) + "\n")

    def finish(self, crash=None):
        if getattr(self, "_finished", False):  # never twice (a crash inside finish must not re-run it)
            return
        self._finished = True
        c = self.c
        if crash:
            self.result, self.reason = "ERROR", "harness crashed: %s" % crash
            self.log(self.reason)
        if getattr(self, "_child", None) and self._child.poll() is None:
            os.killpg(self._child.pid, signal.SIGTERM)
        if not self.dry:
            if c["plug"]:
                self.plug_end = shelly.ensure_on(c["plug"])
                self.log("plug end %s" % json.dumps(self.plug_end))
            if c["wifi_profile"]:
                self.wifi_end = mango.ensure_restored()
                self.log("wifi restored %s" % json.dumps(self.wifi_end))
            self.supply1 = supply()
            self.log("supply end %s" % json.dumps(self.supply1))
            u0, u1 = (self.supply0 or {}).get("undervoltage_lines"), self.supply1.get("undervoltage_lines")
            if u0 is not None and u1 is not None and u1 > u0 and self.result is None:
                self.result = "INVALID-SUPPLY"
        n = len(self.cycles)
        npass = sum(1 for r in self.cycles if r["result"] == "PASS")
        if self.result is None:
            self.result = "PASS" if n and npass == n else ("FAIL" if n else "ERROR")
        if not self.reason:
            self.reason = STOP["why"] or ("completed" if c["mode"] == "once" else "ended")
        if self.lock_mine and os.path.exists(LOCK) and "run_night" in open(LOCK).read():
            os.remove(LOCK)
        self._save_state("done")
        self._report(n, npass)

    def _report(self, n, npass):
        c, dur = self.c, int(time.time() - self.t0)
        with open(os.path.join(self.dir, "results.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "result", "duration_s", "reason", "log"])
            w.writerow([c["test_id"], self.result, dur, "%s; %d/%d cycles PASS" % (self.reason, npass, n), "cycles.jsonl"])
        try:
            rev = subprocess.run(["git", "-C", HERE, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            rev = ""                          # no git on the host (Pi4RFID): copy of the tools, revision unknown
        with open(os.path.join(self.dir, "environment.txt"), "w") as f:
            f.write("rig: %s\nhost: %s\nbrain_ip: %s\nharness: brain-Pico %s tools/bench/rig/run_night.py\n"
                    "config: %s\nsupply_start: %s\nsupply_end: %s\nplug_end: %s\nwifi_end: %s\n" % (
                        c["rig"], os.uname().nodename, c["brain_ip"], rev or "?", json.dumps(c),
                        json.dumps(self.supply0), json.dumps(self.supply1), json.dumps(self.plug_end), json.dumps(self.wifi_end)))
        ff = self.first_fail
        lines = [
            "# %s on %s: **%s**" % (c["test_id"], c["rig"], self.result), "",
            "- Window: %s to %s (%.2f h of max %.2f h)" % (time.strftime("%F %T", time.localtime(self.t0)),
                                                          time.strftime("%F %T"), dur / 3600, c["max_hours"]),
            "- Stopped because: %s" % self.reason,
            "- Cycles: %d, PASS %d, FAIL %d; power cuts: %d (plug %s, %s s)" % (
                n, npass, n - npass, sum(1 for r in self.cycles if isinstance(r.get("cut"), dict)),
                c["plug"] or "-", c["cut_seconds"]),
            "- First failure: %s" % ("cycle %s at %s, rc=%s, log %s" % (ff.get("n", "-"), ff.get("t", "-"), ff["rc"], ff["log"]) if ff else "none"),
            "- Supply: start %s, end %s" % (json.dumps(self.supply0), json.dumps(self.supply1)),
            "- Plug at end: %s" % (json.dumps(self.plug_end) if c["plug"] else "not used"),
            "- WiFi profile: %s, restored: %s" % (c["wifi_profile"] or "not used", json.dumps(self.wifi_end) if c["wifi_profile"] else "-"),
            "- Command: `%s`" % c["command"],
            "- Files: %s (results.csv, cycles.jsonl, harness.log, environment.txt, logs/)" % self.dir, "",
        ]
        open(os.path.join(self.dir, "REPORT.md"), "w").write("\n".join(lines))
        self._point_last()
        self.log("REPORT %s -> %s" % (self.result, os.path.join(self.dir, "REPORT.md")))


def recover(run_dir):
    """After a crash (or kill -9) of the harness: plug ON, WiFi restored, lock removed if it was ours."""
    run_dir = run_dir or os.path.realpath(os.path.expanduser("~/runs/LAST"))
    st = json.load(open(os.path.join(run_dir, "state.json")))
    out = {"run_dir": run_dir, "state": st}
    if st.get("plug"):
        out["plug"] = shelly.ensure_on(st["plug"])
    if st.get("wifi"):
        out["wifi"] = mango.ensure_restored()
    if os.path.exists(LOCK) and "run_night" in open(LOCK).read() and run_dir in open(LOCK).read():
        os.remove(LOCK)
        out["lock"] = "removed"
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser(description="unattended rig run harness (DEV-242)")
    ap.add_argument("config", nargs="?")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--recover", nargs="?", const="", metavar="RUN_DIR")
    a = ap.parse_args()
    if a.recover is not None:
        return recover(a.recover or None)
    if not a.config:
        ap.error("config required")
    r = Run(load(a.config), a.dry_run)

    def on_signal(sig, _):
        STOP["why"] = "signal %d" % sig
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGHUP, on_signal)
    try:
        r.go()
        r.finish()
    except KeyboardInterrupt:
        r.reason = STOP["why"] or "interrupted"
        r.finish()
    except SystemExit:
        raise
    except Exception as e:
        if getattr(r, "_finished", False):
            raise                                # finish itself failed: the safety steps before it already ran
        r.finish(crash="%s: %s" % (e.__class__.__name__, e))
    return 0 if r.result in ("PASS", "DRY-RUN") else 1


if __name__ == "__main__":
    sys.exit(main())
