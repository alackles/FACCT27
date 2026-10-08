"""Raw snapshot -> processed layer: deletion policy, tombstones, pseudonyms.

    uv run python -m facct27.pseudonymize data/raw/2026-10-08

Writes data/processed/<date>/{posts,comments,wikis}.jsonl and report.json,
and the bare-name review list to data/private/<date>/. The handle -> pseudonym
map and its seed live in data/private/ and are shared by every snapshot, so a
pseudonym quoted in the paper survives a re-collection. Nothing under data/
is committed.

Pseudonyms (C1, C2, ...) are assigned by shuffling authors with a stored
random seed, so the numbering carries no information about activity. Authors
new to a later snapshot are shuffled and appended; existing assignments never
change. See DECISIONS.md (2026-10-08) for the deletion policy.
"""

import argparse
import json
import os
import random
import re
import secrets
from collections import Counter

from facct27.collect import read_jsonl, write_jsonl

DELETED = "[deleted]"
UNAVAILABLE = {"[deleted]", "[removed]"}
SYSTEM_ACCOUNTS = {"AutoModerator"}  # Reddit infrastructure, not a person

# What happens to an item, by Arctic Shift's _meta.removal_type.
#   keep       text and author pass through (pseudonymized)
#   review     as keep, flagged needs_review for case-by-case human review
#   tombstone  structure kept (id, parent, thread, time); text and author nulled
# Decided by Acacia 2026-10-08. A removal type missing here stops the run:
# the authors assign it, it doesn't get a default.
POLICY = {
    None: "keep",
    "moderator": "keep",
    "deleted": "tombstone",
    "reddit": "review",
}

FIELDS = ["id", "link_id", "parent_id", "created_utc", "score", "num_comments",
          "link_flair_text", "distinguished", "stickied"]
TEXT_FIELDS = ["title", "selftext", "body"]

# u/name, /u/name, reddit.com/user/name, /user/name. Reddit names are 3-20 chars.
MENTION = re.compile(
    r"(?<![\w/])(?:(?:https?://)?(?:\w+\.)?reddit\.com)?/?(u|user)/([A-Za-z0-9_-]{3,20})\b",
    re.IGNORECASE)
TOKEN = re.compile(r"[A-Za-z0-9_-]{3,20}")


class UnsetPolicy(ValueError):
    pass


def extend_map(existing, authors, seed):
    """Return `existing` plus pseudonyms for any new people in `authors`."""
    new = sorted(a for a in authors if a and a != DELETED
                 and a not in SYSTEM_ACCOUNTS and a not in existing)
    random.Random(f"{seed}:{len(existing)}").shuffle(new)
    start = len(existing)
    return {**existing, **{a: f"C{start + i}" for i, a in enumerate(new, 1)}}


def pseudonym(author, mapping):
    if author is None or author == DELETED:
        return None
    if author in SYSTEM_ACCOUNTS:
        return author
    return mapping[author]


def replace_mentions(text, lower_map):
    def sub(m):
        name = lower_map.get(m.group(2).lower())
        return f"u/{name}" if name else "u/[user]"
    return MENTION.sub(sub, text)


def process_item(x, mapping, lower_map):
    meta = x.get("_meta") or {}
    rtype = meta.get("removal_type")
    action = POLICY.get(rtype)
    if action is None:
        raise UnsetPolicy(rtype)

    out = {k: x.get(k) for k in FIELDS if k in x}
    out["removal_type"] = rtype
    out["was_deleted_later"] = bool(meta.get("was_deleted_later"))
    out["is_edited"] = bool(meta.get("is_edited"))
    out["excluded_reason"] = None
    out["needs_review"] = action == "review"

    if action == "tombstone":
        out["author"] = None
        for f in TEXT_FIELDS:
            if f in x:
                out[f] = None
        out["excluded_reason"] = f"removal_type={rtype}"
        return out

    out["author"] = pseudonym(x.get("author"), mapping)
    for f in TEXT_FIELDS:
        if f not in x:
            continue
        text = x[f]
        if text in UNAVAILABLE and f != "title":
            out[f] = None
            out["excluded_reason"] = out["excluded_reason"] or "text_unavailable_at_collection"
        else:
            out[f] = replace_mentions(text, lower_map) if text else text
    return out


def process_wiki(page, mapping, lower_map):
    return {
        "path": page["path"],
        "revision_date": page.get("revision_date"),
        "revision_author": pseudonym(page.get("revision_author"), mapping),
        "content": replace_mentions(page.get("content") or "", lower_map),
    }


