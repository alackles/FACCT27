from datetime import date

import pytest

from facct27.arctic import ApiTimeout
from facct27.collect import StallError, month_windows, paginate


class FakeArchive:
    """Serves synthetic items with the real API's semantics: exclusive
    `after`/`before`, ascending sort, `limit` cap. Optionally times out on
    any query whose limit exceeds `max_ok_limit`."""

    def __init__(self, timestamps, max_ok_limit=None):
        self.items = [{"id": f"x{i}", "created_utc": t} for i, t in enumerate(timestamps)]
        self.max_ok_limit = max_ok_limit
        self.calls = 0

    def get(self, endpoint, params):
        self.calls += 1
        if self.max_ok_limit and params["limit"] > self.max_ok_limit:
            raise ApiTimeout("Timeout. Maybe slow down a bit")
        hits = [x for x in self.items
                if params["after"] < x["created_utc"] < params["before"]]
        hits.sort(key=lambda x: (x["created_utc"], x["id"]))
        return hits[: params["limit"]]

    def sleep(self, _):
        pass


def ids(items):
    return sorted(x["id"] for x in items)


def test_ties_across_page_boundaries_are_not_dropped():
    # Pages of 4 over runs of 3 same-second items: every boundary splits a tie.
    ts = [1000 + i // 3 for i in range(40)]
    archive = FakeArchive(ts)
    got = paginate(archive, "posts", "sub", 1000, 2000, page_size=4)
    assert ids(got) == ids(archive.items)
    assert len(got) == len({x["id"] for x in got})


def test_window_bounds_are_start_inclusive_end_exclusive():
    archive = FakeArchive([999, 1000, 1500, 1999, 2000])
    got = paginate(archive, "posts", "sub", 1000, 2000, page_size=2)
    assert [x["created_utc"] for x in got] == [1000, 1500, 1999]


def test_full_page_at_one_second_raises_instead_of_truncating():
    archive = FakeArchive([1000] * 5 + [1001])
    with pytest.raises(StallError):
        paginate(archive, "posts", "sub", 1000, 2000, page_size=5)


def test_timeouts_shrink_the_page_and_still_return_everything():
    ts = [1000 + i for i in range(60)]
    archive = FakeArchive(ts, max_ok_limit=25)
    got = paginate(archive, "posts", "sub", 1000, 2000, page_size=100)
    assert ids(got) == ids(archive.items)


def test_month_windows_tile_the_range():
    w = month_windows(date(2025, 11, 15), date(2026, 2, 1))
    assert [label for label, _, _ in w] == ["2025-11", "2025-12", "2026-01"]
    assert all(w[i][2] == w[i + 1][1] for i in range(len(w) - 1))
