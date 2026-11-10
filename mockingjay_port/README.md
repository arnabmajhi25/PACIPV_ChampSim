# Mockingjay port (not built by default)

Mockingjay (Shah et al., HPCA 2022) was used only as a comparison policy. The code is from
[Setu-Gupta/Wrong-Path-ChampSim](https://github.com/Setu-Gupta/Wrong-Path-ChampSim) (Apache-2.0).
We built it in a separate copy of this repository, because the changes it needs would also change the
LRU, SRRIP and PACIPV binaries used for the main results.

| File | What it is |
|---|---|
| `mockingjay.cc` | The policy, with our changes marked `// port:`. LLC geometry is fixed at 4096 sets x 12 ways, 1 CPU |
| `port_mockingjay.json` | Same machine as `port_pacipv.json`, with `"replacement": "mockingjay"` |
| `fill_fix_cache_h.diff` | Fix for `inc/cache.h`: a policy without `replacement_cache_fill()` is told about fills. This is also the ChampSim SRRIP fix |
| `header_guard_ooo_cpu_h.diff` | Workaround in `inc/ooo_cpu.h` for the shared `module_decl.inc` include guard |
| `header_guard_tage_sc_l_cc.diff` | Same workaround in `branch/tage_sc_l/tage_sc_l.cc` |

## Build (in a separate copy of the repository)

```
cp -r PACIPV_ChampSim PACIPV_mj && cd PACIPV_mj
mkdir -p replacement/mockingjay && touch replacement/mockingjay/__legacy__
cp mockingjay_port/mockingjay.cc replacement/mockingjay/
patch inc/cache.h                 < mockingjay_port/fill_fix_cache_h.diff
patch inc/ooo_cpu.h               < mockingjay_port/header_guard_ooo_cpu_h.diff
patch branch/tage_sc_l/tage_sc_l.cc < mockingjay_port/header_guard_tage_sc_l_cc.diff
./config.sh mockingjay_port/port_mockingjay.json && make    # bin/champsim_port_mockingjay
./config.sh srrip_config.json && make                       # bin/champsim_srrip with the fill fix (row 4 of scripts/demo.sh)
```

The `__legacy__` file marks Mockingjay as an old-API module, like the ported EIP, Berti and TAGE-SC-L.
