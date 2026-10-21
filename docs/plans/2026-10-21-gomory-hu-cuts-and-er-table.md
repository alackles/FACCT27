# Plan: ER hubs in the printed table + Gomory–Hu cuts for large candidate sets

## Context

The first real Kirkley run (2026-10-08 snapshot) showed:
- ER finds one in-hub (C653) in every cumulative window.
- CM finds the heavy tail, 492 of 4,633 nodes by 2026-09.

Both encodings are now reported as distinct measures (DECISIONS `b05f5ce`), but the printed table still lists only CM hubs. The out-degree pattern was the main finding (C653's share of replies falls to 3–4% while a responder cohort takes over), yet out-degree isn't printed at all. Separately, `network --candidates kirkley` with 492 CM candidates means ~120k pairwise min-cuts. `cut_pairs` runs one max-flow per pair and stores both sides' member lists per pair, so Acacia killed the run. A Gomory–Hu tree gives every pairwise min-cut value from n−1 max-flows, with the partitions encoded in the tree itself.

## Part A: printed hubs table (`src/facct27/hubs.py`)

- `table(rows, direction)` prints both hub lists, **ER hubs first, then CM hubs** (each `pseudonym:degree`, `*` = moderator, first 8 then `(+n)`), alongside N, M, h_ER, h_CM, η_CM, ER<CM.
- `main` prints two blocks, in-degree then out-degree, both contexts-weighted. Unweighted stays in `hubs.csv`/`hubs.json`.
- Test: extend `test_cli_end_to_end_on_toy_snapshot` to assert that the ER hub pseudonyms and both block headers appear in the printed output.

## Part B: Gomory–Hu cuts (`src/facct27/network.py`)

### Functions
- `gomory_hu(G)` returns a forest: one Gomory–Hu tree per connected component with ≥2 nodes, via `nx.gomory_hu_tree(component, capacity="weight", flow_func=...)`. **`capacity="weight"` must be passed explicitly**, because networkx treats a missing capacity attribute as infinite. The tree edge attribute `weight` is the cut value. The symmetrized contexts-weighted graph from `undirected()` is the same input `cut_pairs` uses.
- `tree_cuts(T, poles, strength)` takes each pole s in sorted order and does one traversal of s's tree, tracking the minimum edge on the path to every node. That gives rows for every t > s in O(k·n), not O(k²·n). Rows have the same fields as `cut_pairs` (s, t, strengths, connected, cut, s_side, t_side, no_better_than_isolating) but **no member lists**. Side sizes come from precomputed subtree sizes of each rooted component tree. **Tie rule:** when several path edges share the minimum, use the one nearest s (deterministic). Poles in different components get `connected: False`, as now.
- `tree_partition(T, s, t)` returns the two member sets for one pair, using the same tie rule. It's for tests and on-demand inspection, not bulk output.

### CLI and outputs
- `--cuts {pairs,tree}`, default `pairs` (existing behavior and outputs unchanged).
- Under `tree`:
  - `gomory_hu.json` holds the forest as an edge list `[u, v, cut]`: pseudonyms and numbers, compact, encodes every partition.
  - `cuts.json` holds rows without member lists.
  - The printed report gets a cut **summary** instead of every row: pairs, connected pairs, degenerate count (`no_better_than_isolating`), plus the full rows of the **non-degenerate** cuts only. My prediction is that nearly all cuts are degenerate. The summary shows it either way.
- Works with either `--candidates` rule.

### Flow function and runtime (step 1, before building the CLI)
- Benchmark on a synthetic graph of corpus scale: `toy.price(T≈4600, m≈3, alpha≈1)` → `build` → `undirected` gives about 4.6k nodes and ~14k edges, comparable to the 2026-10-08 graph. Time `gomory_hu` with `edmonds_karp` (networkx's default, documented as best for sparse right-tailed graphs) against `preflow_push`, and pick the faster. Cut values don't depend on the choice.
- I'll report the timing and the projected corpus runtime to Acacia. If it runs to hours, I'll say so before going further, not after.

## Tests (`tests/test_network.py`)

1. **Karate:** tree cut values equal `cut_pairs` values for **all 561 pairs**. `tree_partition` between nodes 0 and 33 still misplaces only Zachary's individual 9.
2. **Planted toy:** under `--cuts tree`, the C1001–C2001 cut equals `truth["cross_edges"]`. Side sizes and the degenerate flag match `cut_pairs` for every candidate pair.
3. **Disconnected graph:** one tree per component, and cross-component pairs report `connected: False`.
4. **CLI `--cuts tree` end to end** on the toy: writes `gomory_hu.json`, has no member lists anywhere, and the summary counts match `cuts.json`.

## Records

- **DECISIONS** (one row, Claude conventions): `--cuts tree` for large candidate sets; values exact and identical to pairwise; partitions may differ from `nx.minimum_cut` when a pair has several minimum cuts (tie rule: edge nearest s); member lists not stored in tree mode (the tree encodes them); flow function chosen by benchmark.
- **HUMAN.md**: update the Kirkley run section. Rerun `facct27.hubs` for the new table (output-only change, seconds). Add the CM-candidate command `network ... --candidates kirkley --cuts tree` with the measured runtime estimate. Note what to share back (summary block plus `gomory_hu.json` if the satellite subtrees are to be looked at).
- **Commits** (author Claude): (1) table, (2) benchmark result + Gomory–Hu + tests, (3) DECISIONS + HUMAN.md. Nothing is pushed.

## Verification

- `uv run pytest`: all existing tests plus the new ones pass.
- Toy smoke runs: `facct27.hubs` shows ER and CM columns in both blocks; `network --candidates kirkley --cuts tree` writes the tree and the summary.
- The benchmark timing is reported before Acacia runs it on the corpus.

## Not included

- Satellite analysis of the tree (subtrees hanging off cheap edges). The tree file makes it possible; interpretation comes after seeing it.
- Reciprocity and post-vs-comment splits for C653. These are cheap follow-ups, not requested yet.
