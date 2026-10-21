# Plan: Kirkley hub identification for the reply network

## Context

Pole-candidate min-cuts (top-5 per centrality measure) gave degenerate cuts. There is no second node the network divides toward, only one dominant figure and some visual "satellites". Acacia chose Kirkley 2024 (MDL hub classification, *PRE* 109, 034310) to define "hub" with a stated criterion, then run it month by month and cumulatively. All decisions are logged in `FACCT27-workflow/docs/DECISIONS.md` (2026-10-21 rows, commits `d808280`..`55c0ef8`):
- contexts-weighted in-degree with multigraph encodings as primary, unweighted as secondary
- CM primary, with an ER-wins flag
- monthly and cumulative windows
- out-degree as a descriptive companion
- `--candidates {topk,kirkley}`, defaulting to topk
- implementation and validation conventions

Rarefaction is deferred (PROJECT.md, Future directions). The data boundary holds: everything is built and tested on synthetic data, Acacia runs it on the corpus, and only the summary table comes back.

## Reference code findings (`reference/kirkley/Network-hubs/functions.py`, read in full)

- It matches Eqs. 1–4 and 6–9. It adds whole degree blocks (our tie convention), scans all blocks, and takes the strict global minimum (our scan convention). It computes η as L\*/max(L0_ER, L0_CM).
- It uses natural log (`loggamma`, `np.log`), so its description lengths are in **nats**. The paper uses bits. *h*\* and η don't depend on the base. Description lengths are compared after multiplying ours by ln 2.
- `np.log(M)` with M = 0 gives −inf. We handle empty windows explicitly.
- Its Loubar `hub_degrees` uses the Average hub list (line 127). That's a bug, but irrelevant because we don't use Average or Loubar.

## Design

### New `src/facct27/kirkley.py`: the method only, no graph or IO code

- `logchoose(n, k)` and `logmultiset(n, k)` in bits via `math.lgamma / ln 2`. Both return 0 for k = 0, as in the reference.
- `scan(degrees, weighted)`: `degrees` maps node → k. Returns N, M, L0 / L\* / *h*\* / η for ER and CM, `er_wins` (L\*_ER < L\*_CM), *k*\* (lowest CM hub degree), and the CM and ER hub lists as `[node, k]`, sorted by degree descending, then by node. M = 0 or N < 2 returns *h*\* = 0 with `empty: true`.
- This is a pure function with no dependency on `network`, so `network.py` and `hubs.py` can both import it without a circular import.

### New `src/facct27/hubs.py`: windows, degrees, CLI

