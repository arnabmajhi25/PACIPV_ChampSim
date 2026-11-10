#!/usr/bin/env python3
"""Generate the candidate (demand IPV, prefetch IPV) pairs for the PACIPV search.

An IPV is 5 values in 0..3: entries 0-3 give the new RRPV for a hit at that RRPV,
entry 4 gives the insertion RRPV. There are 4**5 = 1024 IPVs, so 1024**2 pairs.

Filters from Section 4.1 of the paper:
  1. No demotion on a hit:  V[p] <= p  for p in 0..3.
  2. Every RRPV must be reachable. Interpreted here per IPV: starting from the
     insertion RRPV and applying promotions (hits) and SRRIP aging (+1), the
     block can visit all of 0,1,2,3.  (In practice: a block can reach RRPV 0.)

This yields 71 IPVs -> 5041 pairs. The paper reports 4032 pairs; its exact
filter list ships with the authors' artifact. If you have that list, use it
instead. The pairs the paper reports ([0,1,1,0,3]/[0,1,0,0,3],
[0,0,0,1,3]/[0,0,1,1,3]) and SRRIP ([0,0,0,0,2]) are all included.

Output: one line per pair, "d0,d1,d2,d3,d4 p0,p1,p2,p3,p4".
"""
import argparse
import itertools

NUM_RRPV = 4
MAX_RRPV = NUM_RRPV - 1


def no_demotion(v):
    return all(v[p] <= p for p in range(NUM_RRPV))


def reachable(v):
    seen, stack = set(), [v[NUM_RRPV]]
    while stack:
        s = stack.pop()
        if s in seen:
            continue
        seen.add(s)
        stack.append(v[s])                    # hit -> promotion
        stack.append(min(s + 1, MAX_RRPV))    # aging during victim search
    return seen


def valid(v):
    return no_demotion(v) and reachable(v) == set(range(NUM_RRPV))


def fmt(v):
    return ",".join(map(str, v))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", default="ipv_pairs.txt")
    ap.add_argument("--exclude-identical", action="store_true",
                    help="drop pairs where demand IPV == prefetch IPV")
    args = ap.parse_args()

    singles = [v for v in itertools.product(range(NUM_RRPV), repeat=NUM_RRPV + 1) if valid(v)]
    pairs = [(d, p) for d in singles for p in singles if not (args.exclude_identical and d == p)]

    with open(args.out, "w") as f:
        for d, p in pairs:
            f.write(f"{fmt(d)} {fmt(p)}\n")

    for chk in [((0, 1, 1, 0, 3), (0, 1, 0, 0, 3)), ((0, 0, 0, 0, 2), (0, 0, 0, 0, 2))]:
        assert chk in pairs or args.exclude_identical, chk
    print(f"{len(singles)} valid IPVs -> {len(pairs)} pairs written to {args.out}")


if __name__ == "__main__":
    main()