def bare_mentions(records, mapping):
    """Handles appearing as plain words (no u/) in processed text, for human review."""
    lower = {a.lower(): a for a in mapping}
    hits = {}
    for r in records:
        text = " ".join(r.get(f) or "" for f in TEXT_FIELDS + ["content"])
        for tok in {t.lower() for t in TOKEN.findall(text)} & lower.keys():
            hits.setdefault(lower[tok], []).append(r.get("id") or r.get("path"))
    return hits


def leaks(records, mapping):
    """Raw handles surviving as an author value or a u/ mention. Must be empty."""
    found = []
    handles = {a.lower() for a in mapping}
    for r in records:
        for f in ("author", "revision_author"):
            if r.get(f) in mapping:
                found.append((r.get("id") or r.get("path"), f))
        for f in TEXT_FIELDS + ["content"]:
            for m in MENTION.finditer(r.get(f) or ""):
                if m.group(2).lower() in handles:
                    found.append((r.get("id") or r.get("path"), f))
    return found


def pseudonymize(snapshot, processed_root="data/processed", private_root="data/private"):
    date = os.path.basename(os.path.normpath(snapshot))
    out_dir = os.path.join(processed_root, date)
    priv_dir = os.path.join(private_root, date)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(priv_dir, exist_ok=True)

    posts = read_jsonl(os.path.join(snapshot, "posts.jsonl"))
    comments = read_jsonl(os.path.join(snapshot, "comments.jsonl"))
    with open(os.path.join(snapshot, "wikis.json"), encoding="utf-8") as f:
        wikis = json.load(f) or []

    unset = Counter((x.get("_meta") or {}).get("removal_type") for x in posts + comments)
    unset = {k: n for k, n in unset.items() if k not in POLICY}
    if unset:
        raise UnsetPolicy(f"no policy for removal_type(s) {unset}; add to POLICY "
                          "after the authors decide, and record it in DECISIONS.md")

    seed_path = os.path.join(private_root, "seed.txt")
    if os.path.exists(seed_path):
        with open(seed_path, encoding="utf-8") as f:
            seed = f.read().strip()
    else:
        seed = secrets.token_hex(16)
        with open(seed_path, "w", encoding="utf-8") as f:
            f.write(seed + "\n")
    map_path = os.path.join(private_root, "pseudonyms.json")
    existing = {}
    if os.path.exists(map_path):
        with open(map_path, encoding="utf-8") as f:
            existing = json.load(f)

    authors = {x.get("author") for x in posts + comments}
    authors |= {w.get("revision_author") for w in wikis}
    mapping = extend_map(existing, authors, seed)
    lower_map = {a.lower(): p for a, p in mapping.items()}

    out = {
        "posts": [process_item(x, mapping, lower_map) for x in posts],
        "comments": [process_item(x, mapping, lower_map) for x in comments],
        "wikis": [process_wiki(w, mapping, lower_map) for w in wikis],
    }
    everything = out["posts"] + out["comments"] + out["wikis"]
    leaked = leaks(everything, mapping)
    if leaked:
        raise AssertionError(f"{len(leaked)} handle leaks; nothing written")

    for name, records in out.items():
        write_jsonl(os.path.join(out_dir, f"{name}.jsonl"), records)
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=1, sort_keys=True)
    bare = bare_mentions(everything, mapping)
    with open(os.path.join(priv_dir, "bare_mentions.json"), "w", encoding="utf-8") as f:
        json.dump(bare, f, indent=1, sort_keys=True)

    report = {
        "snapshot": snapshot,
        "pseudonymized_authors": len(mapping),
        "pseudonyms_new_this_run": len(mapping) - len(existing),
        "needs_review": {k: sum(r["needs_review"] for r in out[k]) for k in ("posts", "comments")},
        "excluded_reason": {k: dict(Counter(str(r["excluded_reason"]) for r in out[k]))
                            for k in ("posts", "comments")},
        "removal_type": {k: dict(Counter(str(r["removal_type"]) for r in out[k]))
                         for k in ("posts", "comments")},
        "wiki_pages": len(out["wikis"]),
        "bare_mention_review": {"handles": len(bare),
                                "records": sum(len(v) for v in bare.values()),
                                "list": os.path.join(priv_dir, "bare_mentions.json")},
        "policy": {str(k): v for k, v in POLICY.items()},
    }
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("snapshot")
    args = p.parse_args(argv)
    print(json.dumps(pseudonymize(args.snapshot), indent=2))


if __name__ == "__main__":
    main()
