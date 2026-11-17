# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# soak_an.py SOAK.jsonl - host: summary of a soak_run.py log (scenario x result counts, record continuity, time span).
import json, collections, datetime, sys, glob
path = sys.argv[1]
rows = [json.loads(l) for l in open(path)]
print("file", path.split('/')[-1], "records", len(rows), "first", rows[0]['ts'], "last", rows[-1]['ts'])
ns = [r['n'] for r in rows]; print("n contiguous 1..N:", ns == list(range(1, len(rows) + 1)))
c = collections.Counter((r['scenario'], r['result']) for r in rows)
for k in sorted(c): print("  ", k, c[k])
t = [datetime.datetime.fromisoformat(r['ts']) for r in rows]
gaps = [(rows[i]['n'], int((t[i + 1] - t[i]).total_seconds())) for i in range(len(t) - 1)]
big = [g for g in gaps if g[1] > 260]
print("max gap s", max(g for _, g in gaps), "gaps > 260 s:", big[:8])
rep = [r['report'] for r in rows if r.get('report')]
up = [x.get('uptime') for x in rep if x.get('uptime') is not None]
print("uptime at probe min/max", min(up), max(up), "| records without report", len(rows) - len(rep))
print("reset_reason", dict(collections.Counter(x.get('reset_reason') for x in rep)), "safe_mode", dict(collections.Counter(x.get('safe_mode') for x in rep)), "nvm0", dict(collections.Counter(x.get('nvm0') for x in rep)))
mem = [x['mem_end'] for x in rep if x.get('mem_end')]; print("mem_end min/max", min(mem), max(mem), "first/last", mem[0], mem[-1])
okc = sum(b.get('ok', 0) for x in rep for b in x['buses'].values()); err = sum(b.get('err', 0) for x in rep for b in x['buses'].values())
print("i2c ok", okc, "err", err)
usbn = collections.Counter(x.get('usb', {}).get('n') for x in rep); print("usb module count per record:", dict(usbn))
mods = collections.Counter()
for r in rows:
    if r['result'] == 'PASS':
        for bn, b in r['report']['buses'].items():
            for m in b['modules']: mods[(bn, m['type'], m['fw'])] += 1
        for m in r['report'].get('usb', {}).get('modules', []): mods[('usb', m.get('type'), m.get('fw'))] += 1
print("modules seen in PASS records:", dict(mods))
fails = [r for r in rows if r['result'] != 'PASS']
print("FAILS", len(fails))
for r in fails:
    rep_ = r.get('report') or {}
    mm = {bn: [(m['type'], m['fw']) for m in b['modules']] for bn, b in rep_.get('buses', {}).items()}
    print(" ", r['n'], r['ts'][5:], r['scenario'], "|", r['reason'], "|", mm, "usb", rep_.get('usb', {}).get('n'), "up", rep_.get('uptime'))
bytype = collections.Counter(r['scenario'] for r in rows); print("scenarios:", dict(bytype))
