"""Synthetic processed snapshot with planted structure and known answers.

    uv run python -m facct27.toy data/toy
    uv run python -m facct27.network data/toy --out data/toy/network

Every record is invented. Two communities form around hubs C1001 and C2001, joined
by a few cross-community replies, and every edge case the graph rules handle is
planted in known numbers (written to truth.json). Record shapes follow the
processed layer written by pseudonymize.py.
"""

import argparse
import json
import os
import random
from collections import Counter

from facct27.collect import write_jsonl

INSTANT = "text_unavailable_at_collection"


class Toy:
    def __init__(self, seed=0, start=1_740_787_200):  # 2025-03-01 UTC
        self.rng = random.Random(seed)
        self.t = start
        self.posts, self.comments = [], []
        self.thread, self.author = {}, {}

    def _item(self, author, fields):
        self.t += self.rng.randint(60, 3600)
        return {"id": f"x{len(self.posts) + len(self.comments) + 1}", "author": author,
                "created_utc": self.t, "distinguished": None, "removal_type": None,
                "excluded_reason": None, "needs_review": False, **fields}

    def post(self, author, **kw):
        x = self._item(author, {"title": "toy", "selftext": "toy", **kw})
        name = f"t3_{x['id']}"
        self.posts.append(x)
        self.thread[name], self.author[name] = name, author
        return name

    def comment(self, author, parent, **kw):
        link = self.thread.get(parent) or kw.pop("link_id")
        x = self._item(author, {"body": "toy", **kw, "parent_id": parent, "link_id": link})
        name = f"t1_{x['id']}"
        self.comments.append(x)
        self.thread[name], self.author[name] = link, author
        return name


def generate(seed=0, members=30, hub_threads=12):
    """Return (posts, comments, truth) for a two-community toy snapshot."""
    toy = Toy(seed)
    rng = toy.rng
    a, b = hubs = ("C1001", "C2001")
    side = {h: [f"C{int(h[1:]) + i}" for i in range(1, members + 1)] for h in hubs}
    hub_posts, member_posts = {h: [] for h in hubs}, {h: [] for h in hubs}

    # Planted structure: dense within each community.
    for hub, ms in side.items():
        for _ in range(hub_threads):
            p = toy.post(hub)
            hub_posts[hub].append(p)
            first = [toy.comment(m, p) for m in rng.sample(ms, 8)]
            for c in first[::2]:
                toy.comment(hub, c)
            for _ in range(4):
                c = rng.choice(first)
                toy.comment(rng.choice([m for m in ms if m != toy.author[c]]), c)
        for m in ms:
            p = toy.post(m)
            member_posts[hub].append(p)
            for r in rng.sample([x for x in ms if x != m], 3):
                c = toy.comment(r, p)
                if rng.random() < 0.5:
                    toy.comment(hub, c)

    # A few replies across: the planted minimum cut between the hubs.
    for src, dst in ((a, b), (b, a)):
        for m in rng.sample(side[src], 3):
            toy.comment(m, rng.choice(hub_posts[dst]))

    # Edge cases, all in community A, each counted under the rule that drops it.
    n = Counter()
    ms, p0 = side[a], hub_posts[a][0]

    autos = [toy.comment("AutoModerator", f"t3_{x['id']}", distinguished="moderator")
             for x in list(toy.posts)]
    toy.comment(ms[1], autos[0])
    n["source_system_account"] += len(autos)
    n["parent_system_account"] += 1

    for p in member_posts[a][1:4]:  # a human moderator acting officially
        toy.comment(ms[0], p, distinguished="moderator")

    tombs = [toy.comment(None, p0, body=None, removal_type="deleted",
                         excluded_reason="removal_type=deleted") for _ in range(3)]
    toy.comment(ms[2], tombs[0])
    for _ in range(2):  # deleted accounts: text survives, author doesn't
        toy.comment(None, p0)
    n["source_no_author"] += 5
    n["parent_no_author"] += 1

    # Text gone at first fetch: dropped unless someone replied to it.
    for _ in range(2):
        toy.comment(None, p0, body=None, excluded_reason=INSTANT)
    seen = toy.comment(None, p0, body=None, excluded_reason=INSTANT)
    toy.comment(ms[3], seen)
    ip = toy.post("C1950", selftext=None, excluded_reason=INSTANT)
    for m in ms[4:6]:
        toy.comment(m, ip)
    ic = toy.comment("C1951", p0, body=None, excluded_reason=INSTANT)
    toy.comment(ms[6], ic)
    toy.comment("C1952", p0, body=None, excluded_reason=INSTANT)
    n["instant_removal_unseen"] += 3
    n["source_no_author"] += 1
    n["parent_no_author"] += 1

    for i in range(2):
        toy.comment(ms[7], f"t1_gone{i}", link_id=p0)
    n["parent_missing"] += 2

    c = toy.comment(ms[8], p0)
    for _ in range(2):
        toy.comment(ms[8], c)
    n["self_loop"] += 2

    for m in ms[9:11]:
        toy.comment(m, p0, needs_review=True)

    c = toy.comment("C1901", p0)  # one long argument: 30 replies, one thread
    for i in range(30):
        c = toy.comment("C1902" if i % 2 == 0 else "C1901", c)

    for m in side[b][:3]:  # mention layer only
        toy.comment(m, hub_posts[b][0], body=f"u/{a} has the better version")
    toy.comment(side[b][3], hub_posts[b][0], body="thanks u/[user]")

    extra_a = ["C1901", "C1902", "C1950", "C1951"]
    truth = {
        "counts": dict(n),
        "partition": {**{v: a for v in [a, *side[a], *extra_a]},
                      **{v: b for v in [b, *side[b]]}},
        "cross_edges": 6,
        "mod": ms[0], "mod_actions": 3, "needs_review": 2,
        "argument": ["C1901", "C1902"], "argument_replies": 30,
        "instant": {"post": "C1950", "comment": "C1951", "unseen": "C1952"},
        "mentions": {a: 3},
    }
    return toy.posts, toy.comments, truth


