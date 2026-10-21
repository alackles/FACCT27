import json

import networkx as nx
import pytest

from facct27 import network, toy

IGNORED = {"considered", "interactions"}


@pytest.fixture(scope="module")
def planted():
    posts, comments, truth = toy.generate(seed=0)
    D, counts = network.build(posts, comments)
    return posts, comments, truth, D, counts


def karate():
    G = nx.karate_club_graph()
    posts, comments, names = toy.from_graph(G)
    D, _ = network.build(posts, comments)
    return G, names, network.undirected(D)


def test_karate_records_rebuild_zacharys_weighted_graph():
    G, names, U = karate()
    want = {frozenset((names[u], names[v])): w for u, v, w in G.edges(data="weight")}
    assert {frozenset((u, v)): w for u, v, w in U.edges(data="contexts")} == want


def test_karate_min_cut_misplaces_only_zacharys_individual_9():
    # Zachary 1977: the flow model placed every member except individual 9
    # (node 8 here, zero-indexed) on the side they actually joined.
    G, names, U = karate()
    cut = network.cut_pairs(U, [names[0], names[33]])[0]
    assert cut["s"] == names[0]
    hi = set(cut["s_members"])
    wrong = [v for v in G if (names[v] in hi) != (G.nodes[v]["club"] == "Mr. Hi")]
    assert wrong == [8]


def test_every_planted_edge_case_is_dropped_by_its_rule_and_nothing_else(planted):
    *_, truth, D, counts = planted
    fired = {k: v for k, v in counts.items() if v and k not in IGNORED}
    assert fired == truth["counts"]


def test_nodes_are_people_with_moderators_flagged(planted):
    *_, truth, D, counts = planted
    assert "AutoModerator" not in D and None not in D
    assert [v for v, m in D.nodes(data="mod") if m] == [truth["mod"]]


def test_weight_counts_threads_not_replies(planted):
    *_, truth, D, counts = planted
    e = network.undirected(D)[truth["argument"][0]][truth["argument"][1]]
    assert (e["contexts"], e["replies"]) == (1, truth["argument_replies"])


def test_instant_removals_stay_only_when_replied_to(planted):
    *_, truth, D, counts = planted
    i = truth["instant"]
    assert D.in_degree(i["post"]) == 2
    assert D.in_degree(i["comment"]) == 1 and D.out_degree(i["comment"]) == 1
    assert i["unseen"] not in D


def test_review_and_mod_options_drop_exactly_the_flagged_items(planted):
    posts, comments, truth, D, counts = planted
    assert sum(e for *_, e in D.edges(data="needs_review")) == truth["needs_review"]
    _, strict = network.build(posts, comments, needs_review=False, mod_actions=False)
    assert strict["needs_review_excluded"] == truth["needs_review"]
    assert strict["mod_action_excluded"] == truth["mod_actions"]


def test_min_cut_between_hubs_recovers_planted_partition(planted):
    *_, truth, D, counts = planted
    a, b = "C1001", "C2001"
    cut = network.cut_pairs(network.undirected(D), [a, b])[0]
    assert cut["cut"] == truth["cross_edges"] and not cut["no_better_than_isolating"]
    side_a = set(cut["s_members"])
    assert {v for v, hub in truth["partition"].items() if hub == a} == side_a


def test_cut_that_only_isolates_a_weak_pole_is_flagged(planted):
    *_, truth, D, counts = planted
    cut = network.cut_pairs(network.undirected(D), ["C1001", truth["instant"]["post"]])[0]
    assert cut["no_better_than_isolating"]


def test_kirkley_candidates_are_the_planted_hubs_and_get_cut(planted):
    posts, comments, truth, *_ = planted
    _, report, cuts = network.analyze(posts, comments, candidates="kirkley")
    assert report["candidates"]["rule"] == "kirkley"
    assert [v for v, _ in report["candidates"]["hubs"]] == ["C1001", "C2001"]
    assert [(c["s"], c["t"]) for c in cuts] == [("C1001", "C2001")]
    assert cuts[0]["cut"] == truth["cross_edges"]


def test_single_kirkley_hub_reports_no_candidate_pairs():
    star = nx.DiGraph((f"leaf{i}", "centre") for i in range(40))
    star.add_edges_from((f"leaf{i}", f"leaf{i + 1}") for i in range(0, 40, 4))
    posts, comments, names = toy.from_graph(star)
    _, report, cuts = network.analyze(posts, comments, candidates="kirkley")
    assert report["candidates"]["h"] == 1
    assert report["candidates"]["hubs"][0][0] == names["centre"]
    assert report["candidates"]["note"] == "no candidate pairs" and cuts == []


