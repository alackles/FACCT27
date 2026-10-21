import json

import pytest

from facct27.collect import read_jsonl, write_jsonl
from facct27.pseudonymize import UnsetPolicy, pseudonymize

# Synthetic handles only; no real usernames in tests.
POSTS = [
    {"id": "p1", "author": "alice_x", "created_utc": 1, "title": "hi u/bob_y",
     "selftext": "see /u/Bob_Y and https://www.reddit.com/user/alice_x/ and u/stranger",
     "_meta": {}},
    {"id": "p2", "author": "carol_z", "created_utc": 2, "title": "gone",
     "selftext": "retracted text", "_meta": {"removal_type": "deleted",
                                              "was_deleted_later": True}},
]
COMMENTS = [
    {"id": "c1", "author": "bob_y", "created_utc": 3, "link_id": "t3_p2",
     "parent_id": "t3_p2", "body": "thanks alice_x", "_meta": {}},
    {"id": "c2", "author": "[deleted]", "created_utc": 4, "link_id": "t3_p2",
     "parent_id": "t1_c1", "body": "[deleted]", "_meta": {}},
    {"id": "c3", "author": "AutoModerator", "created_utc": 5, "link_id": "t3_p1",
     "parent_id": "t3_p1", "body": "rule reminder", "_meta": {"removal_type": "moderator"}},
]
WIKIS = [{"path": "/r/s/wiki/team", "revision_author": "dave_w", "revision_date": 9,
          "content": "mods: u/dave_w, u/alice_x"}]


@pytest.fixture
def run(tmp_path):
    def _run(posts=POSTS, comments=COMMENTS):
        snap = tmp_path / "raw" / "2026-01-01"
        snap.mkdir(parents=True, exist_ok=True)
        write_jsonl(str(snap / "posts.jsonl"), posts)
        write_jsonl(str(snap / "comments.jsonl"), comments)
        (snap / "wikis.json").write_text(json.dumps(WIKIS))
        pseudonymize(str(snap), str(tmp_path / "processed"), str(tmp_path / "private"))
        d = tmp_path / "processed" / "2026-01-01"
        return {k: {r.get("id") or r["path"]: r for r in read_jsonl(str(d / f"{k}.jsonl"))}
                for k in ("posts", "comments", "wikis")}
    return _run


def test_no_handle_survives_in_author_or_mention_form(run, tmp_path):
    out = run()
    dumped = json.dumps(out).lower()
    for handle in ("alice_x", "bob_y", "carol_z", "dave_w"):
        assert f"u/{handle}" not in dumped
        assert f'"{handle}"' not in dumped
    assert "u/[user]" in out["posts"]["p1"]["selftext"]  # mentioned, never posted


def test_mentions_map_to_the_same_pseudonym_as_the_author(run):
    out = run()
    bob = out["comments"]["c1"]["author"]
    assert f"u/{bob}" in out["posts"]["p1"]["title"]
    assert f"u/{bob}" in out["posts"]["p1"]["selftext"]  # /u/Bob_Y, case-folded


def test_self_deleted_becomes_tombstone_that_keeps_the_tree(run):
    p2 = run()["posts"]["p2"]
    assert p2["author"] is None and p2["title"] is None and p2["selftext"] is None
    assert p2["id"] == "p2" and p2["created_utc"] == 2
    assert p2["excluded_reason"] == "removal_type=deleted"


def test_unavailable_at_collection_and_system_accounts(run):
    c = run()["comments"]
    assert c["c2"]["author"] is None and c["c2"]["body"] is None
    assert c["c2"]["parent_id"] == "t1_c1"
    assert c["c3"]["author"] == "AutoModerator" and c["c3"]["body"] == "rule reminder"


def test_unassigned_removal_type_stops_the_run(run):
    odd = POSTS + [{"id": "p3", "author": "e", "created_utc": 6, "title": "t",
                    "selftext": "", "_meta": {"removal_type": "no_such_type"}}]
    with pytest.raises(UnsetPolicy):
        run(posts=odd)


def test_admin_removed_items_are_kept_and_flagged_for_review(run):
    flagged = POSTS + [{"id": "p3", "author": "erin_v", "created_utc": 6, "title": "t",
                        "selftext": "body", "_meta": {"removal_type": "reddit"}}]
    p = run(posts=flagged)["posts"]
    assert p["p3"]["needs_review"] and p["p3"]["selftext"] == "body"
    assert p["p3"]["author"].startswith("C")
    assert not p["p1"]["needs_review"]


def test_map_persists_across_snapshots(tmp_path):
    def snap(name, authors):
        d = tmp_path / "raw" / name
        d.mkdir(parents=True)
        write_jsonl(str(d / "posts.jsonl"), [
            {"id": a, "author": a, "created_utc": 1, "title": "t", "selftext": "", "_meta": {}}
            for a in authors])
        write_jsonl(str(d / "comments.jsonl"), [])
        (d / "wikis.json").write_text("[]")
        pseudonymize(str(d), str(tmp_path / "processed"), str(tmp_path / "private"))
        return json.loads((tmp_path / "private" / "pseudonyms.json").read_text())
    first = snap("s1", ["ann_q", "ben_q"])
    second = snap("s2", ["ben_q", "cat_q"])
    assert second["ann_q"] == first["ann_q"] and second["ben_q"] == first["ben_q"]
    assert "cat_q" in second
