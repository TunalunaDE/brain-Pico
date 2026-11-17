<!-- SPDX-FileCopyrightText: 2026 noknok (Christopher Houben) -->
<!-- SPDX-License-Identifier: MIT -->
# tools/bench/dev32

DEV-32 failure-state setups, run on a bench brain via pico.py, see DEV-32 HANDOFF.

Committed unchanged by DEV-77 (17 Nov 2026; Sue's originals from Sep 2026, until then only on a bench host).
They predate ADR-003: they use root paths (`/fw_<type>.bin`, `/product.py`, `/wifi.json`) and plain file
writes, so on a current brain (read-only FS, `/data` + Store) check each one before trusting its result.
`bench_h_*` = offline product / self-heal / cache checks (setup, fix, check, cleanup); `bench_p2_*` = buzzer
alert, per-module gate (`update_all(exclude_uids=...)`), state readout, cache fix.
