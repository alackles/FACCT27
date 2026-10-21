"""Reply graph and data-driven pole candidates from a processed snapshot.

    uv run python -m facct27.network data/processed/2026-10-08 --out data/derived/2026-10-08

Uses author, id, parent, thread, time and flag fields, plus text only for u/C…
mentions under --layer mention. Prints counts and pseudonyms only, so the report
is safe to paste. Writes graph.graphml, cuts.json and report.json to --out, plus
gomory_hu.json under --cuts tree.
Edge rules are recorded in docs/DECISIONS.md (2026-10-19).
"""

import argparse
import itertools
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone

import networkx as nx
from networkx.algorithms.flow import edmonds_karp

from facct27 import kirkley
from facct27.collect import read_jsonl
from facct27.pseudonymize import SYSTEM_ACCOUNTS, TEXT_FIELDS

INSTANT = "text_unavailable_at_collection"  # text already gone at first fetch
MOD = "moderator"
MENTION = re.compile(r"(?<![\w/])u/(C\d+)\b")


def index(posts, comments):
    """fullname -> item, each tagged with the thread it belongs to."""
    items = {f"t3_{p['id']}": {**p, "thread": f"t3_{p['id']}"} for p in posts}
    items.update({f"t1_{c['id']}": {**c, "thread": c["link_id"]} for c in comments})
    return items


def build(posts, comments, layer="reply", start=None, end=None,
          needs_review=True, mod_actions=True):
    """Directed graph in which u -> v means u replied to v (or mentioned v).

    Edge attributes: threads (set), contexts (= len(threads)), replies, mod (how many
    were moderator-distinguished), needs_review (how many await review). Returns the
    graph and a Counter of what each rule dropped, checked in the order written.
    """
    items = index(posts, comments)
    replied_to = {c["parent_id"] for c in comments}

    def in_window(x):
        t = x["created_utc"]
        return (start is None or t >= start) and (end is None or t < end)

    D = nx.DiGraph()
    n = Counter()
    for name, x in items.items():
        if layer == "reply" and name.startswith("t3_"):
            continue
        n["considered"] += 1
        u = x.get("author")
        is_mod = x.get("distinguished") == MOD
        if not in_window(x):
            n["outside_window"] += 1
        elif x.get("excluded_reason") == INSTANT and name not in replied_to:
            n["instant_removal_unseen"] += 1
        elif u is None:
            n["source_no_author"] += 1
        elif u in SYSTEM_ACCOUNTS:
            n["source_system_account"] += 1
        elif x.get("needs_review") and not needs_review:
            n["needs_review_excluded"] += 1
        elif is_mod and not mod_actions:
            n["mod_action_excluded"] += 1
        elif layer == "reply":
            parent = items.get(x["parent_id"])
            if parent is None:
                n["parent_missing"] += 1
            elif parent.get("author") is None:
                n["parent_no_author"] += 1
            elif parent["author"] in SYSTEM_ACCOUNTS:
                n["parent_system_account"] += 1
            else:
                add(D, n, u, parent["author"], x, is_mod)
        else:
            text = " ".join(x.get(f) or "" for f in TEXT_FIELDS)
            for v in dict.fromkeys(MENTION.findall(text)):  # once per item
                add(D, n, u, v, x, is_mod)

    mods = {x.get("author") for x in items.values()
            if x.get("distinguished") == MOD and in_window(x)}
    for v in D:
        D.nodes[v]["mod"] = v in mods
    for _, _, e in D.edges(data=True):
        e["contexts"] = len(e["threads"])
    authors = {x.get("author") for x in items.values() if in_window(x)}
    D.graph["authors_without_edges"] = len(authors - set(D) - SYSTEM_ACCOUNTS - {None})
    return D, n


