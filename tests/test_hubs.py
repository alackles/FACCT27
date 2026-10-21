import csv
import json
import statistics

from facct27 import hubs, kirkley, network, toy
from facct27.collect import write_jsonl


def final_cumulative(rows, direction="in", weighting="contexts"):
    return [r for r in rows if r["series"] == "cumulative" and r["direction"] == direction
            and r["weighting"] == weighting][-1]


def test_superlinear_growth_makes_the_seeds_the_hubs():
    # Kirkley Fig. 3d: with superlinear attachment, h* converges to the m seed nodes.
    found = []
    for seed in range(10):
        posts, comments, truth = toy.price(seed=seed, m=4, alpha=2.7)
        r = final_cumulative(hubs.analyze(posts, comments))
        assert set(truth["seeds"]) <= {v for v, _, _ in r["hubs_CM"]}
        found.append(r["h_CM"])
    assert statistics.median(found) == 4


def test_months_partition_interactions_and_cumulative_ends_at_whole_graph():
    posts, comments, _ = toy.price(seed=0)
    rows = hubs.analyze(posts, comments)
    primary = [r for r in rows if r["direction"] == "in" and r["weighting"] == "contexts"]
    D, counts = network.build(posts, comments)
    monthly = [r for r in primary if r["series"] == "monthly"]
    assert len(monthly) == len(hubs.months(comments)) > 1
    assert sum(r["interactions"] for r in monthly) == counts["interactions"]
    whole = kirkley.scan(hubs.degree_sequence(D))
    last = final_cumulative(rows)
    assert (last["N"], last["M"], last["h_CM"]) == (whole["N"], whole["M"], whole["h_CM"])


def test_cli_end_to_end_on_toy_snapshot(tmp_path, capsys):
    snap = tmp_path / "snap"
    snap.mkdir()
    posts, comments, _ = toy.generate(seed=0)
    for x in posts + comments:
        for field in ("title", "selftext", "body"):
            if field in x:
                x[field] = "SENTINEL_TEXT"
    write_jsonl(str(snap / "posts.jsonl"), posts)
    write_jsonl(str(snap / "comments.jsonl"), comments)
    hubs.main([str(snap), "--out", str(tmp_path / "hubs")])
    printed = capsys.readouterr().out
    report = json.loads((tmp_path / "hubs" / "hubs.json").read_text())
    with open(tmp_path / "hubs" / "hubs.csv", newline="") as f:
        assert len(list(csv.DictReader(f))) == len(report["rows"])
    with open(tmp_path / "hubs" / "degrees.csv", newline="") as f:
        degrees = list(csv.DictReader(f))
    assert len(degrees) == 4 * len({d["node"] for d in degrees})
    names = {v for r in report["rows"] for enc in ("ER", "CM") for v, _, _ in r[f"hubs_{enc}"]}
    assert names and all(v.startswith("C") for v in names)
    assert "in-degree, contexts-weighted" in printed and "out-degree, contexts-weighted" in printed
    er = {v for r in report["rows"] if r["weighting"] == "contexts" for v, _, _ in r["hubs_ER"]}
    assert er and all(f"{v}:" in printed for v in er)
    assert "SENTINEL_TEXT" not in printed + json.dumps(report)  # no text leaks


def test_degree_table_flags_agree_with_the_scan():
    posts, comments, _ = toy.price(seed=0)
    D, _ = network.build(posts, comments)
    rows = hubs.degree_table(D)
    for direction in hubs.DIRECTIONS:
        for weighting, weighted in hubs.WEIGHTINGS.items():
            panel = [r for r in rows if (r["direction"], r["weighting"]) == (direction, weighting)]
            r = kirkley.scan(hubs.degree_sequence(D, direction, weighted), weighted)
            assert [p["rank"] for p in panel] == list(range(1, D.number_of_nodes() + 1))
            assert sum(p["hub_ER"] for p in panel) == r["h_ER"]
            assert sum(p["hub_CM"] for p in panel) == r["h_CM"]
            assert [p["degree"] for p in panel] == sorted((p["degree"] for p in panel), reverse=True)
