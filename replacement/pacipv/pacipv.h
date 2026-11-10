#ifndef REPLACEMENT_PACIPV_H
#define REPLACEMENT_PACIPV_H

// PACIPV: Prefetch Aware Coarse-grained Insertion and Promotion Vectors
// (Mostofi et al., ISCA 2025) for ChampSim's class-based module system.
//
// Two 5-entry vectors over 2-bit RRPVs (0 = re-reference soon, 3 = evict):
//   ipv[0..3] : new RRPV for a block hit while at RRPV 0..3   (promotion)
//   ipv[4]    : RRPV given to a newly filled block            (insertion)
// Demand accesses use demand_ipv; prefetch accesses use prefetch_ipv.
// Victim selection and aging are identical to SRRIP.
//
// The vectors can be overridden at run time (no recompilation needed for the
// design-space sweep):
//   PACIPV_DEMAND="0,1,1,0,3" PACIPV_PREFETCH="0,1,0,0,3" bin/champsim ...

#include <array>
#include <cstdint>
#include <string>
#include <vector>

#include "cache.h"
#include "modules.h"

class pacipv : public champsim::modules::replacement
{
public:
  static constexpr int NUM_RRPV = 4;
  static constexpr uint8_t MAX_RRPV = NUM_RRPV - 1;
  using ipv_t = std::array<uint8_t, NUM_RRPV + 1>;

private:
  long NUM_SET, NUM_WAY;
  std::vector<uint8_t> rrpv;

  // Defaults: best pair reported in the paper for instruction-heavy (CVP) workloads.
  ipv_t demand_ipv{0, 1, 1, 0, 3};
  ipv_t prefetch_ipv{0, 1, 0, 0, 3};

  bool random_tiebreak = true;

  // Statistics
  uint64_t demand_hits = 0, prefetch_hits = 0, write_hits = 0;
  uint64_t demand_fills = 0, prefetch_fills = 0;

  uint8_t& rrpv_of(long set, long way) { return rrpv[static_cast<std::size_t>(set * NUM_WAY + way)]; }
  const ipv_t& ipv_for(access_type type) const { return (type == access_type::PREFETCH) ? prefetch_ipv : demand_ipv; }

  static ipv_t parse_ipv(const char* env_name, const ipv_t& fallback);
  static std::string to_string(const ipv_t& v);

public:
  explicit pacipv(CACHE* cache);
  pacipv(CACHE* cache, long sets, long ways);

  long find_victim(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set, champsim::address ip,
                   champsim::address full_addr, access_type type);

  void replacement_cache_fill(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip,
                              champsim::address victim_addr, access_type type);

  void update_replacement_state(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip,
                                champsim::address victim_addr, access_type type, bool hit);

  void replacement_final_stats();
};

#endif