- `degree_sequence(D, direction="in", weighted=True)` covers every node in D, including degree-0 nodes. Weighted sums the `contexts` edge attribute. Unweighted counts edges. `out` uses the reversed direction.
- `months(comments)` gives calendar-UTC month boundaries from the first to the last comment `created_utc`. Boundaries come from the data, not hard-coded dates.
- `analyze(posts, comments, needs_review, mod_actions)`: for each series (monthly; cumulative from the first month's start to each month-end), it calls `network.build(start, end)` **once per window**, reusing every existing exclusion rule. It then runs `scan` for each of {in, out} × {contexts, unweighted}. One row per window × direction × weighting, with N, M, edge-rule counts, and the scan output.
- CLI: `uv run python -m facct27.hubs data/processed/<snap> --out data/derived/<snap>/hubs [--exclude-needs-review] [--exclude-mod-actions]`. Writes `hubs.json` (full rows including hub lists) and `hubs.csv` (scalar columns, ready for plotting), and prints a compact table of counts and pseudonyms only, safe to paste, matching `network.py`'s report convention.

### Changes to `src/facct27/network.py`

- `analyze(..., candidates="topk")` plus a CLI flag `--candidates {topk,kirkley}`, default `topk`, so existing runs reproduce exactly.
- Under `kirkley`, candidates are the CM in-hubs from `kirkley.scan` on D's in-degree, weighted by the run's `--weight` (default `contexts`, which matches DECISIONS; a `replies` sensitivity run stays internally consistent). `cut_pairs` runs on those candidates.
- The report gains `"candidates": {"rule", "h", "hubs", "er_wins"}`. *h*\* ≤ 1 yields `cuts: []` with `"note": "no candidate pairs"`. The top-k centrality listing stays in the report as description.

### Changes to `src/facct27/toy.py`

- `price(seed, T=100, m=4, alpha=2.7, start, step_days)` generates the growing network of Kirkley's Eq. 11. There are m seed nodes. Each step, a new node replies once (one thread) to each of m distinct existing nodes, chosen with probability ∝ (k_in + 1)^α. Before each step the clock is set to `start + t·step_days`, so steps fall into known months. Records reuse the `Toy` class through `toy.comment(new, toy.post(target))`. Returns (posts, comments, truth), where truth holds the seed names and per-step arrivals.

### Oracle fixture (one-time, outside the repo)

- A script in the session scratchpad loads `functions.py` by path via `importlib` and runs it with `uv run --no-project --with numpy --with scipy python -I`. It runs on about 6 synthetic degree sequences: uniform balls-in-bins, Zipf-like, a planted break (3 nodes far above the rest), a small sequence with ties, a sequence from the Price toy, and one sparse case. Each runs weighted and unweighted (unweighted sequences keep k ≤ N−1).
- The output goes to `tests/fixtures/kirkley_reference.json`: the input sequences, h_ER, h_CM, DLs in nats, η, and the reference repo's `git rev-parse HEAD`. Only numbers are committed, never Kirkley's code.

## Tests

`tests/test_kirkley.py` covers the method:
1. **Matches the reference code** on every fixture sequence, weighted and unweighted: *h*\* exact, η to 1e-9, DLs after ×ln 2.
2. **Uniform (Poisson-like) in-degrees give ER *h*\* = 0**, weighted, N = 1000, mean 100, several seeds (paper Fig. 2a).
3. **A planted break is recovered**: CM finds exactly the 3 high nodes.
4. **Ties are deterministic**: permuting node order gives the same hubs, and a tied block is all in or all out.
5. **Empty and degenerate windows** (M = 0, N = 1) return *h*\* = 0 and `empty`, without crashing.

`tests/test_hubs.py` covers the pipeline:
6. **Price growth with superlinear attachment** (α = 2.7, m = 4) through records → `build` → final cumulative window. CM *h*\* ≈ m and the hubs are the seed nodes (paper Fig. 3d). The exact assertion (for example, median over 10 seeds = m) gets set from the first run. If the paper's behavior doesn't reproduce, I report that rather than tune the test until it passes.
7. **Monthly windows partition interactions**: the interaction counts summed over months equal the whole-period count. The last cumulative window's degree sequence equals the whole-period graph's.
8. **The CLI runs end to end** on a toy snapshot: it writes `hubs.json` and `hubs.csv`, and output contains pseudonyms and counts only.

`tests/test_network.py` gets additions:
9. **`--candidates kirkley` on the planted two-community toy** includes both planted hubs as candidates and cuts between them. On a star (via `toy.from_graph`), *h*\* = 1 gives no pairs and the explicit note. Existing tests cover the topk default.

## DECISIONS (one new row, Claude conventions)

- `math.lgamma` replaces `scipy.special.gammaln` (same function, no new dependency). This corrects the 55c0ef8 row.
- The reference code works in nats, and comparisons convert.
- Empty windows are reported as `empty` with *h*\* = 0.
- Window boundaries come from the data.
- Kirkley candidates follow `--weight`.

## Commits (author Claude, small)

1. `kirkley.py` + oracle fixture + `test_kirkley.py`
2. `toy.price`
3. `hubs.py` + `test_hubs.py`
4. `network --candidates` + tests
5. DECISIONS row

Nothing is pushed.

## Verification

- `uv run pytest` passes, with all existing network, collect, and pseudonymize tests still green.
- `uv run python -m facct27.toy data/toy && uv run python -m facct27.hubs data/toy --out data/toy/hubs` produces readable output.
- `uv run python -m facct27.network data/toy --out data/toy/net --candidates kirkley` reports candidates and cuts.
- Acacia then runs `facct27.hubs` and `network --candidates kirkley` on `data/processed/2026-10-08` and shares only the printed tables.

## Not included

- Average and Loubar comparison columns. The reference code computes them, and they could support an appendix line like "ad hoc thresholds would have said X." I'd add them only if asked.
- Rarefaction (deferred).
- Hubs on the mention layer.
- Attachment-kernel estimation.