def add(D, n, u, v, x, is_mod):
    if u == v:
        n["self_loop"] += 1
        return
    if not D.has_edge(u, v):
        D.add_edge(u, v, threads=set(), replies=0, mod=0, needs_review=0)
    e = D[u][v]
    e["threads"].add(x["thread"])
    e["replies"] += 1
    e["mod"] += is_mod
    e["needs_review"] += bool(x.get("needs_review"))
    n["interactions"] += 1


def undirected(D, weight="contexts"):
    """Symmetrize. A pair's contexts are the threads they interacted in, either way."""
    G = nx.Graph()
    G.add_nodes_from(D.nodes(data=True))
    for u, v, e in D.edges(data=True):
        if G.has_edge(u, v):
            g = G[u][v]
            g["threads"] |= e["threads"]
            for k in ("replies", "mod", "needs_review"):
                g[k] += e[k]
        else:
            G.add_edge(u, v, threads=set(e["threads"]),
                       **{k: e[k] for k in ("replies", "mod", "needs_review")})
    for _, _, g in G.edges(data=True):
        g["contexts"] = len(g["threads"])
        g["weight"] = g[weight]
        g["distance"] = 1 / g["weight"]  # stronger tie, shorter path
    return G


def centrality(D, G, weight="contexts", betweenness_sample=None, seed=0):
    """Freeman's three (degree as weighted strength, betweenness, closeness),
    plus in-strength: how much the community replies to someone."""
    return {
        "strength": dict(G.degree(weight="weight")),
        "in_strength": dict(D.in_degree(weight=weight)),
        "betweenness": nx.betweenness_centrality(G, weight="distance",
                                                 k=betweenness_sample, seed=seed),
        "closeness": nx.closeness_centrality(G, distance="distance"),
    }


def top(scores, k):
    return sorted(scores, key=lambda v: (-scores[v], v))[:k]


def cut_pairs(G, poles):
    """Zachary-style minimum cut between each pair of poles; capacity = edge weight.

    no_better_than_isolating: the cut costs as much as cutting the weaker pole off
    alone, so it says little about how the community divides. Reported, not filtered.
    """
    strength = dict(G.degree(weight="weight"))
    rows = []
    for s, t in itertools.combinations(sorted(poles), 2):
        row = {"s": s, "t": t, "s_strength": strength[s], "t_strength": strength[t]}
        if not nx.has_path(G, s, t):
            row.update(connected=False)
        else:
            H = G.subgraph(nx.node_connected_component(G, s))
            value, (S, T) = nx.minimum_cut(H, s, t, capacity="weight")
            row.update(connected=True, cut=value, s_side=len(S), t_side=len(T),
                       no_better_than_isolating=value >= min(strength[s], strength[t]),
                       s_members=sorted(S), t_members=sorted(T))
        rows.append(row)
    return rows


def gomory_hu(G):
    """Gomory-Hu forest of G: one tree per connected component, edge weight = cut.

    The min s-t cut in G is the lightest edge on the tree path from s to t, and
    deleting that edge splits the tree into a minimum cut. Needs n - 1 max-flows,
    not one per pair. capacity must be named: networkx reads a missing capacity
    attribute as infinite.
    """
    F = nx.Graph()
    for nodes in nx.connected_components(G):
        if len(nodes) > 1:
            F.update(nx.gomory_hu_tree(G.subgraph(nodes), capacity="weight",
                                       flow_func=edmonds_karp))
    return F


def _rooted(F):
    """Per node: component root, entry/exit order and subtree size, rooting each tree
    at its smallest node, so membership in a subtree is an interval test."""
    root, tin, tout, size = {}, {}, {}, {}
    clock = 0
    for r in sorted(min(c) for c in nx.connected_components(F)):
        stack, seen = [(r, iter(sorted(F[r])))], {r}
        root[r], tin[r] = r, clock
        clock += 1
        while stack:
            v, children = stack[-1]
            c = next((c for c in children if c not in seen), None)
            if c is None:
                stack.pop()
                tout[v] = clock
                size[v] = 1 + sum(size[c] for c in F[v] if tin[c] > tin[v])
            else:
                seen.add(c)
                root[c], tin[c] = r, clock
                clock += 1
                stack.append((c, iter(sorted(F[c]))))
    return root, tin, tout, size


