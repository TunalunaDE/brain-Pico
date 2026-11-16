# Atorch DL24P electronic load - bench control (DEV-146, DEV-142)

Small Python scripts that drive the Atorch DL24P (USB HID `0483:5750`, firmware V1.1.0) from a Linux bench
host (today: agent-hq, `/dev/hidraw0`, run with `sudo`). Protocol: PROTOCOL.md of
github.com/sophusand/atorch-dl24p-python (captured from the official app).

| Script | What it does |
| --- | --- |
| `dl24_run.py <A> <baseline_s> <load_s> <log>` | Constant-current run with logging and safety stops (V < `DL24_VMIN` 3.5 V, MOSFET > `DL24_TMAX` 75 C, I > set + 0.5 A, no reply 5 s); the load's own time limit as backstop |
| `dl24_protect.py <A> <W>` | Set over-current / over-power protection and read it back. Lowering the over-power limit gives an abrupt self-trip (DEV-142) |
| `dl24_cutoff.py <V>` | Set the low-voltage cut-off (enforced and latching); lower it for current-limit tests, set it back to 3.0 V |
| `dl24_probe.py`, `dl24_words.py` | Read-only: settings and measurements |

Bench notes (rig wiring, safe limits, lessons): `~/.claude/tools.md` section "Temperature + electronic-load instruments".
The MOD-0011 board-side logger used with these: `module-I2C-picohub-MOD-0011` `firmware/test/picohub_demand_log.py`.
