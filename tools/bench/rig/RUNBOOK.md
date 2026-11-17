<!-- SPDX-FileCopyrightText: 2026 noknok (Christopher Houben) -->
<!-- SPDX-License-Identifier: MIT -->

# How to start an overnight run (unattended rig runbook, DEV-242)

For agents (Bob first) who start a long test on a bench rig in the evening and read the result in the
morning, with nobody at the bench. Host addresses, plug IDs and rig descriptions live in the private
bench notes (`tools.md`), not here. No credentials go in any file here.

| File | Runs on | Does |
|---|---|---|
| `run_night.py CONFIG.toml [--dry-run]` | bench host (Pi) | The harness: reserve, supply check, WiFi profile, loop or once, stop, restore, ONE report |
| `run_night.py --recover [RUN_DIR]` | bench host | After a crash / kill -9 of the harness: plug ON, WiFi restored, lock removed |
| `shelly.py status\|on\|off\|cycle PLUG` | any host on the LAN | Shelly Plug M Gen3: Test1/Test2 only, self-restoring cuts |
| `mango.py check\|show\|reserve\|release\|set PROFILE [--for S]\|restore` | a host with the Mango's ssh key | WiFi-degradation profiles on the GL.iNet Mango 2, with a router-side lock |
| `examples/*.toml` | - | Self-test, power-cut soak, weak-WiFi run |

## 0. One-time setup (per rig)

1. The rig has a checkout or copy of brain-Pico `tools/` (the harness calls `../../rpc_call.py`, `../../pico.py`).
2. Python 3.11 or newer (TOML configs). Older: write the config as JSON.
3. `export BENCH_SUDO_PW=...` in the shell that starts the run (for `dmesg`), unless sudo is passwordless.
4. Shelly: nothing to install. Know which testing plug feeds THIS rig's J1 (`shelly.py status all`, tools.md table).
5. Mango 2 (only for WiFi runs): site facts (address, test SSID, access, KNOWN STATE, reservation) are in the
   private bench notes, section "GL.iNet Mango 2" - read it first. The bench host's ssh public key is in the
   Mango's root `authorized_keys`; `python3 mango.py check` lists what works and, under `cannot`, what the
   router cannot do. The brain under test is joined to the Mango's test SSID.
   **Reserve before you degrade:** `MANGO_OWNER=me python3 mango.py reserve --owner me --minutes 90`, then
   `set` / `restore` (they refuse without the lock), then `release`. `show` exits 0 only in the known state.
   `run_night.py` with `wifi_profile` does all of this itself.

## 1. Before the run (5 minutes, with the setup message)

- Newest code on the rig (brain, modules, PicoHub): check, or say in the report why not.
- Nobody else on the rig: `~/BENCH_IN_USE` absent (the harness refuses to start otherwise).
- **The right brain:** set `expect_device` (device name or CPU id from `/rpc hello`). A home-LAN scan can find a
  different brain than the one on your rig (17 Nov 2026: a pilot ran against the cellar brain).
- `python3 run_night.py my.toml --dry-run`: config valid, plug answers. Then one short real pilot
  (`examples/selftest_pi4rfid.toml`, 2-15 min) if the rig or the config is new.
- Tell Christopher in ONE line: what runs, on which rig, until when (clock time), log path, what you do at the end.

## 2. Start

```bash
cd tools/bench/rig
nohup python3 run_night.py examples/powercut_soak_noknok_pi.toml > ~/runs/nohup.out 2>&1 &
```

Check once after a few minutes that `~/runs/LAST/harness.log` shows the first cycles, then leave it.
To stop early: `touch ~/runs/STOP` (loop mode stops after the current cycle and restores everything) or
`kill <pid>` (SIGTERM: same clean finish). Never `kill -9`, but if it happens: `run_night.py --recover`.

## 3. Morning

Read `~/runs/LAST/REPORT.md`: result (PASS / FAIL / INVALID-SUPPLY / ERROR), why it stopped, cycles and
cuts, first failure with its log, supply at start and end, plug and WiFi state at the end. A run with a new
undervoltage is INVALID-SUPPLY: not a product failure, fix the supply first. Copy the run folder into
QA-Testing `runs/` (it already has `results.csv` + `environment.txt` in the catalog format).

## Config keys

| Key | Default | Meaning |
|---|---|---|
| `mode` | `loop` | `loop` = cycles; `once` = one long command (e.g. `../../soak/gate_night.sh IP`) |
| `rig`, `test_id` | - | names in the report and the run folder (`~/runs/<date>_<test_id>_<rig>/`) |
| `max_hours` | 8 | hard limit, capped at 12 |
| `command`, `command_timeout_s` | -, 600 | the check; exit 0 = PASS. `$BRAIN_IP` and `$RUN_DIR` are set. `regress_all` is refused |
| `fail_marker` | - | regex: a PASS whose log matches it counts as FAIL |
| `plug`, `cut_seconds` | -, 5 | Shelly Test1/Test2 cut before each cycle (plug restores itself) |
| `max_cuts_per_hour` | 20 | cuts above it are skipped (capped at 60) |
| `cycle_every_s`, `settle_s` | 300, 60 | cycle period; wait after a cut before the check |
| `stop_after_fails` | 3 | consecutive FAILs that end the run |
| `wifi_profile` | - | Mango profile for the whole run: `weak`, `slow`, `lossy`, `flaky`, `down` |
| `wifi_hold_router_timer` | false | the Mango restores itself after `max_hours` + 10 min, even if the host dies |
| `supply_check_every_s` | 1800 | a new undervoltage line in dmesg stops the run (INVALID-SUPPLY) |
| `brain_ip`, `env` | -, {} | passed to the command |
| `expect_device` | - | text the brain's `/rpc hello` must contain (device name / CPU id); else WRONG-BRAIN, nothing runs |
| `usb_cut_hub` | - | also cut USB VBUS (`uhubctl -l HUB`, ganged) during each plug cut, for a Pico fed by the Pi's USB |

## Safety rules the harness enforces

- Only Testing Plug 1 / 2 can be switched. The cellar main plug and the main testing supply feed the agent
  box and both Pis: `shelly.py` refuses them.
- Every cut is `Switch.Set on=false toggle_after=N`: the plug turns itself back ON. Proven 17 Nov 2026 on
  Testing Plug 2: harness killed with `kill -9` in the middle of a 20 s cut, plug back ON by its own timer.
- At the end, on SIGTERM, on a crash: plug forced ON (read back), Mango back to `good`, lock removed, report written.
- Never `regress_all.sh` (Christopher runs it). Never `nmcli`/NetworkManager changes on the Pis.

## Known limits

- `once` mode checks STOP and the supply only at the end (the long command owns the night).
- Mango shaping acts on traffic towards the brain only (egress of the AP interface); upload-only shaping needs an ifb.
- A weak profile lowers what the router SENDS; the brain's own RSSI is not guaranteed: record `status.link.rssi`.
- The Mango rebooted twice on 17 Nov 2026: a reboot clears the profile and the lock and drops the brain's WiFi for
  a minute, so a single FAIL in a WiFi run can be the router - check its uptime before blaming the product.
