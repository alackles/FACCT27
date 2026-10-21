"""Kirkley hubs of the reply graph, month by month and cumulatively.

    uv run python -m facct27.hubs data/processed/2026-10-08 --out data/derived/2026-10-08/hubs

Each window's graph comes from network.build, so every edge rule applies unchanged.
Each window is scanned for in- and out-hubs, on contexts-weighted and unweighted
degree. Prints the primary rows (in-degree, contexts-weighted) as counts and
pseudonyms only, so the table is safe to paste; all rows go to hubs.json (with hub
lists) and hubs.csv (scalars). Decisions: docs/DECISIONS.md (2026-10-21).
"""

import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone

from facct27 import kirkley, network
from facct27.collect import read_jsonl

DIRECTIONS = ("in", "out")
WEIGHTINGS = {"contexts": True, "unweighted": False}  # name -> multigraph encoding
SCALARS = ["series", "window", "direction", "weighting", "N", "M", "interactions",
           "empty", "h_CM", "h_ER", "er_wins", "k_star", "eta_CM", "eta_ER",
           "L0_CM", "L_CM", "L0_ER", "L_ER"]


def degree_sequence(D, direction="in", weighted=True):
    """{node: degree} over every node of D, zeros included."""
    deg = D.in_degree if direction == "in" else D.out_degree
    return dict(deg(weight="contexts" if weighted else None))


def months(comments):
    """[(label, start, end)] for each UTC calendar month from first to last comment."""
    times = [c["created_utc"] for c in comments]
    t = datetime.fromtimestamp(min(times), timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)
    last = max(times)
    out = []
    while t.timestamp() <= last:
        nxt = t.replace(year=t.year + t.month // 12, month=t.month % 12 + 1)
        out.append((t.strftime("%Y-%m"), int(t.timestamp()), int(nxt.timestamp())))
        t = nxt
    return out


def analyze(posts, comments, needs_review=True, mod_actions=True):
    windows = months(comments)
    first = windows[0][1]
    rows = []
    for series in ("monthly", "cumulative"):
        for label, start, end in windows:
            D, counts = network.build(posts, comments, start=first if series == "cumulative"
                                      else start, end=end, needs_review=needs_review,
                                      mod_actions=mod_actions)
            for direction in DIRECTIONS:
                for weighting, weighted in WEIGHTINGS.items():
                    r = kirkley.scan(degree_sequence(D, direction, weighted), weighted)
                    for enc in ("ER", "CM"):
                        r[f"hubs_{enc}"] = [[v, k, D.nodes[v]["mod"]]
                                            for v, k in r[f"hubs_{enc}"]]
                    rows.append({"series": series, "window": label, "direction": direction,
                                 "weighting": weighting,
                                 "interactions": counts["interactions"], **r})
    return rows


def table(rows, show=8):
    """Primary rows as text: CM hubs listed as pseudonym:degree, * = moderator."""
    head = f"{'series':<10} {'window':<7} {'N':>5} {'M':>6} {'h_CM':>4} {'h_ER':>4} " \
           f"{'eta_CM':>6} {'ER<CM':>5}  CM hubs"
    lines = [head]
    for r in rows:
        if r["direction"] != "in" or r["weighting"] != "contexts":
            continue
        hubs = " ".join(f"{v}:{k}{'*' if mod else ''}" for v, k, mod in r["hubs_CM"][:show])
        if len(r["hubs_CM"]) > show:
            hubs += f" (+{len(r['hubs_CM']) - show})"
        lines.append(f"{r['series']:<10} {r['window']:<7} {r['N']:>5} {r['M']:>6} "
                     f"{r['h_CM']:>4} {r['h_ER']:>4} {r['eta_CM']:>6.3f} "
                     f"{'yes' if r['er_wins'] else '':>5}  {hubs}")
    return "\n".join(lines)


def write(out, report):
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "hubs.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    with open(os.path.join(out, "hubs.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, SCALARS, extrasaction="ignore")
        w.writeheader()
        w.writerows(report["rows"])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("snapshot", help="processed snapshot with posts.jsonl, comments.jsonl")
    p.add_argument("--out", required=True)
    p.add_argument("--exclude-needs-review", action="store_true")
    p.add_argument("--exclude-mod-actions", action="store_true")
    a = p.parse_args(argv)

    began = time.time()
    posts = read_jsonl(os.path.join(a.snapshot, "posts.jsonl"))
    comments = read_jsonl(os.path.join(a.snapshot, "comments.jsonl"))
    rows = analyze(posts, comments, not a.exclude_needs_review, not a.exclude_mod_actions)
    report = {"snapshot": a.snapshot,
              "params": {"needs_review": not a.exclude_needs_review,
                         "mod_actions": not a.exclude_mod_actions},
              "rows": rows, "seconds": round(time.time() - began, 1)}
    write(a.out, report)
    print(table(rows))
    print(f"\n{len(rows)} rows (in/out x contexts/unweighted) in {a.out}/hubs.csv; "
          f"{report['seconds']} s")


if __name__ == "__main__":
    main()
