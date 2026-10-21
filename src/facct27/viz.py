"""Interactive network view, written as one local HTML file.

    uv run python -m facct27.viz data/processed/2026-10-08 --out data/derived/2026-10-08/network.html

Open the file in a browser (it loads d3 from cdnjs; the data stay in the file).
It holds pseudonyms and counts only, but it is built from the corpus: keep it
local, and don't publish or share it.

Groups are Louvain communities on the undirected, contexts-weighted graph (the
default), or Kirkley in-hubs under --groups ER / CM: clicking a hub highlights it and
the people who replied to it. Node order, and so the layout, is the same in every
version. Exploratory, for looking, not a reported result.
"""

import argparse
import json
import os

import networkx as nx

from facct27 import kirkley, network
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


def hub_payload(D, G, encoding="CM", weight="contexts"):
    """Kirkley in-hubs (weighted in-degree, multigraph encodings) as groups: each hub
    with the people who replied to it, since their replies are what make it a hub."""
    nodes, links, index = base(D, G)
    r = kirkley.scan(dict(D.in_degree(weight=weight)), weighted=True)
    hubs = [{"id": v, "in_degree": k, "repliers": D.in_degree(v),
             "members": sorted([index[v]] + [index[u] for u in D.predecessors(v)])}
            for v, k in r[f"hubs_{encoding}"]]
    return {"nodes": nodes, "links": links, "hubs": hubs,
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
    a = p.parse_args(argv)

    posts = read_jsonl(os.path.join(a.snapshot, "posts.jsonl"))
    comments = read_jsonl(os.path.join(a.snapshot, "comments.jsonl"))
    D, _ = network.build(posts, comments, a.layer, a.start, a.end)
    G = network.undirected(D, a.weight)
    data = (payload(D, G, a.seed, a.resolution) if a.groups == "louvain"
            else hub_payload(D, G, a.groups, a.weight))
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
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
