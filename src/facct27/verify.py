"""Integrity report for a raw snapshot. Reports problems; never fixes them.

    uv run python -m facct27.verify data/raw/2026-10-08

Prints counts only, never usernames or text, so the output is safe to paste
into notes or a methods appendix.
"""

import argparse
import json
import os
from collections import Counter

from facct27.collect import KINDS, read_jsonl, sha256

DELETED = "[deleted]"
REMOVED = "[removed]"


def text_of(x):
    return x.get("selftext", x.get("body"))


def status_counts(items):
    c = Counter()
    for x in items:
        meta = x.get("_meta") or {}
        rtype = meta.get("removal_type")
        c[f"removal_type={rtype}"] += 1
        # Whether a removal policy has any text to act on: was it captured first?
        text = text_of(x)
        status = text if text in (DELETED, REMOVED) else "present"
        c[f"removal_type={rtype} & text={status}"] += 1
        c["was_deleted_later"] += bool(meta.get("was_deleted_later"))
        c["is_edited"] += bool(meta.get("is_edited"))
        c["no_second_fetch"] += "retrieved_2nd_on" not in meta
        c["author=[deleted]"] += x.get("author") == DELETED
        c["text=[deleted]"] += text_of(x) == DELETED
        c["text=[removed]"] += text_of(x) == REMOVED
        c["distinguished=moderator"] += x.get("distinguished") == "moderator"
        c["author=AutoModerator"] += x.get("author") == "AutoModerator"
    return dict(sorted(c.items()))


def verify(snapshot):
    with open(os.path.join(snapshot, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    data = {k: read_jsonl(os.path.join(snapshot, f"{k}.jsonl")) for k in KINDS}
    report = {}

    report["checksums_match"] = {
        name: sha256(os.path.join(snapshot, name)) == digest
        for name, digest in manifest["sha256"].items()
    }

    report["count_vs_time_series"] = {}
    for k in KINDS:
        got, expected = manifest["counts"][k], manifest["expected_counts_time_series"][k]
        diffs = {m: {"collected": got.get(m, 0), "time_series": expected.get(m, 0)}
                 for m in sorted(set(got) | set(expected))
                 if m in got and got.get(m, 0) != expected.get(m, 0)}
        report["count_vs_time_series"][k] = diffs or "all months match"

    report["duplicate_ids"] = {k: len(v) - len({x["id"] for x in v}) for k, v in data.items()}

    post_ids = {"t3_" + x["id"] for x in data["posts"]}
    comment_ids = {"t1_" + x["id"] for x in data["comments"]}
    comments = data["comments"]
    report["comments"] = {
        "total": len(comments),
        "post_missing": sum(x["link_id"] not in post_ids for x in comments),
        "top_level": sum(x["parent_id"].startswith("t3_") for x in comments),
        "parent_comment_missing": sum(x["parent_id"].startswith("t1_")
                                      and x["parent_id"] not in comment_ids
                                      for x in comments),
    }

    report["status"] = {k: status_counts(v) for k, v in data.items()}
    report["distinct_authors"] = len({x.get("author") for v in data.values() for x in v})
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("snapshot")
    args = p.parse_args(argv)
    print(json.dumps(verify(args.snapshot), indent=2))


if __name__ == "__main__":
    main()
