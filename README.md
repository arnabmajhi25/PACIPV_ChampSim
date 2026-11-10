# PACIPV in ChampSim (CS2201, Group 15)

This fork of [ChampSim](https://github.com/ChampSim/ChampSim) implements **PACIPV** (Prefetch-Aware Coarse-grained Insertion and Promotion Vectors, Mostofi et al., ISCA 2025) as a last-level-cache replacement policy and evaluates it against LRU, SRRIP and Mockingjay.

## What PACIPV does

Every LLC block has a 2-bit re-reference prediction value (RRPV): 0 means "reused soon" and 3 means "evict next". The policy is described by two 5-entry vectors:

- `V[0..3]`: the new RRPV of a block that is hit while at RRPV 0..3 (promotion).
- `V[4]`: the RRPV given to a newly filled block (insertion).

Demand accesses use the demand vector and prefetch accesses use the prefetch vector. Victim selection and aging are the same as SRRIP: evict a block at RRPV 3, and if there is none, age the whole set until one appears. SRRIP is the special case `[0,0,0,0,2]` for both vectors.

The default vectors are the paper's best pair: demand `[0,1,1,0,3]`, prefetch `[0,1,0,0,3]`.

## What is in this repository

| Path | Contents |
|---|---|
| [replacement/pacipv/](replacement/pacipv/) | The PACIPV replacement module (`pacipv.h`, `pacipv.cc`) |
| [prefetcher/eip/](prefetcher/eip/) | EIP L1I prefetcher, ported to this ChampSim version |
| [prefetcher/berti/](prefetcher/berti/) | Berti L1D prefetcher, ported |
| [branch/tage_sc_l/](branch/tage_sc_l/) | TAGE-SC-L branch predictor, ported |
| [scripts/](scripts/) | Scripts to split traces, generate IPV pairs, run simulations, analyse results, and demo the policy |
| `lru_config.json`, `srrip_config.json`, `pacipv_config.json` | Baseline machine: hashed perceptron, next-line L2 prefetcher, LLC policy varies |
| `port_lru.json`, `port_pacipv.json` | Paper-like machine: TAGE-SC-L, EIP at L1I, Berti at L1D, next-line at L2 |
| [mockingjay_port/](mockingjay_port/) | Mockingjay policy used for comparison, with its config and our build patches (see the folder's README) |
| `ipv_pairs_authors.txt` | The 4032 (demand, prefetch) IPV pairs from the authors' artifact |

All configurations use a 3 MB, 12-way LLC (4096 sets).

Changes to ChampSim itself are small (6 lines):

- `Makefile`: the legacy bridge also strips `O3_CPU::`, so ported branch predictors are detected.
- `inc/cache.h`: adds the prefetcher signature used by the ported prefetchers (integer addresses with `useful_prefetch`).
- `inc/util/lru_table.h`: removes an `#error` that stopped the ported legacy modules from compiling.

## Run time options

The vectors can be changed without recompiling:

```
PACIPV_DEMAND=0,1,1,0,3 PACIPV_PREFETCH=0,1,0,0,3 bin/champsim_pacipv ...
PACIPV_TIEBREAK=first bin/champsim_pacipv ...   # take the first way at RRPV 3 (default: random among them)
```

## Build

Install the dependencies as described under "Download dependencies" below. Then build each configuration:

```
./config.sh pacipv_config.json && make      # bin/champsim_pacipv
./config.sh lru_config.json    && make      # bin/champsim_lru
./config.sh srrip_config.json  && make      # bin/champsim_srrip
./config.sh port_pacipv.json   && make      # bin/champsim_port_pacipv
./config.sh port_lru.json      && make      # bin/champsim_port_lru
```

## Reproduce the experiments

We used the public CVP-1 server traces converted to ChampSim format (`srv_*.champsimtrace.xz`). Each script prints full usage with `--help`.

```
# 1. Split traces into train/test sets by benchmark, then keep the top N by L1I miss latency
python3 scripts/split_traces.py --traces all_traces.txt --out-prefix sets/

# 2. Generate candidate IPV pairs (or use ipv_pairs_authors.txt)
python3 scripts/gen_ipvs.py -o ipv_pairs.txt

# 3. Run a fixed policy or a sweep of IPV pairs (resumable, parallel)
python3 scripts/run_sims.py --binary bin/champsim_port_lru    --traces test.txt --tag lru    --out res/lru.csv --warmup 10000000 --sim 20000000
python3 scripts/run_sims.py --binary bin/champsim_port_pacipv --traces test.txt --tag pacipv --out res/pacipv.csv --warmup 10000000 --sim 20000000

# 4. Compare against LRU (geometric-mean speedup, mean LLC demand MPKI)
python3 scripts/analyze.py compare --baseline res/lru.csv res/srrip_true.csv res/pacipv.csv
```

For "true SRRIP", run the PACIPV binary with `PACIPV_DEMAND=0,0,0,0,2 PACIPV_PREFETCH=0,0,0,0,2`.

## Results

These results come from 10 test traces on the paper-like machine, with 10M warmup and 20M measured instructions. Speedup is the geometric mean of IPC over LRU.

| Policy | Speedup over LRU | 95% bootstrap CI | Faster / slower traces | Mean LLC demand MPKI |
|---|---|---|---|---|
| LRU | baseline | | | 1.977 |
| True SRRIP `[0,0,0,0,2]` | +0.064% | -0.32% to +0.54% | 5 / 3 | 1.876 |
| PACIPV `[0,1,1,0,3]`/`[0,1,0,0,3]` | +0.100% | -0.33% to +0.72% | 4 / 5 | 1.862 |
| Mockingjay | -0.530% | -1.38% to +0.01% | 2 / 8 | 2.060 |

**We did not reproduce the paper's 3.3% speedup.** PACIPV has the lowest demand MPKI, but every difference from LRU is within noise. Most of PACIPV's gain comes from one trace (srv_38); without it, the result is -0.17%. Our traces put little pressure on the LLC: 9 of the 10 traces had fewer LRU misses than the LLC's 49,152 blocks. Our runs are also far shorter than the paper's.

### ChampSim SRRIP bug

ChampSim's built-in `srrip` module inserts filled blocks at RRPV 3 instead of 2, because the fill path does not set the RRPV. We showed this with an equivalence test on srv_9 (5M warmup, 10M measured):

| Configuration | LLC accesses | Hits | Misses | IPC |
|---|---|---|---|---|
| ChampSim SRRIP | 9454 | 3381 | 6073 | 0.4405 |
| PACIPV `[0,0,0,0,3]`, first-way tiebreak | 9454 | 3381 | 6073 | 0.4405 |
| PACIPV `[0,0,0,0,2]`, first-way tiebreak | 9477 | 3508 | 5969 | 0.4406 |
| ChampSim SRRIP with fill fixed | 9477 | 3508 | 5969 | 0.4406 |

The matching rows are identical in every count. This shows both that our PACIPV implementation is correct and that the built-in SRRIP is really `[0,0,0,0,3]`. Our evaluation therefore uses true SRRIP through PACIPV.

## Demo

```
python3 scripts/ipv_demo.py    # instant: one 4-way set, event by event, PACIPV vs SRRIP
bash scripts/demo.sh           # about 12 min: reruns the SRRIP equivalence test above
```

To use traces stored somewhere else, run `TRACES=/path/to/traces bash scripts/demo.sh`.

---

# ChampSim (original README)


![GitHub](https://img.shields.io/github/license/ChampSim/ChampSim)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/ChampSim/ChampSim/test.yml)
![GitHub forks](https://img.shields.io/github/forks/ChampSim/ChampSim)
[![Coverage Status](https://coveralls.io/repos/github/ChampSim/ChampSim/badge.svg?branch=develop)](https://coveralls.io/github/ChampSim/ChampSim?branch=develop)

ChampSim is a trace-based simulator for a microarchitecture study. If you have questions about how to use ChampSim, we encourage you to search the threads in the Discussions tab or start your own thread. If you are aware of a bug or have a feature request, open a new Issue.

# Using ChampSim

ChampSim is the result of academic research. If you use this software in your work, please cite it using the following reference:

    Gober, N., Chacon, G., Wang, L., Gratz, P. V., Jimenez, D. A., Teran, E., Pugsley, S., & Kim, J. (2022). The Championship Simulator: Architectural Simulation for Education and Competition. https://doi.org/10.48550/arXiv.2210.14324

If you use ChampSim in your work, you may submit a pull request modifying `PUBLICATIONS_USING_CHAMPSIM.bib` to have it featured in [the documentation](https://champsim.github.io/ChampSim/master/Publications-using-champsim.html).

# Download dependencies

ChampSim uses [vcpkg](https://vcpkg.io) to manage its dependencies. In this repository, vcpkg is included as a submodule. You can download the dependencies with
```
git submodule update --init
vcpkg/bootstrap-vcpkg.sh
vcpkg/vcpkg install
```

# Compile

ChampSim takes a JSON configuration script. Examine `champsim_config.json` for a fully-specified example. All options described in this file are optional and will be replaced with defaults if not specified. The configuration scrip can also be run without input, in which case an empty file is assumed.
```
$ ./config.sh <configuration file>
$ make
```

# Download DPC-3 trace

Traces used for the 3rd Data Prefetching Championship (DPC-3) can be found here. (https://dpc3.compas.cs.stonybrook.edu/champsim-traces/speccpu/) A set of traces used for the 2nd Cache Replacement Championship (CRC-2) can be found from this link. (http://bit.ly/2t2nkUj)

Storage for these traces is kindly provided by Daniel Jimenez (Texas A&M University) and Mike Ferdman (Stony Brook University). If you find yourself frequently using ChampSim, it is highly encouraged that you maintain your own repository of traces, in case the links ever break.

# Run simulation

Execute the binary directly.
```
$ bin/champsim --warmup-instructions 200000000 --simulation-instructions 500000000 ~/path/to/traces/600.perlbench_s-210B.champsimtrace.xz
```

The number of warmup and simulation instructions given will be the number of instructions retired. Note that the statistics printed at the end of the simulation include only the simulation phase.

# Add your own branch predictor, data prefetchers, and replacement policy
**Copy an empty template**
```
$ mkdir prefetcher/mypref
$ cp prefetcher/no_l2c/no.cc prefetcher/mypref/mypref.cc
```

**Work on your algorithms with your favorite text editor**
```
$ vim prefetcher/mypref/mypref.cc
```

**Compile and test**
Add your prefetcher to the configuration file.
```
{
    "L2C": {
        "prefetcher": "mypref"
    }
}
```
Note that the example prefetcher is an L2 prefetcher. You might design a prefetcher for a different level.

```
$ ./config.sh <configuration file>
$ make
$ bin/champsim --warmup-instructions 200000000 --simulation-instructions 500000000 600.perlbench_s-210B.champsimtrace.xz
```

# How to create traces

Program traces are available in a variety of locations, however, many ChampSim users wish to trace their own programs for research purposes.
Example tracing utilities are provided in the `tracer/` directory.

# Evaluate Simulation

ChampSim measures the IPC (Instruction Per Cycle) value as a performance metric. <br>
There are some other useful metrics printed out at the end of simulation. <br>

Good luck and be a champion! <br>
