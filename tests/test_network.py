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
