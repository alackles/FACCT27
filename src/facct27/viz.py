"""Interactive network view, written as one local HTML file.

    uv run python -m facct27.viz data/processed/2026-10-08 --out data/derived/2026-10-08/network.html

Open the file in a browser (it loads d3 from cdnjs; the data stay in the file).
It holds pseudonyms and counts only, but it is built from the corpus: keep it
local, and don't publish or share it.

Groups are Louvain communities on the undirected, contexts-weighted graph (the
default), or Kirkley in-hubs under --groups ER / CM: clicking a hub highlights it and
the people who replied to it. Node order, and so the layout, is the same in every
version. With --months, a hub view also steps through calendar months (the windows
of facct27.hubs) on that fixed layout: each month shows who and which ties were
active, and that month's hubs. Exploratory, for looking, not a reported result.
"""

import argparse
import json
import os

import networkx as nx

from facct27 import kirkley, network
from facct27.hubs import months as month_windows
from facct27.collect import read_jsonl

TEMPLATE = os.path.join(os.path.dirname(__file__), "viz.html")


def base(D, G):
    """Nodes (sorted by degree) and links shared by every version, so the in-browser
    layout, which depends only on this order, puts each person in the same place."""
    order = sorted(G, key=lambda v: (-G.degree(v), v))
    index = {v: i for i, v in enumerate(order)}
    nodes = [{"id": v, "degree": G.degree(v), "contexts": G.degree(v, weight="weight"),
              "replied_by": D.in_degree(v), "replied_to": D.out_degree(v),
              "mod": bool(G.nodes[v].get("mod"))} for v in order]
    links = [[index[u], index[v], w] for u, v, w in G.edges(data="weight")]
    return nodes, links, index


def payload(D, G, seed=0, resolution=1.0):
    nodes, links, _ = base(D, G)
    comms = nx.community.louvain_communities(G, weight="weight", seed=seed,
                                             resolution=resolution)
    comms = sorted(comms, key=lambda c: (-len(c), min(c)))
    cluster = {v: i for i, c in enumerate(comms, 1) for v in c}
    for n in nodes:
        n["cluster"] = cluster[n["id"]]
    return {
        "nodes": nodes, "links": links,
        "clusters": [{"id": i, "size": len(c)} for i, c in enumerate(comms, 1)],
        "meta": {"mode": "louvain", "louvain_seed": seed, "resolution": resolution},
    }


def hub_list(D, encoding, weight, index):
    """Kirkley in-hubs of D (weighted in-degree, multigraph encodings), each with the
    people who replied to it, since their replies are what make it a hub."""
    r = kirkley.scan(dict(D.in_degree(weight=weight)), weighted=True)
    hubs = [{"id": v, "in_degree": k, "repliers": D.in_degree(v),
             "members": sorted([index[v]] + [index[u] for u in D.predecessors(v)])}
            for v, k in r[f"hubs_{encoding}"]]
    return hubs, r


def first_hubs(views, k):
    """The first k people to be hubs: months in order, each month's hubs in rank
    (in-degree) order, so a month that makes several people hubs at once gives the
    earlier places to its higher-ranked ones."""
    seen = {}
    for m in views:
        for h in m["hubs"]:
            if len(seen) < k and h["id"] not in seen:
                seen[h["id"]] = m["label"]
    return [{"id": v, "first": label} for v, label in seen.items()]