def price(seed=0, T=100, m=4, alpha=2.7, start=1_738_368_000, step_days=3):
    """Growing network from Kirkley 2024 Eq. 11 (Price's model, attachment exponent alpha).

    Starts with m seed members C1..Cm. At step t a new member arrives and replies, in a
    thread of its own, to posts by m distinct existing members, each chosen with
    probability proportional to (in-degree + 1) ** alpha. Step t happens on day
    start + t * step_days (default start 2025-02-01 UTC), so steps land in known months.
    Returns (posts, comments, truth) with the seeds and each step's day.
    """
    toy = Toy(seed, start)
    rng = toy.rng
    members = [f"C{i}" for i in range(1, m + 1)]
    k = dict.fromkeys(members, 0)
    days = []
    for t in range(T):
        toy.t = start + t * step_days * 86400
        days.append(toy.t)
        new = f"C{m + t + 1}"
        weights = [(k[v] + 1) ** alpha for v in members]
        targets = set()
        while len(targets) < m:
            targets.add(rng.choices(members, weights)[0])
        for v in sorted(targets):
            toy.comment(new, toy.post(v))
            k[v] += 1
        members.append(new)
        k[new] = 0
    return toy.posts, toy.comments, {"seeds": members[:m], "step_utc": days, "in_degree": k}


def from_graph(G, weight="weight"):
    """Records in which each edge (u, v, w) is w threads of u replying to a post by v.
    Nodes are renamed C1, C2, … in G's node order; returns (posts, comments, names)."""
    toy = Toy()
    names = {v: f"C{i}" for i, v in enumerate(G, 1)}
    for u, v, w in G.edges(data=weight, default=1):
        for _ in range(w):
            toy.comment(names[u], toy.post(names[v]))
    return toy.posts, toy.comments, names


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("out")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)
    posts, comments, truth = generate(args.seed)
    os.makedirs(args.out, exist_ok=True)
    write_jsonl(os.path.join(args.out, "posts.jsonl"), posts)
    write_jsonl(os.path.join(args.out, "comments.jsonl"), comments)
    with open(os.path.join(args.out, "truth.json"), "w", encoding="utf-8") as f:
        json.dump(truth, f, indent=1)
    print(f"{len(posts)} posts, {len(comments)} comments -> {args.out}")


if __name__ == "__main__":
    main()