def test_gomory_hu_tree_gives_every_karate_cut_and_zacharys_split():
    G, names, U = karate()
    nodes = sorted(U)
    strength = dict(U.degree(weight="weight"))
    F = network.gomory_hu(U)
    from_tree = {(r["s"], r["t"]): r["cut"] for r in network.tree_cuts(F, nodes, strength)}
    pairwise = {(r["s"], r["t"]): r["cut"] for r in network.cut_pairs(U, nodes)}
    assert len(from_tree) == 561 and from_tree == pairwise
    hi, _ = network.tree_partition(F, names[0], names[33])
    wrong = [v for v in G if (names[v] in hi) != (G.nodes[v]["club"] == "Mr. Hi")]
    assert wrong == [8]


def test_tree_cuts_match_pairwise_cuts_on_planted_toy(planted):
    *_, truth, D, counts = planted
    U = network.undirected(D)
    poles = ["C1001", "C2001", truth["instant"]["post"], "C1005", "C2007"]
    keep = ("s", "t", "connected", "cut", "s_side", "t_side", "no_better_than_isolating")
    pairwise = [{k: r[k] for k in keep} for r in network.cut_pairs(U, poles)]
    tree = [{k: r[k] for k in keep}
            for r in network.tree_cuts(network.gomory_hu(U), poles,
                                       dict(U.degree(weight="weight")))]
    assert tree == pairwise
    hubs = next(r for r in tree if (r["s"], r["t"]) == ("C1001", "C2001"))
    assert hubs["cut"] == truth["cross_edges"]


def test_tree_cuts_across_components_are_not_connected():
    U = nx.Graph()
    U.add_weighted_edges_from([("a", "b", 2), ("b", "c", 1), ("x", "y", 3)])
    F = network.gomory_hu(U)
    assert nx.number_connected_components(F) == 2
    rows = {(r["s"], r["t"]): r for r in network.tree_cuts(F, "abcxy", dict(U.degree(weight="weight")))}
    assert not rows[("a", "x")]["connected"] and rows[("a", "c")]["cut"] == 1
    assert (rows[("a", "c")]["s_side"], rows[("a", "c")]["t_side"]) == (2, 1)


def test_cli_tree_cuts_end_to_end(tmp_path, capsys):
    toy.main([str(tmp_path / "toy")])
    network.main([str(tmp_path / "toy"), "--out", str(tmp_path / "net"),
                  "--candidates", "kirkley", "--cuts", "tree"])
    capsys.readouterr()
    report = json.loads((tmp_path / "net" / "report.json").read_text())
    cuts = json.loads((tmp_path / "net" / "cuts.json").read_text())
    forest = json.loads((tmp_path / "net" / "gomory_hu.json").read_text())
    assert len(forest) == report["graph"]["nodes"] - report["graph"]["components"]
    s = report["cut_summary"]
    assert (s["method"], s["pairs"]) == ("tree", len(cuts))
    assert s["degenerate"] == sum(c.get("no_better_than_isolating", False) for c in cuts)
    assert not any(k.endswith("_members") for c in cuts for k in c)


def test_mention_layer_links_mentioner_to_mentioned(planted):
    posts, comments, truth, *_ = planted
    M, _ = network.build(posts, comments, layer="mention")
    assert {v: M.in_degree(v) for v in M if M.in_degree(v)} == truth["mentions"]


def test_cli_end_to_end_on_toy_snapshot(tmp_path, capsys):
    toy.main([str(tmp_path / "toy")])
    network.main([str(tmp_path / "toy"), "--out", str(tmp_path / "net")])
    report = json.loads(capsys.readouterr().out.split("\n", 1)[1])
    assert report["graph"]["nodes"] == nx.read_graphml(tmp_path / "net" / "graph.graphml").number_of_nodes()
    assert report["cuts"] and all("s_members" not in c for c in report["cuts"])


def test_viz_payload_covers_every_node_and_tie(planted):
    from facct27 import viz
    *_, D, counts = planted
    G = network.undirected(D)
    data = viz.payload(D, G)
    assert {n["id"] for n in data["nodes"]} == set(G)
    assert len(data["links"]) == G.number_of_edges()
    assert sum(c["size"] for c in data["clusters"]) == G.number_of_nodes()
    html = viz.render({"x": "</script>"})  # a closing tag in the data can't end the block
    blob = html.split('type="application/json">', 1)[1].split("</script>", 1)[0]
    assert json.loads(blob) == {"x": "</script>"}


def test_hub_view_groups_each_hub_with_its_repliers_in_the_same_layout_order(planted):
    from facct27 import viz
    *_, D, counts = planted
    G = network.undirected(D)
    louvain, hubs = viz.payload(D, G), viz.hub_payload(D, G, "CM")
    assert [n["id"] for n in hubs["nodes"]] == [n["id"] for n in louvain["nodes"]]
    assert hubs["links"] == louvain["links"]
    assert [h["id"] for h in hubs["hubs"]] == ["C1001", "C2001"]
    index = {n["id"]: i for i, n in enumerate(hubs["nodes"])}
    for h in hubs["hubs"]:
        want = {index[h["id"]]} | {index[u] for u in D.predecessors(h["id"])}
        assert set(h["members"]) == want and h["repliers"] == len(want) - 1
