# tools/bench - test helpers for the brain bench

Small tools used by the QA runs (Bob) and anyone testing a brain on a bench host (a Pi with the
brain Pico on USB). They complement `tools/pico.py`, `tools/rpc_call.py` and the `software/bench_*.py`
scripts. Nothing here ships to a customer brain. MIT, like the rest of this repo.

| File | Runs on | What it does |
|---|---|---|
| `boot_capture.py [SECONDS]` | host | Waits for an unplug + replug, then records the boot from the first second. Sends nothing. |
| `serial_listen.py [SECONDS] [--reboot\|--ctrlc]` | host | Listen-only console reader (reopens after resets). `--reboot` soft-reboots first; `--ctrlc` tells "busy" from "console dead". |
| `yank_loop.sh [RUNS] [--runtime-only]` | host | Hands-free power-pull rounds with `software/bench_yank.py`: a person pulls during each tone, the loop records each boot and runs the next round. `--runtime-only` for brains with real setup data. |
| `dev107_store_cuts.sh [ROUNDS] [IP]` | host | DEV-107: power cut during a Store write, then probe the next boot. Default: the Pi cuts VBUS itself (`uhubctl -l 2`) 0.5-6 s into the tone; `HAND=1`: a person pulls during the tone. Even rounds record the boot from replug, odd rounds touch the console first at 5-30 s. On a dead console: `/rpc hello`, dmesg, listen + Ctrl-C, data-only port cycle. Logs `~/dev107/`. |
| `dev70_at.sh HH:MM HOURS PHASES...` | host | Starts `dev70_mdns_nights.sh` at a clock time today, plus a 15-min `/rpc status` link watcher (drops, rejoins, uptime) to `dev70/link3.log`. No USB contact during the run. |
| `dev70_guard.sh END_FILE PHASE` | host | Keeps a DEV-70 run going until the end time in END_FILE, also after a Pi restart (run once + cron `@reboot`); resumes with the remaining whole hours, never twice. |
| `rpc_failure_modes.sh <ip>` | host on the LAN | `/rpc` failure modes: bad values, reboot keeps settings, dead product URL keeps the old product. Resets settings at the end. |
| `wifi_offline.py IN OUT` | host | Offline copy of a brain's `wifi.json` (fake SSID, password emptied) for tests that need a brain without network. Prints key names only. |
| `bench_inventory.py` | Pico (`pico.py run`) | Read-only: library versions, `settings.toml` pins, WiFi SSID, pin problems, modules on every I2C bus `settings.toml` configures (bus A, bus B) and the USB host. |
| `bench_dev78_parser.py` | Pico | LEDs 16x: 0x03 brightness stream (>= 10/s, 5 min, `LOAD = True` adds Display redraws); compares what was sent with the diag build's parser counters (0x3E) and polls 0x30 for governor cuts. |
| `bench_dev78_phases.py` | Pico | LEDs 16x visual glitch test: phases A (same frame resent), B (nothing sent), C (sweep), D (sweep + Display load), 60 s each; the watcher clicks the LED Button at every glitch, clicks are logged per phase. |
| `bench_display_rotation.py` | Pico | Visual check of all four Display orientations (frame, corner markers, asymmetric text). |
| `crash_product.py` | Pico, as `/data/product.py` | Crashes on purpose: exercises 3-strike recovery and safe idle. |

Rules that cost time to learn:
- Only **one** program may read the Pico's serial port at a time (pico.py, a listener, Thonny).
- Find the port by id (`/dev/serial/by-id/usb-Raspberry_Pi_Pico*-if00`): a WCH-LinkE also has a serial port.
- After a power-on a brain needs ~25 s before the product runs; leave the console alone until then.
- Keep logs and backups in `~/` on the Pi, not `/tmp` (wiped on reboot).
- `wifi.json` holds a real WiFi password: never print it, delete host copies after a test.

Unattended runs (DEV-242): `rig/` = run harness, Shelly plug control, Mango 2 WiFi profiles. Start with
[`rig/RUNBOOK.md`](rig/RUNBOOK.md) ("how to start an overnight run").

Bench-host scripts taken into git by DEV-77 (17 Nov 2026; they existed only on Pi4RFID / agent-hq):

