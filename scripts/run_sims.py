#!/usr/bin/env python3
"""Run ChampSim over many traces (and optionally many IPV pairs) in parallel.

Baseline / single policy (e.g. LRU, SRRIP, Mockingjay, PACIPV with fixed IPVs):
    run_sims.py --binary bin/champsim_lru --traces train.txt --tag lru --out results/lru.csv

PACIPV design-space sweep (one binary, IPVs passed through env vars):
    run_sims.py --binary bin/champsim_pacipv --traces train_top100.txt \
                --pairs ipv_pairs.txt --tag pacipv --out results/sweep.csv -j 64

Output CSV columns:
    tag,demand_ipv,prefetch_ipv,trace,ipc,l1i_avg_miss_lat,llc_demand_mpki
The script is resumable: rows already in --out are skipped.
Raw logs go to --logdir (default: <out>.logs/).
"""
import argparse
import csv
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

IPC_RE = re.compile(r"CPU 0 cumulative IPC:\s*([\d.]+)")
INSTR_RE = re.compile(r"CPU 0 cumulative IPC:\s*[\d.]+\s+instructions:\s*(\d+)")
L1I_LAT_RE = re.compile(r"L1I AVERAGE MISS LATENCY:\s*([\d.]+)")
# LLC demand misses: sum LOAD + RFO misses from the LLC stats block.
LLC_LINE_RE = re.compile(r"LLC (LOAD|RFO)\s+ACCESS:\s*\d+\s+HIT:\s*\d+\s+MISS:\s*(\d+)")

FIELDS = ["tag", "demand_ipv", "prefetch_ipv", "trace", "ipc", "l1i_avg_miss_lat", "llc_demand_mpki"]


def parse(log):
    m = IPC_RE.findall(log)
    if not m:
        return None
    ipc = float(m[-1])  # last match = ROI result
    lat = L1I_LAT_RE.findall(log)
    instr = INSTR_RE.findall(log)
    llc_miss = sum(int(x[1]) for x in LLC_LINE_RE.findall(log))
    mpki = (1000.0 * llc_miss / int(instr[-1])) if instr and int(instr[-1]) > 0 else ""
    return ipc, (float(lat[-1]) if lat else ""), mpki


def run_one(args, trace, pair, logdir):
    env = os.environ.copy()
    d, p = pair if pair else ("", "")
    if pair:
        env["PACIPV_DEMAND"], env["PACIPV_PREFETCH"] = d, p
    cmd = [args.binary, "--warmup-instructions", str(args.warmup),
           "--simulation-instructions", str(args.sim), trace]
    name = os.path.basename(trace) + (f"__{d.replace(',', '')}_{p.replace(',', '')}" if pair else "")
    try:
        out = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=args.timeout).stdout
    except subprocess.TimeoutExpired:
        return None
    with open(os.path.join(logdir, name + ".log"), "w") as f:
        f.write(out)
    r = parse(out)
    if r is None:
        return None
    return {"tag": args.tag, "demand_ipv": d, "prefetch_ipv": p, "trace": os.path.basename(trace),
            "ipc": r[0], "l1i_avg_miss_lat": r[1], "llc_demand_mpki": r[2]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--binary", required=True)
    ap.add_argument("--traces", required=True, help="file with one trace path per line")
    ap.add_argument("--pairs", help="ipv_pairs.txt from gen_ipvs.py (omit for a fixed-policy run)")
    ap.add_argument("--tag", required=True, help="label stored in the CSV, e.g. lru, srrip, pacipv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--logdir")
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--warmup", type=int, default=50_000_000)
    ap.add_argument("--sim", type=int, default=100_000_000)
    ap.add_argument("--timeout", type=int, default=6 * 3600)
    args = ap.parse_args()

    traces = [l.strip() for l in open(args.traces) if l.strip() and not l.startswith("#")]
    pairs = [tuple(l.split()) for l in open(args.pairs) if l.strip()] if args.pairs else [None]

    logdir = args.logdir or args.out + ".logs"
    os.makedirs(logdir, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    done = set()
    if os.path.exists(args.out):
        with open(args.out) as f:
            for r in csv.DictReader(f):
                done.add((r["demand_ipv"], r["prefetch_ipv"], r["trace"]))

    jobs = [(t, pr) for pr in pairs for t in traces
            if ((pr[0], pr[1]) if pr else ("", "")) + (os.path.basename(t),) not in done]
    print(f"{len(jobs)} simulations to run ({len(done)} already done)", file=sys.stderr)

    new_file = not os.path.exists(args.out)
    with open(args.out, "a", newline="") as f, ThreadPoolExecutor(args.jobs) as pool:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        futs = {pool.submit(run_one, args, t, pr, logdir): (t, pr) for t, pr in jobs}
        for i, fut in enumerate(as_completed(futs), 1):
            row = fut.result()
            if row is None:
                print(f"FAILED: {futs[fut]}", file=sys.stderr)
                continue
            w.writerow(row)
            f.flush()
            if i % 100 == 0:
                print(f"{i}/{len(jobs)}", file=sys.stderr)


if __name__ == "__main__":
    main()
