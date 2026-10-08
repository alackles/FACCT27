"""Census of a subreddit's posts and comments from Arctic Shift into a raw snapshot.

    uv run python -m facct27.collect --after 2025-01-01 --before 2026-10-01 \
        --out data/raw/2026-10-08

Writes, under --out:
    parts/{posts,comments}/YYYY-MM.jsonl   one file per month (the resume unit)
    posts.jsonl, comments.jsonl            all months, sorted by (created_utc, id)
    wikis.json, rules.json                 subreddit wiki pages and rules as returned
    manifest.json                          query, timing, counts, checksums, commit

The raw snapshot is unmodified API output, including real usernames and
self-deleted text. It must stay under data/ (gitignored); see DECISIONS.md.
A snapshot with a manifest is complete and is never written to again.
"""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, date, datetime

from facct27.arctic import BASE_URL, USER_AGENT, ApiTimeout, Client

KINDS = ("posts", "comments")
MIN_PAGE = 5


class StallError(RuntimeError):
    """A full page shares one timestamp, so the time cursor can't advance."""


def epoch(d):
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())


def month_windows(after, before):
    """Split [after, before) into calendar-month windows of (label, start, end) epochs."""
    windows = []
    cur = after
    while cur < before:
        nxt = date(cur.year + cur.month // 12, cur.month % 12 + 1, 1)
        end = min(nxt, before)
        windows.append((f"{cur:%Y-%m}", epoch(cur), epoch(end)))
        cur = end
    return windows


def paginate(client, kind, subreddit, start, end, page_size=100):
    """Every item of `kind` created in [start, end), oldest first.

    The API's `after` and `before` are exclusive (checked 2026-10-08). The
    cursor is set one second before the last timestamp seen, so items sharing
    that second are fetched again rather than skipped; duplicates are dropped
    by id.
    """
    seen = {}
    cursor = start - 1
    limit = page_size
    timeouts = 0
    while True:
        params = {"subreddit": subreddit, "after": cursor, "before": end,
                  "sort": "asc", "limit": limit}
        try:
            page = client.get(f"{kind}/search", params)
        except ApiTimeout:
            timeouts += 1
            if limit == MIN_PAGE and timeouts > 3:
                raise
            client.sleep(5 * timeouts)
            limit = max(MIN_PAGE, limit // 2)
            continue
        timeouts = 0

        new = [x for x in page if x["id"] not in seen]
        for x in new:
            seen[x["id"]] = x
        if not new:
            if len(page) == limit:
                raise StallError(f"{limit}+ {kind} at t={page[0]['created_utc']}; "
                                 "raise --page-size")
            break
        cursor = page[-1]["created_utc"] - 1

    return sorted(seen.values(), key=lambda x: (x["created_utc"], x["id"]))


def expected_counts(client, kind, subreddit):
    """Arctic Shift's own monthly counts, as an independent completeness check."""
    series = client.get("time_series", {"key": f"r/{subreddit}/{kind}/count",
                                         "precision": "month"})
    return {datetime.fromtimestamp(row["date"], UTC).strftime("%Y-%m"): row["value"]
            for row in series}


def write_jsonl(path, items):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for x in items:
            f.write(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(tmp, path)


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def repo_commit():
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return None


def collect(client, subreddit, after, before, out, page_size=100, log=print):
    manifest_path = os.path.join(out, "manifest.json")
    if os.path.exists(manifest_path):
        raise SystemExit(f"{out} is a completed snapshot; choose a new --out")
    started = datetime.now(UTC).isoformat(timespec="seconds")
    windows = month_windows(after, before)
    os.makedirs(out, exist_ok=True)
    runs_path = os.path.join(out, "runs.jsonl")
    with open(runs_path, "a", encoding="utf-8") as f:  # one line per (re)start
        f.write(json.dumps({"started_utc": started, "commit": repo_commit()}) + "\n")

    counts = {}
    for kind in KINDS:
        part_dir = os.path.join(out, "parts", kind)
        os.makedirs(part_dir, exist_ok=True)
        counts[kind] = {}
        for label, start, end in windows:
            part = os.path.join(part_dir, f"{label}.jsonl")
            if os.path.exists(part):
                counts[kind][label] = len(read_jsonl(part))
                log(f"{kind} {label}: {counts[kind][label]} (already collected)")
                continue
            items = paginate(client, kind, subreddit, start, end, page_size)
            write_jsonl(part, items)
            counts[kind][label] = len(items)
            log(f"{kind} {label}: {len(items)}")

    files = {}
    for kind in KINDS:
        items = []
        for label, _, _ in windows:
            items += read_jsonl(os.path.join(out, "parts", kind, f"{label}.jsonl"))
        path = os.path.join(out, f"{kind}.jsonl")
        write_jsonl(path, items)
        files[f"{kind}.jsonl"] = path

    wiki_paths = client.get("subreddits/wikis/list", {"subreddit": subreddit})
    extras = {
        "wikis.json": client.get("subreddits/wikis", {"subreddit": subreddit, "limit": 100}),
        "rules.json": client.get("subreddits/rules", {"subreddits": subreddit}),
    }
    for name, data in extras.items():
        path = os.path.join(out, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        files[name] = path
    if len(extras["wikis.json"] or []) != len(wiki_paths or []):
        log(f"warning: wiki list has {len(wiki_paths)} paths, "
            f"fetched {len(extras['wikis.json'])} pages")

    expected = {k: expected_counts(client, k, subreddit) for k in KINDS}
    manifest = {
        "source": BASE_URL,
        "user_agent": USER_AGENT,
        "subreddit": subreddit,
        "after_inclusive": after.isoformat(),
        "before_exclusive": before.isoformat(),
        "page_size": page_size,
        "started_utc": started,
        "runs": read_jsonl(runs_path),
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "collector_commit": repo_commit(),
        "requests_made_final_run": client.requests_made,
        "counts": counts,
        "totals": {k: sum(v.values()) for k, v in counts.items()},
        "expected_counts_time_series": expected,
        "wiki_paths_listed": wiki_paths,
        "sha256": {name: sha256(path) for name, path in files.items()},
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    log(f"done: {manifest['totals']} in {client.requests_made} requests -> {out}")
    return manifest


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--subreddit", default="ClaudeAIJailbreak")
    p.add_argument("--after", type=date.fromisoformat, required=True,
                   help="first day included (UTC)")
    p.add_argument("--before", type=date.fromisoformat, required=True,
                   help="first day excluded (UTC)")
    p.add_argument("--out", required=True, help="snapshot dir, e.g. data/raw/2026-10-08")
    p.add_argument("--page-size", type=int, default=100)
    args = p.parse_args(argv)
    collect(Client(), args.subreddit, args.after, args.before, args.out, args.page_size,
            log=lambda *a: print(*a, flush=True))


if __name__ == "__main__":
    main()