| File | Runs on | What it does |
|---|---|---|
| `night/dev179_night.sh IP N` + `night/bench_dev179_night.py` | host (Pi4RFID, Debug Probe) | DEV-179 night A/B: N app reboots, radio-off vs plain arm, usbmon, SWD dump/reset on a hang (hooks in `probe/`, branch `dev-172-probe`), supply check at start/end. |
| `night/dev179_report.py CYCLES.jsonl` | host | Per-arm summary of a DEV-179 night (resets seen, console wedges, hangs). |
| `night/rpc_status_power.py IP` | host | One line of PicoHub power data from `/rpc status`. |
| `power/usb_powercycle.sh [OFF] [HUB] [PORT]` | host (Pi 4) | Cold boot via uhubctl VBUS cut (default hub 2, ganged) and wait for the Pico port. Not a J1 cut: use `rig/shelly.py`. |
| `power/reboot_loop.py IP N` | host | N app reboots; time to `hello` + modules back. |
| `power/rpc_cutwatch.py IP SECONDS` | host | DEV-169: after a reset, `hello` 1/s + `status`; logs cut replies and ping. |
| `thermal/max31856_log.py` | host (Pi, SPI) | MAX31856 thermocouple logger (DEV-146), rejects corrupt samples. |
| `thermal/picohub_thermal_log.py` | Pico | MOD-0011 thermal run: holds the input contract, logs rails/currents/temperature. |
| `thermal/picohub_clear_faults.py` | Pico | Clears the PicoHub's latched faults (CLEAR_FAULTS 0x12). |
| `diag/ver_check.py` | Pico | Read-only versions on the rig: CircuitPython, code.py, noknok, PicoHub power manager (rule "newest code first"). |
| `diag/list_modules.py` | Pico | Read-only inventory: every enumerated module with type, bus, UID, I2C address and firmware (DEV-197: match a clamped module's minichlink UNIID to the brain's view, check its version after a flash). |
| `diag/i2c_scan_pins.py`, `diag/scan_7f.py`, `diag/probe_bus.py` | Pico | I2C scan on every common pin pair; 0x7F/0x7E probe on bus A; Conductor addresses per type. |
| `diag/nvm_dump.py`, `diag/fs_walk.py`, `diag/env_check.py` | Pico | Read-only: nvm crash counter + OTA stamp; filesystem tree; parsed `settings.toml`. |
| `diag/find_brain.py NAME_PART` | host | Finds the brain on the /24 by `/rpc hello` (DHCP addresses move). |
| `diag/rpc_status_timing.py IP N [load]`, `diag/rpc_hello.py IP` | host | DEV-181 `status` timing in phases; one raw `hello`. |
| `diag/scan_bus.py`, `diag/pullup_probe.py`, `diag/find_module.py` | Pico | raw scan per pin pair; "no pull-ups" vs "module silent"; find a module waiting at 0x7F (only enumeration sees it). |
| `diag/read_fw_log.py`, `diag/dump_log.py`, `diag/tail_log.py` | Pico | `/log.txt` since the last boot / last 6 KB / last 14 lines (needs `/debug_log`). |
| `gate/gate_chain.sh IP` + `gate/gate_enum.py`, `gate/gate_rpc_settings.py`, `gate/gate_rpc_stress.py` | host (noknok-pi rig) | Release-gate chain (Bob, v1.3.0): SWD restore of the published images, S/M bench tests, /rpc + mDNS + due-boot checks, then a power-cut soak until 08:30; restart-proof (`~/gate/state`). Needs `BENCH_SUDO_PW`. |
| `dev32/bench_h_*.py`, `dev32/bench_p2_*.py` | Pico | DEV-32 failure-state setups (offline product, self-heal, cache-first OTA, buzzer alert, per-module gate). Pre-ADR-003 paths: see `dev32/README.md`. |
| `night/leakwatch.py IP HOURS OUT` | host | Overnight memory-slope watch of a running brain over /rpc only (hello 2 s, settings.get 3 s, status 60 s): mem_free trend, link stats, resets (DEV-181). |
| `host/wifi_add.sh` | bench host | Add a NEW WiFi profile with NetworkManager; the person types the password (agents never). Existing profiles untouched. |