def _lightest_edges(F, s):
    """For every node t in s's tree: (cut, u, v), the lightest edge on the path from
    s, taking the one nearest s when several tie."""
    best, stack = {s: None}, [s]
    while stack:
        x = stack.pop()
        for y, e in F[x].items():
            if y not in best:
                w = e["weight"]
                best[y] = (w, x, y) if best[x] is None or w < best[x][0] else best[x]
                stack.append(y)
    return best


def tree_cuts(F, poles, strength):
    """cut_pairs rows from a Gomory-Hu forest, without member lists.

    One traversal per pole instead of one max-flow per pair. Side sizes come from
    subtree sizes: deleting edge (u, v) cuts off the subtree of whichever end is
    the child in the rooted tree.
    """
    root, tin, tout, size = _rooted(F)
    comp = {r: sum(1 for v in root if root[v] == r) for r in set(root.values())}
    rows = []
    poles = sorted(poles)
    for i, s in enumerate(poles):
        best = _lightest_edges(F, s) if s in F else {}
        for t in poles[i + 1:]:
            row = {"s": s, "t": t, "s_strength": strength[s], "t_strength": strength[t]}
            if t not in best:
                row.update(connected=False)
            else:
                cut, u, v = best[t]
                child = v if tin[v] > tin[u] else u
                below = tin[child] <= tin[s] < tout[child]
                s_side = size[child] if below else comp[root[s]] - size[child]
                row.update(connected=True, cut=cut, s_side=s_side,
                           t_side=comp[root[s]] - s_side,
                           no_better_than_isolating=cut >= min(strength[s], strength[t]))
            rows.append(row)
    return rows


def tree_partition(F, s, t):
    """(s side, t side) of the minimum s-t cut that the forest encodes."""
    cut, u, v = _lightest_edges(F, s)[t]
    H = F.copy()
    H.remove_edge(u, v)
    S = nx.node_connected_component(H, s)
    return sorted(S), sorted(nx.node_connected_component(H, t))


def kirkley_candidates(D, weight="contexts"):
    """CM in-hubs (Kirkley 2024) on in-degree weighted by `weight`, as pole candidates."""
    r = kirkley.scan(dict(D.in_degree(weight=weight)), weighted=True)
    info = {"rule": "kirkley", "h": r["h_CM"], "hubs": r["hubs_CM"], "er_wins": r["er_wins"]}
    if r["h_CM"] < 2:
        info["note"] = "no candidate pairs"
    return [v for v, _ in r["hubs_CM"]], info


