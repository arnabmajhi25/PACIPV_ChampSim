"""Step-by-step demo of one 4-way cache set under PACIPV and SRRIP.

Mirrors replacement/pacipv/pacipv.cc: victim = first way at RRPV 3, aging the
whole set by the gap when none is at 3; fill sets RRPV = V[4]; a hit at RRPV r
sets it to V[r]. Prefetch accesses use the prefetch vector.

    python scripts/ipv_demo.py
"""

PACIPV = {'demand': [0, 1, 1, 0, 3], 'prefetch': [0, 1, 0, 0, 3]}
SRRIP = {'demand': [0, 0, 0, 0, 2], 'prefetch': [0, 0, 0, 0, 2]}

START = [('A', 0), ('B', 2), ('C', 1), ('D', 1)]
EVENTS = [('demand', 'E'), ('demand', 'C'), ('prefetch', 'D'), ('demand', 'F')]


def show(ways):
    return '  '.join(f'{b}:{r}' for b, r in ways)


def access(ways, vectors, kind, block):
    v = vectors[kind]
    for i, (b, r) in enumerate(ways):
        if b == block:  # hit: promotion
            ways[i] = (b, v[r])
            return f'{kind} hit on {block}: RRPV {r} -> {v[r]}'
    gap = 3 - max(r for _, r in ways)
    if gap:  # nobody at 3: age the whole set
        ways[:] = [(b, r + gap) for b, r in ways]
    i = next(i for i, (_, r) in enumerate(ways) if r == 3)
    victim = ways[i][0]
    ways[i] = (block, v[4])  # fill: insertion
    aged = f'aged set by {gap}, ' if gap else ''
    return f'{kind} miss on {block}: {aged}evict {victim}, insert {block} at {v[4]}'


for name, vectors in (('PACIPV  demand [0,1,1,0,3]  prefetch [0,1,0,0,3]', PACIPV), ('SRRIP   [0,0,0,0,2]', SRRIP)):
    ways = list(START)
    print(f'\n{name}\n  {"start":<58} {show(ways)}')
    for kind, block in EVENTS:
        msg = access(ways, vectors, kind, block)
        print(f'  {msg:<58} {show(ways)}')
