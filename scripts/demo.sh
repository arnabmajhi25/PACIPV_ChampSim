#!/bin/bash
# Live demo of the equivalence test (about 12 minutes on our laptop: start it before the TA arrives).
#   bash scripts/demo.sh            -> equivalence test on srv_9
#   bash scripts/demo.sh compare    -> LRU vs true SRRIP vs PACIPV on srv_32
cd "$(dirname "$0")/.." || exit 1
TRACES=${TRACES:-$HOME/pacipv_traces/public/srv}
W=5000000; S=10000000

run() { # label, then command; prints LLC counts and IPC from the measured region
  local label=$1; shift
  "$@" --warmup-instructions $W --simulation-instructions $S "$TRACE" > "/tmp/demo_${label// /_}.log" 2>&1
  awk -v l="$label" '/Region of Interest/{p=1} p && /LLC TOTAL/{a=$4;h=$6;m=$8} p && /cumulative IPC/{ipc=$5}
       END{printf "%-34s %9s %8s %8s %8s\n", l, a, h, m, ipc}' "/tmp/demo_${label// /_}.log"
}
header() { printf "\n%-34s %9s %8s %8s %8s\n" "Configuration" "LLC acc" "hits" "misses" "IPC"; }

if [ "$1" = "compare" ]; then
  TRACE=$TRACES/srv_32.champsimtrace.xz
  echo "Trace srv_32, ported machine (EIP, Berti, TAGE-SC-L), ${W} warmup + ${S} measured"
  header
  run "LRU" bin/champsim_port_lru &
  PACIPV_TIEBREAK=first PACIPV_DEMAND=0,0,0,0,2 PACIPV_PREFETCH=0,0,0,0,2 run "True SRRIP [0,0,0,0,2]" bin/champsim_port_pacipv &
  run "PACIPV [0,1,1,0,3]/[0,1,0,0,3]" bin/champsim_port_pacipv &
  wait
  exit 0
fi

TRACE=$TRACES/srv_9.champsimtrace.xz
echo "Equivalence test on srv_9, ${W} warmup + ${S} measured (runs in parallel, about 12 min)"
echo "Expect: rows 1 and 2 identical (ChampSim SRRIP inserts at 3), rows 3 and 4 identical (true SRRIP)."
header
run "1 ChampSim SRRIP" bin/champsim_srrip &
PACIPV_TIEBREAK=first PACIPV_DEMAND=0,0,0,0,3 PACIPV_PREFETCH=0,0,0,0,3 run "2 PACIPV [0,0,0,0,3] first-way" bin/champsim_pacipv &
PACIPV_TIEBREAK=first PACIPV_DEMAND=0,0,0,0,2 PACIPV_PREFETCH=0,0,0,0,2 run "3 PACIPV [0,0,0,0,2] first-way" bin/champsim_pacipv &
[ -x "$HOME/PACIPV_mj/bin/champsim_srrip" ] && run "4 ChampSim SRRIP with fill fix" "$HOME/PACIPV_mj/bin/champsim_srrip" &
wait
