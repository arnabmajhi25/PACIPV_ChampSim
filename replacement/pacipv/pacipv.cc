#include "pacipv.h"

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <stdexcept>

pacipv::pacipv(CACHE* cache) : pacipv(cache, cache->NUM_SET, cache->NUM_WAY) {}

pacipv::pacipv(CACHE* cache, long sets, long ways)
    : replacement(cache), NUM_SET(sets), NUM_WAY(ways), rrpv(static_cast<std::size_t>(sets * ways), MAX_RRPV)
{
  demand_ipv = parse_ipv("PACIPV_DEMAND", demand_ipv);
  prefetch_ipv = parse_ipv("PACIPV_PREFETCH", prefetch_ipv);
  const char* tiebreak = std::getenv("PACIPV_TIEBREAK");
  random_tiebreak = (tiebreak == nullptr || std::string{tiebreak} != "first");
  // Printed so every simulation log records which pair it ran with.
  std::cout << "PACIPV demand_ipv=" << to_string(demand_ipv) << " prefetch_ipv=" << to_string(prefetch_ipv) << std::endl;
}

// ---------------------------------------------------------------------------
// Victim selection. Pick a way with RRPV == MAX_RRPV; if none exists, age the
// whole set (+1 each) until one does. Adding the gap to the oldest block in
// one step is equivalent to repeated increments.
//
// Ties are broken randomly, as in the authors' artifact. Set
// PACIPV_TIEBREAK=first to take the first way instead, which is what ChampSim's
// SRRIP does; use that for the [0,0,0,0,2] equivalence check.
// ---------------------------------------------------------------------------
long pacipv::find_victim(uint32_t, uint64_t, long set, const champsim::cache_block*, champsim::address, champsim::address, access_type)
{
  auto begin = std::next(rrpv.begin(), set * NUM_WAY);
  auto end = std::next(begin, NUM_WAY);

  auto victim = std::max_element(begin, end); // first way with the largest RRPV
  if (*victim < MAX_RRPV) {
    const uint8_t gap = static_cast<uint8_t>(MAX_RRPV - *victim);
    std::for_each(begin, end, [gap](uint8_t& r) { r = static_cast<uint8_t>(r + gap); });
  }
  if (!random_tiebreak)
    return std::distance(begin, victim);

  auto remaining = std::rand() % std::count(begin, end, MAX_RRPV);
  auto chosen = std::find_if(begin, end, [&remaining](uint8_t r) { return r == MAX_RRPV && remaining-- == 0; });
  return std::distance(begin, chosen);
}

// ---------------------------------------------------------------------------
// Insertion: the new block's RRPV comes from ipv[NUM_RRPV] of the IPV that
// matches the access type that caused the fill.
// ---------------------------------------------------------------------------
void pacipv::replacement_cache_fill(uint32_t, long set, long way, champsim::address, champsim::address, champsim::address, access_type type)
{
  rrpv_of(set, way) = ipv_for(type)[NUM_RRPV];
  if (type == access_type::PREFETCH)
    ++prefetch_fills;
  else
    ++demand_fills;
}

// ---------------------------------------------------------------------------
// Promotion: on a hit, RRPV r becomes ipv[r]. Because replacement_cache_fill()
// is defined, ChampSim calls this after every tag check, so misses are ignored
// here (insertion was handled above).
// ---------------------------------------------------------------------------
void pacipv::update_replacement_state(uint32_t, long set, long way, champsim::address, champsim::address, champsim::address, access_type type,
                                      bool hit)
{
  if (!hit)
    return;

  // Every non-prefetch hit, writebacks included, uses the demand IPV. This
  // matches both the authors' artifact and ChampSim's SRRIP.
  uint8_t& r = rrpv_of(set, way);
  r = ipv_for(type)[r];

  if (type == access_type::PREFETCH)
    ++prefetch_hits;
  else if (type == access_type::WRITE)
    ++write_hits;
  else
    ++demand_hits;
}

void pacipv::replacement_final_stats()
{
  std::cout << "PACIPV demand_ipv=" << to_string(demand_ipv) << " prefetch_ipv=" << to_string(prefetch_ipv) << '\n'
            << "PACIPV demand_hits=" << demand_hits << " prefetch_hits=" << prefetch_hits << " write_hits=" << write_hits
            << " demand_fills=" << demand_fills << " prefetch_fills=" << prefetch_fills << std::endl;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
pacipv::ipv_t pacipv::parse_ipv(const char* env_name, const ipv_t& fallback)
{
  const char* s = std::getenv(env_name);
  if (s == nullptr || *s == '\0')
    return fallback;

  ipv_t v{};
  std::stringstream ss{std::string{s}};
  std::string tok;
  std::size_t i = 0;
  while (std::getline(ss, tok, ',')) {
    if (i >= v.size())
      throw std::invalid_argument(std::string{env_name} + ": expected exactly 5 comma-separated values");
    const int x = std::stoi(tok);
    if (x < 0 || x > MAX_RRPV)
      throw std::invalid_argument(std::string{env_name} + ": each value must be in 0..3");
    v[i++] = static_cast<uint8_t>(x);
  }
  if (i != v.size())
    throw std::invalid_argument(std::string{env_name} + ": expected exactly 5 comma-separated values");
  return v;
}

std::string pacipv::to_string(const ipv_t& v)
{
  std::string out = "[";
  for (std::size_t i = 0; i < v.size(); ++i) {
    out += std::to_string(v[i]);
    if (i + 1 < v.size())
      out += ",";
  }
  return out + "]";
}
