#!/usr/bin/env python3
"""Split traces into disjoint train/test sets by benchmark, then keep the top-N
of each set by L1I average miss latency under LRU (as in Section 5.1).

Step 1 (no baseline yet): just split.
    split_traces.py --traces all_traces.txt --out-prefix sets/

Step 2 (after running LRU on both sets with run_sims.py): pick the top-N.
    split_traces.py --traces all_traces.txt --out-prefix sets/ --lru results/lru.csv --top 100

Traces from the same benchmark (different SimPoints) are never split across
sets. The benchmark name is taken from the file name with --group-regex; the
default strips a trailing "_<number>" / "-<number>" and the extension, e.g.
"srv_12.champsimtrace.xz" and "srv_7.champsimtrace.xz" -> "srv".
Adjust it for your trace naming.
"""
import argparse
import csv
import os
import random
import re
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--traces", required=True)
    ap.add_argument("--out-prefix", default="")
    ap.add_argument("--group-regex", default=r"^(.*?)(?:[_\-.]\d+)?(?:\.champsimtrace)?(?:\.(?:xz|gz))?$")
    ap.add_argument("--train-frac", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--lru", help="LRU results CSV from run_sims.py (enables top-N selection)")
    ap.add_argument("--top", type=int, default=100)
    args = ap.parse_args()

    traces = [l.strip() for l in open(args.traces) if l.strip() and not l.startswith("#")]
    rx = re.compile(args.group_regex)
    groups = defaultdict(list)
    for t in traces:
        m = rx.match(os.path.basename(t))
        groups[m.group(1) if m else os.path.basename(t)].append(t)

    names = sorted(groups)
    random.Random(args.seed).shuffle(names)
    n_train = round(len(names) * args.train_frac)
    sets = {"train": [t for g in names[:n_train] for t in groups[g]],
            "test": [t for g in names[n_train:] for t in groups[g]]}

    if args.out_prefix:
        os.makedirs(os.path.dirname(args.out_prefix) or ".", exist_ok=True)
    for k, v in sets.items():
        with open(f"{args.out_prefix}{k}.txt", "w") as f:
            f.write("\n".join(v) + "\n")
        print(f"{k}: {len(v)} traces from {len({rx.match(os.path.basename(t)).group(1) for t in v})} benchmarks")

    if args.lru:
        lat = {}
        with open(args.lru) as f:
            for r in csv.DictReader(f):
                if r["l1i_avg_miss_lat"]:
                    lat[r["trace"]] = float(r["l1i_avg_miss_lat"])
        for k, v in sets.items():
            ranked = sorted((t for t in v if os.path.basename(t) in lat),
                            key=lambda t: lat[os.path.basename(t)], reverse=True)[: args.top]
            with open(f"{args.out_prefix}{k}_top{args.top}.txt", "w") as f:
                f.write("\n".join(ranked) + "\n")
            print(f"{k}_top{args.top}: {len(ranked)} traces")


if __name__ == "__main__":
    main()
