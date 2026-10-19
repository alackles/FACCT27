"""Interactive network view, written as one local HTML file.

    uv run python -m facct27.viz data/processed/2026-10-08 --out data/derived/2026-10-08/network.html

Open the file in a browser (it loads d3 from cdnjs; the data stay in the file).
It holds pseudonyms and counts only, but it is built from the corpus: keep it
local, and don't publish or share it.

Clusters are Louvain communities on the undirected, contexts-weighted graph:
exploratory, for looking, not a reported result.
"""

import argparse
import json
import os

import networkx as nx

from facct27 import network
from facct27.collect import read_jsonl

TEMPLATE = os.path.join(os.path.dirname(__file__), "viz.html")


def payload(D, G, seed=0, resolution=1.0):
    comms = nx.community.louvain_communities(G, weight="weight", seed=seed,
                                             resolution=resolution)
    comms = sorted(comms, key=lambda c: (-len(c), min(c)))
    cluster = {v: i for i, c in enumerate(comms, 1) for v in c}
    order = sorted(G, key=lambda v: (-G.degree(v), v))
    index = {v: i for i, v in enumerate(order)}
    return {
        "nodes": [{"id": v, "degree": G.degree(v), "contexts": G.degree(v, weight="weight"),
                   "replied_by": D.in_degree(v), "replied_to": D.out_degree(v),
                   "cluster": cluster[v], "mod": bool(G.nodes[v].get("mod"))}
                  for v in order],
        "links": [[index[u], index[v], w] for u, v, w in G.edges(data="weight")],
        "clusters": [{"id": i, "size": len(c)} for i, c in enumerate(comms, 1)],
        "meta": {"louvain_seed": seed, "resolution": resolution},
    }


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
    a = p.parse_args(argv)

    posts = read_jsonl(os.path.join(a.snapshot, "posts.jsonl"))
    comments = read_jsonl(os.path.join(a.snapshot, "comments.jsonl"))
    D, _ = network.build(posts, comments, a.layer, a.start, a.end)
    G = network.undirected(D, a.weight)
    data = payload(D, G, a.seed, a.resolution)
    data["meta"].update(layer=a.layer, weight=a.weight, start=a.start, end=a.end)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(render(data))
    sizes = [c["size"] for c in data["clusters"]]
    print(json.dumps({"out": a.out, "nodes": len(data["nodes"]), "links": len(data["links"]),
                      "clusters": len(sizes), "largest_clusters": sizes[:10]}, indent=2))


if __name__ == "__main__":
    main()
