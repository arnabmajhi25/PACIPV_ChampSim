#!/usr/bin/env python3
"""Rank IPV pairs (training) or compare policies (testing) against an LRU baseline.

Rank the sweep (training phase):
    analyze.py rank --baseline results/lru_train.csv --sweep results/sweep.csv --top 20

Compare policies on the testing set:
    analyze.py compare --baseline results/lru_test.csv \
        results/srrip_test.csv results/mockingjay_test.csv results/pacipv_test.csv

Speedup is the geometric mean of per-trace IPC ratios over LRU (Section 4.4);
LLC MPKI is the arithmetic mean.
"""
import argparse
import csv
import math
from collections import defaultdict


def load(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def geomean(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else float("nan")


def baseline_ipc(path):
    return {r["trace"]: float(r["ipc"]) for r in load(path)}


def cmd_rank(args):
    base = baseline_ipc(args.baseline)
    per_pair = defaultdict(dict)
    for r in load(args.sweep):
        if r["trace"] in base:
            per_pair[(r["demand_ipv"], r["prefetch_ipv"])][r["trace"]] = float(r["ipc"]) / base[r["trace"]]

    # Only rank pairs that finished on every trace, so they are compared fairly.
    full = max((len(v) for v in per_pair.values()), default=0)
    scored = sorted(((geomean(list(v.values())), k) for k, v in per_pair.items() if len(v) == full), reverse=True)

    print(f"{len(scored)} complete pairs over {full} traces\n")
    print(f"{'rank':>4}  {'demand IPV':<12} {'prefetch IPV':<12} geomean speedup")
    for i, (s, (d, p)) in enumerate(scored[: args.top], 1):
        print(f"{i:>4}  [{d}]  [{p}]  {100 * (s - 1):+.2f}%")

    srrip = per_pair.get(("0,0,0,0,2", "0,0,0,0,2"))
    if srrip and len(srrip) == full:
        print(f"\nSRRIP-equivalent pair [0,0,0,0,2]/[0,0,0,0,2]: {100 * (geomean(list(srrip.values())) - 1):+.2f}%")

    # Per-trace oracle ("PACIPV-best" in Figure 8)
    traces = defaultdict(list)
    for v in per_pair.values():
        for t, s in v.items():
            traces[t].append(s)
    best = [max(v) for v in traces.values()]
    print(f"Per-trace best IPV (PACIPV-best): {100 * (geomean(best) - 1):+.2f}% geomean")


def cmd_compare(args):
    base = baseline_ipc(args.baseline)
    print(f"{'policy':<14} {'traces':>6} {'geomean speedup':>16} {'LLC demand MPKI':>16} {'traces faster':>14}")
    for path in args.results:
        rows = [r for r in load(path) if r["trace"] in base]
        if not rows:
            continue
        sp = [float(r["ipc"]) / base[r["trace"]] for r in rows]
        mpki = [float(r["llc_demand_mpki"]) for r in rows if r["llc_demand_mpki"]]
        avg_mpki = sum(mpki) / len(mpki) if mpki else float("nan")
        faster = sum(1 for s in sp if s > 1)
        print(f"{rows[0]['tag']:<14} {len(rows):>6} {100 * (geomean(sp) - 1):>+15.2f}% {avg_mpki:>16.3f} {faster:>8}/{len(sp)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rank")
    r.add_argument("--baseline", required=True)
    r.add_argument("--sweep", required=True)
    r.add_argument("--top", type=int, default=20)
    c = sub.add_parser("compare")
    c.add_argument("--baseline", required=True)
    c.add_argument("results", nargs="+")
    args = ap.parse_args()
    cmd_rank(args) if args.cmd == "rank" else cmd_compare(args)


if __name__ == "__main__":
    main()