def hub_payload(D, G, encoding="CM", weight="contexts", months=(), track=0):
    """Kirkley in-hubs as groups. `months` is [(label, start, end, D_month)]: each
    becomes a view over the same nodes and links (so the same layout), listing which
    people and ties are active that month, their monthly counts, and that month's hubs.
    `track` > 0 gives the first `track` people to become hubs a fixed color each."""
    nodes, links, index = base(D, G)
    hubs, r = hub_list(D, encoding, weight, index)
    link_at = {frozenset((nodes[s]["id"], nodes[t]["id"])): i
               for i, (s, t, _) in enumerate(links)}
    views = []
    for label, start, end, Dm in months:
        Gm = network.undirected(Dm, weight)
        m_hubs, m = hub_list(Dm, encoding, weight, index)
        views.append({
            "label": label, "start": start, "end": end,
            "h": m[f"h_{encoding}"], "in_degree_total": m["M"], "hubs": m_hubs,
            # [index, connections, thread contexts, replied to by, replied to, mod]
            "nodes": [[index[v], Gm.degree(v), Gm.degree(v, weight="weight"),
                       Dm.in_degree(v), Dm.out_degree(v), int(bool(Dm.nodes[v].get("mod")))]
                      for v in Dm],
            "links": [[link_at[frozenset((u, v))], w] for u, v, w in Gm.edges(data="weight")],
        })
    return {"nodes": nodes, "links": links, "hubs": hubs, "months": views,
            "tracked": first_hubs(views, track),
            "meta": {"mode": "hubs", "encoding": encoding, "h": r[f"h_{encoding}"],
                     "in_degree_total": r["M"]}}


def render(data):
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    return html.replace("__DATA__", blob)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("snapshot", help="processed snapshot with posts.jsonl, comments.jsonl")
    p.add_argument("--out", required=True, help="path of the HTML file to write")
    p.add_argument("--layer", choices=["reply", "mention"], default="reply")
    p.add_argument("--weight", choices=["contexts", "replies"], default="contexts")
    p.add_argument("--start", type=network.epoch, help="UTC date, inclusive (YYYY-MM-DD)")
    p.add_argument("--end", type=network.epoch, help="UTC date, exclusive (YYYY-MM-DD)")
    p.add_argument("--seed", type=int, default=0, help="Louvain seed")
    p.add_argument("--resolution", type=float, default=1.0, help="Louvain resolution")
    p.add_argument("--groups", choices=["louvain", "ER", "CM"], default="louvain",
                   help="sidebar groups: Louvain clusters, or Kirkley in-hubs (ER or CM)")
    p.add_argument("--months", action="store_true",
                   help="hub views only: add a month selector over the fixed whole-period layout")
    p.add_argument("--track", type=int, default=0, metavar="K",
                   help="with --months: color the first K people to become hubs (max 7)")
    a = p.parse_args(argv)
    if a.months and (a.groups == "louvain" or a.start or a.end):
        p.error("--months needs --groups ER or CM, and no --start/--end")
    if a.track and not (a.months and 0 < a.track <= 7):
        p.error("--track needs --months, and K from 1 to 7 (one color each)")

    posts = read_jsonl(os.path.join(a.snapshot, "posts.jsonl"))
    comments = read_jsonl(os.path.join(a.snapshot, "comments.jsonl"))
    D, _ = network.build(posts, comments, a.layer, a.start, a.end)
    G = network.undirected(D, a.weight)
    months = [(label, start, end, network.build(posts, comments, a.layer, start, end)[0])
              for label, start, end in month_windows(comments)] if a.months else ()
    data = (payload(D, G, a.seed, a.resolution) if a.groups == "louvain"
            else hub_payload(D, G, a.groups, a.weight, months, a.track))
    data["meta"].update(layer=a.layer, weight=a.weight, start=a.start, end=a.end)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(render(data))
    summary = {"out": a.out, "nodes": len(data["nodes"]), "links": len(data["links"])}
    if a.groups == "louvain":
        sizes = [c["size"] for c in data["clusters"]]
        summary.update(clusters=len(sizes), largest_clusters=sizes[:10])
    else:
        summary.update(encoding=a.groups, hubs=len(data["hubs"]),
                       top_hubs=[[h["id"], h["in_degree"]] for h in data["hubs"][:10]])
        if data["tracked"]:
            summary.update(tracked=[[t["id"], t["first"]] for t in data["tracked"]])
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
