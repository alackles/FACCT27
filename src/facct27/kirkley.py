"""Hub identification by minimum description length (Kirkley 2024, PRE 109, 034310).

A node set is the hub set if transmitting the edges pointing at it separately gives
the shortest description of the graph. Only the degree sequence matters, and the best
set of size h is always the h highest-degree nodes (Appendix B), so the search is a
scan down the sorted degrees. Description lengths are in bits, as in the paper.
Equation numbers below are the paper's; conventions are in docs/DECISIONS.md.
"""

import math
from collections import Counter

LN2 = math.log(2)


def logchoose(n, k):
    """log2 of the binomial coefficient C(n, k); 0 for k = 0."""
    if k <= 0 or n <= 0:
        return 0.0
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)) / LN2


def logmultiset(n, k):
    """log2 of ((n, k)): ways to place k items in n slots, repeats allowed."""
    return logchoose(n + k - 1, k)


def scan(degrees, weighted=True):
    """Hubs under the ER and CM encodings for a {node: degree} mapping.

    weighted=True uses the multigraph encodings (Eqs. 6-9), for integer weights;
    False uses the simple-graph ones (Eqs. 1-4). Nodes of equal degree enter the hub
    set together, and the whole range of h is scanned for the global minimum.
    """
    N, M = len(degrees), sum(degrees.values())
    ranked = sorted(degrees, key=lambda v: (-degrees[v], v))
    if M == 0 or N < 2:
        return {"N": N, "M": M, "empty": True, "er_wins": False, "k_star": None,
                **{f"{x}_{enc}": v for enc in ("ER", "CM")
                   for x, v in (("L0", 0.0), ("L", 0.0), ("h", 0), ("eta", 1.0))},
                "hubs_ER": [], "hubs_CM": []}

    if weighted:
        edges = lambda n, m: logmultiset(n * N, m)  # sources per target: N (self-loops)
        per_node = lambda k: logmultiset(N, k)
        L0 = {"ER": logmultiset(N * N, M)}                                       # (6)
    else:
        edges = lambda n, m: logchoose(n * (N - 1), m)
        per_node = lambda k: logchoose(N - 1, k)
        L0 = {"ER": logchoose(N * (N - 1), M)}                                   # (1)
    L0["CM"] = logmultiset(N, M) + sum(per_node(k) for k in degrees.values())  # (2)/(7)

    best = {enc: (L0[enc], 0) for enc in L0}
    h = Mh = hub_terms = 0
    for k, count in sorted(Counter(degrees.values()).items(), reverse=True):
        h += count
        Mh += count * k
        hub_terms += count * per_node(k)
        shared = math.log2(N) + math.log2(M) + logchoose(N, h)
        rest = edges(N - h, M - Mh)
        L = {"ER": shared + edges(h, Mh) + rest,                                 # (3)/(8)
             "CM": shared + logmultiset(h, Mh) + hub_terms + rest}               # (4)/(9)
        for enc in L:
            if L[enc] < best[enc][0]:
                best[enc] = (L[enc], h)

    out = {"N": N, "M": M, "empty": False}
    for enc, (L, h) in best.items():
        out.update({f"L0_{enc}": L0[enc], f"L_{enc}": L, f"h_{enc}": h,
                    f"eta_{enc}": L / max(L0.values()),                          # (5)/(10)
                    f"hubs_{enc}": [[v, degrees[v]] for v in ranked[:h]]})
    out["er_wins"] = out["L_ER"] < out["L_CM"]
    out["k_star"] = out["hubs_CM"][-1][1] if out["hubs_CM"] else None
    return out
