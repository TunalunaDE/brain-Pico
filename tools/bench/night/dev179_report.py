#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 noknok (Christopher Houben)
# SPDX-License-Identifier: MIT
#
# dev179_report.py CYCLES.jsonl - DEV-179 A/B result: per arm (radio off before reset / plain reset)
# resets that really happened, console wedges (product up, console silent), hangs (/rpc dead),
# lost reboot commands; Fisher's exact test (one-sided: radio off has FEWER failures).
import json, math, sys
recs = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
arms = {True: [], False: []}
for r in recs:
    arms[bool(r.get("radio_off"))].append(r)

def counts(rs):
    lost = sum(r["result"] == "LOST_CMD" for r in rs)
    real = [r for r in rs if r["result"] != "LOST_CMD"]
    wedged = sum(r["result"] == "WEDGED" for r in real)
    hang = sum(r["result"] == "HANG" for r in real)
    return len(rs), lost, len(real), wedged, hang

def fisher_one_sided(a, b, c, d):
    """P(X <= a) for the table [[a, b], [c, d]] (a = failures in arm 1), hypergeometric."""
    n = a + b + c + d; r1 = a + b; c1 = a + c
    def p(x):
        return math.comb(c1, x) * math.comb(n - c1, r1 - x) / math.comb(n, r1)
    return sum(p(x) for x in range(max(0, r1 - (n - c1)), a + 1))

print("%-26s %6s %6s %6s %7s %5s %7s" % ("arm", "cycles", "lost", "resets", "wedged", "hang", "fail %"))
res = {}
for k, name in ((True, "radio OFF before reset"), (False, "plain reset (radio on)")):
    n, lost, real, w, h = counts(arms[k])
    res[k] = (real, w + h)
    print("%-26s %6d %6d %6d %7d %5d %6.1f%%" % (name, n, lost, real, w, h, 100.0 * (w + h) / real if real else 0))
(r_off, f_off), (r_on, f_on) = res[True], res[False]
if r_off and r_on:
    p = fisher_one_sided(f_off, r_off - f_off, f_on, r_on - f_on)
    print("one-sided Fisher p (radio off fails less) = %.3f  -> %s" % (
        p, "significant (p < 0.05)" if p < 0.05 else "not significant"))
