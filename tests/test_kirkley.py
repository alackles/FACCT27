import json
import math
import os
import random

import pytest

from facct27 import kirkley

REFERENCE = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures",
                                        "kirkley_reference.json")))


@pytest.mark.parametrize("case", REFERENCE["cases"],
                         ids=lambda c: f"{c['name']}-{'weighted' if c['weighted'] else 'simple'}")
def test_matches_kirkleys_reference_code(case):
    # Expected values come from running the author's functions.py (commit in the
    # fixture) on these sequences; it reports description lengths in nats.
    r = kirkley.scan(dict(enumerate(case["degrees"])), case["weighted"])
    for enc in ("ER", "CM"):
        assert r[f"h_{enc}"] == case[f"h_{enc}"]
        assert r[f"L_{enc}"] * math.log(2) == pytest.approx(case[f"L_nats_{enc}"], rel=1e-9)
        assert r[f"eta_{enc}"] == pytest.approx(case[f"eta_{enc}"], abs=1e-9)


def test_poisson_in_degrees_have_no_er_hubs():
    # Kirkley Fig. 2a: with Poisson in-degrees the ER encoding always finds zero hubs.
    rng = random.Random(0)
    N, mean = 1000, 100
    degrees = dict.fromkeys(range(N), 0)
    for _ in range(N * mean):
        degrees[rng.randrange(N)] += 1
    assert kirkley.scan(degrees, weighted=True)["h_ER"] == 0


def test_tied_degrees_enter_together_regardless_of_node_order():
    degrees = {"a": 9, "b": 9, "c": 5, "d": 5, "e": 5, **{f"z{i}": 1 for i in range(11)}}
    want = kirkley.scan(degrees)
    items = list(degrees.items())
    random.Random(1).shuffle(items)
    got = kirkley.scan(dict(items))
    assert got == want
    for enc in ("ER", "CM"):
        hub_degrees = {k for _, k in want[f"hubs_{enc}"]}
        rest = [k for v, k in degrees.items() if v not in dict(want[f"hubs_{enc}"])]
        assert not hub_degrees & set(rest)  # no degree value split across the cut


@pytest.mark.parametrize("degrees", [{}, {"a": 3}])
def test_empty_or_single_node_windows_report_no_hubs(degrees):
    r = kirkley.scan(degrees)
    assert r["empty"] and r["h_CM"] == r["h_ER"] == 0 and r["hubs_CM"] == []