def analyze(posts, comments, layer="reply", weight="contexts", start=None, end=None,
            needs_review=True, mod_actions=True, k=5, betweenness_sample=None,
            candidates="topk", cuts="pairs"):
    D, counts = build(posts, comments, layer, start, end, needs_review, mod_actions)
    G = undirected(D, weight)
    scores = centrality(D, G, weight, betweenness_sample)
    for name, s in scores.items():
        nx.set_node_attributes(D, s, name)
    tops = {name: top(s, k) for name, s in scores.items()}
    if candidates == "kirkley":
        poles, chosen = kirkley_candidates(D, weight)
    else:
        poles, chosen = set().union(*tops.values()), {"rule": "topk", "k": k}
    if cuts == "tree":
        forest = gomory_hu(G)
        rows = tree_cuts(forest, poles, dict(G.degree(weight="weight")))
    else:
        forest, rows = None, cut_pairs(G, poles)
    sizes = sorted((len(c) for c in nx.connected_components(G)), reverse=True)
    report = {
        "params": {"layer": layer, "weight": weight, "start": start, "end": end,
                   "needs_review": needs_review, "mod_actions": mod_actions, "top_k": k,
                   "betweenness_sample": betweenness_sample, "candidates": candidates,
                   "cuts": cuts},
        "edge_rules": dict(sorted(counts.items())),
        "graph": {"nodes": D.number_of_nodes(), "directed_edges": D.number_of_edges(),
                  "undirected_edges": G.number_of_edges(), "components": len(sizes),
                  "largest_component": sizes[0] if sizes else 0,
                  "mods": sum(m for _, m in D.nodes(data="mod")),
                  "authors_without_edges": D.graph["authors_without_edges"]},
        "candidates": chosen,
        "top": {name: [[v, round(scores[name][v], 6), D.nodes[v]["mod"]] for v in vs]
                for name, vs in tops.items()},
        "cut_summary": {
            "method": cuts, "pairs": len(rows),
            "connected": sum(1 for c in rows if c["connected"]),
            "degenerate": sum(1 for c in rows if c.get("no_better_than_isolating")),
            "listed": "all pairs" if cuts == "pairs" else "non-degenerate pairs only"},
        "cuts": [{k: v for k, v in c.items() if not k.endswith("_members")} for c in rows
                 if cuts == "pairs" or (c["connected"] and not c["no_better_than_isolating"])],
    }
    if forest is not None:
        D.graph["gomory_hu"] = forest
    return D, report, rows


def write(out, D, report, cuts):
    os.makedirs(out, exist_ok=True)
    H = D.copy()
    H.graph.pop("gomory_hu", None)
    for _, _, e in H.edges(data=True):
        del e["threads"]  # GraphML has no sets; contexts carries the count
    nx.write_graphml(H, os.path.join(out, "graph.graphml"))
    outputs = [("report.json", report), ("cuts.json", cuts)]
    if "gomory_hu" in D.graph:
        outputs.append(("gomory_hu.json", sorted([min(u, v), max(u, v), w] for u, v, w
                                                in D.graph["gomory_hu"].edges(data="weight"))))
    for name, obj in outputs:
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1)


def epoch(day):
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("snapshot", help="processed snapshot with posts.jsonl, comments.jsonl")
    p.add_argument("--out", required=True)
    p.add_argument("--layer", choices=["reply", "mention"], default="reply")
    p.add_argument("--weight", choices=["contexts", "replies"], default="contexts")
    p.add_argument("--start", type=epoch, help="UTC date, inclusive (YYYY-MM-DD)")
    p.add_argument("--end", type=epoch, help="UTC date, exclusive (YYYY-MM-DD)")
    p.add_argument("--exclude-needs-review", action="store_true")
    p.add_argument("--exclude-mod-actions", action="store_true")
    p.add_argument("--top", type=int, default=5, help="candidates per centrality measure")
    p.add_argument("--candidates", choices=["topk", "kirkley"], default="topk",
                   help="pole candidates: top-k per measure, or Kirkley CM in-hubs")
    p.add_argument("--cuts", choices=["pairs", "tree"], default="pairs",
                   help="one max-flow per pair, or all pairs from a Gomory-Hu tree "
                        "(writes gomory_hu.json; no member lists)")
    p.add_argument("--betweenness-sample", type=int,
                   help="approximate betweenness from this many sources (default: exact)")
    a = p.parse_args(argv)

    began = time.time()
    posts = read_jsonl(os.path.join(a.snapshot, "posts.jsonl"))
    comments = read_jsonl(os.path.join(a.snapshot, "comments.jsonl"))
    D, report, cuts = analyze(posts, comments, a.layer, a.weight, a.start, a.end,
                              not a.exclude_needs_review, not a.exclude_mod_actions,
                              a.top, a.betweenness_sample, a.candidates, a.cuts)
    report = {"snapshot": a.snapshot, **report, "seconds": round(time.time() - began, 1)}
    write(a.out, D, report, cuts)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