`tools/agent-hq/`: `provision_agents_box.sh` (first setup of the agents' Ubuntu box), `usbpower_test.sh`, `adb_ui_dump.sh` (test-tablet screen texts). `tools/soak/gate_night.sh IP` = release-gate night (reset loop + power-cut soak + verdict).

DEV-97 / DEV-74 bench scripts (Bob, 19 Oct 2026; all run with `pico.py run`):

| File | What it does |
|---|---|
| `bench_dev97_state.py` | Read-only: parked module at 0x7E on each bus, modules + UIDs, `/data` and `/` listing. |
| `bench_dev97_fixture.py` | Writes a fake `/data/wifi.json` (SSID that does not exist, no secret) + minimal `/data/product.py` so the brain takes the offline-with-product boot path. `REMOVE = True` undoes it. |
| `bench_dev97_park.py` | Parks the Buzzer in its bootloader (ERASE, nothing written) after enumerating, so the rescue knows its UID. |
| `bench_dev97_recover.py` | Reflashes a parked Buzzer from `/data/fw_buzzer.bin` or `/buzzer_firmware.bin` on the Pico. |
| `bench_dev74_settings.py` | Rewrites `/settings.toml` for one failure scenario (`MODE` = noB, nopins, typo, restore); reboot afterwards. |
| `bench_dev74_drive.py` | Drives the Buzzer (bus A) and LED Button (bus B) and checks `i2c_bus` + `by_uid()` across buses. |
| `bench_dev74_cutenum.py` | DEV-74 step 7: arms the Pico watchdog (hard reset) while `enumerate()` runs, to cut it mid-sweep. |
| `bench_dev97_cut.py` | DEV-97 step 4: parks the Display, flashes it and hard-resets the brain after `CUT_AT` bytes. |
| `bench_dev98_downgrade.py` | DEV-98: flashes an older Display app (`/display_050.bin`) and makes the daily OTA check due. |
| `bench_factory_reset.py` | Clears wifi.json, product.py and the Store copy of the credentials (brain not reachable on the LAN). |
| `bench_dev98_downgrade16.py` | DEV-98: flashes an older LEDs 16x app (`/leds16_202.bin`) through the Pico USB host, makes the OTA check due, hard-resets. Needs two runs (the bootloader is not seen on the first, DEV-45); then `tools/usb_bench/leds_ota_bl.py` finishes the flash. Since code.py 0.27 `bench_dev133_rescue_setup.py` is the simpler downgrade. Images: module repo `firmware/bin` at commit `2d1856a` is v2.2.0 (the oldest that reports type 0x06). |
| `bench_dev130_scan_then_ap.py` | DEV-130: the code.py 0.25 radio order on the real Pico 2 W, three cycles: WiFi scan with the hotspot DOWN -> `start_ap` (AP up, 192.168.4.1) -> `stop_ap` -> a failed join -> again. Writes nothing; `pico.py reset` afterwards. Expect `RESULT PASS`. |
| `bench_dev123_cycle.py` | DEV-123 failure point: `status()` in a tight loop while `cycle_rail("bus_a", 300)` runs; no call may hang. |
| `pullrun.sh` + `pr_update.py` / `pr_check.py` / `pr_recover.py` | DEV-124 real power-pull run (20 Oct 2026): on the Pi, board fed from a Pi USB port; each round starts an app update on the Pico, cuts ALL Pi USB power with `uhubctl -l 2` (the USB 3 hub is the one that switches VBUS on a Pi 4B) at a random moment, restores it, classifies the power manager (old / new / parked) and recovers it. `sh pullrun.sh ROUNDS MIN MAX`; log in `~/bob/pullrun.log`. |
| `bench_dev133_rescue_setup.py` | DEV-133 USB rescue (and the downgrade for the update test): the cache for `usb_leds_16x` becomes v2.2.0 (`/leds16_220.bin`), the Store learns serial -> type, the OTA check is made NOT due, `/debug_log` on, then 0xB0 with no pending record and a hard reset. Expect `[USBFW] ... flashed` (2.2.0), hard reset, `[USBFW] ... verified`. Needs code.py 0.27 + noknok 1.18 + noknok_usb 1.2 on the Pico. |
| `bench_dev133_due.py` | DEV-133 USB update: makes the daily OTA check due and hard-resets. With a 16x below the published version expect `[FW] ... PENDING`, hard reset, `[USBFW] ... flashed`, hard reset, `[USBFW] ... verified`, product up (about 1:45 min). |
| `bench_dev133_read.py` | Read-only: last 25 Store events, the `[usb]`/`[fw]`/`[USBFW]`/`[BOOT]`/`[RESCUE]`/`[CRASH]` lines of `/data/log.txt` (needs `/debug_log`), the Store `usb` record, `nvm[0:6]`. Wait about 30 s after a reset before running it. |
| `bench_dev134_park_x035.py` | DEV-134: parks the PicoHub X035 without an app (J2 off) using `/bl_x035_bench.py`. Its own `supervisor.reload()` drops to the REPL under `pico.py`: follow with `pico.py reset`. Expect `[RESCUE] ... picohub ... reflashed`, `[BOOT] hard reset before the product`, then no `[CRASH]` strikes. |
| `dev70_mdns_nights.sh` | DEV-70 unattended mDNS idle test (Sue, 22 Oct 2026): per phase (default `on off on`, 12 h each) it writes `settings.toml` = base + `NOKNOK_MDNS = 1/0` (the only `pico.py` contact), cuts USB power with `uhubctl -l 2`, proves the reset and the name state, then polls `hello` every 30 s and resolves `noknok-a324.local` every 10 min. 10 failed polls in a row = HANG: captures ping, ARP, name, serial (listen + one Ctrl-C) before the next phase. No watchdog. `nohup bash dev70_mdns_nights.sh BASE.toml 12 on off on > ~/dev/pico/dev70/run.log 2>&1 &`; read `grep -E 'PHASE|HANG|RESET|RESULT|FAIL' run.log`. Shares the brain with DEV-67: never both at once. |
| `bench_dev79_kick.py` | DEV-79 (Sue): does a WiFi join started with a 0.5 s timeout finish in the background? 5 rounds (radio off/on, kick, watch 20 s). `RESULT background=5/5` means noknok_rpc `LINK_FULL_EVERY` can go to 0. `pico.py run bench_dev79_kick.py 200`, then `pico.py reset`. |
| `dhcp_offers.py` | DEV-113 (Sue), bench host, root: sends one DHCPDISCOVER (random MAC, takes no lease) and lists every offer with server, address, gateway, DNS. Healthy = one offer from the router; a `192.168.4.16..` offer via `192.168.4.1` is flagged as a stray setup-hotspot DHCP server. `echo "$BENCH_SUDO_PW" \| sudo -S python3 dhcp_offers.py wlan0 8`. |
| `bench_dev191_churn.py` | DEV-191 (Sue), bench host: ping loss vs request churn - background `ping -i 0.5` while `settings.get` runs every 3 s / 1 s with a new connection each (the app's settings-page pattern), plus an idle control arm; brain `status.link` before/after. 4 Nov 2026: idle 0.3 %, 3 s 16.7 %, 1 s 71.7 %. No phone needed. |
| `bench_dev189_park.py` | DEV-189 (Sue), bench host + `~/dev/pico/pico.py`: sets 3 strikes + soft reboot, checks the parked brain answers `hello` (`state: parked`) and leaves park on `reboot`; `guard` arg = parked network fallback (bench flag `NOKNOK_BENCH_PARK_NET_FAIL`, removed again). `CAPTURE=dir` holds the console port open and logs each boot: without it, a `pico.py reset` that closes the port mid-boot occasionally leaves the parked brain off the network (console, not field). |
| `bench_dev204_swap.py` | DEV-204 (Sue), bench host + `~/dev/pico/pico.py`: swaps the saved addresses of the Knob and the PicoHub in the Store, hard-resets with the console held (power-on path incl. the boot-hold check) and checks: no factory reset (`hello` still `provisioned`), `[MODULE]` mismatch logged, knob + picohub re-adopted. Needs noknok.py >= 1.26. |
| `bench_dev196_recover.py` | DEV-196 (Sue), bench host + `~/dev/pico/pico.py`, sudo via `BENCH_SUDO_PW`: "Recover my device" without hands - reads the Store (WiFi copy, nvm CRC) before and after, puts the brain into its UF2 bootloader (radio off first), copies the non-wipe UF2 onto RP2350 (= the drag), captures the console from power-on and times restore / WiFi / app channel / product; checks reachability afterwards. |
| `bench_dev113_rogue_dhcp.py` | DEV-113 (Sue), on the Pico: hotspot up, hotspot down, join home WiFi without a reset, hold 60 s ("PROBE NOW": run `dhcp_offers.py`), hard reset. `STOP_DHCP = True` tests the code.py 0.32 fix. |
| `bench_dev79_router_off.sh` | DEV-79 acceptance (Sue), bench host, detached: waits for the router to be unplugged, cuts the brain's USB power (cold boot with no network), records the console passively, waits for the router to come back, reports how long until the brain answers `hello` and whether the `.local` name resolves. Needs a person to unplug/replug the router. |
