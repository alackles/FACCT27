# Parked for the authors

Questions set aside for human thought. They aren't tasks for Claude, and nothing here has been acted on. When one is settled, move the outcome to `DECISIONS.md` and delete it here.

Figures are from `verify` on the 2026-10-08 snapshot, run 2026-10-19.

## To run: Kirkley hub analysis (added 2026-10-21)

The code is built and tested on synthetic data only (plan: `docs/plans/2026-10-21-kirkley-hub-identification.md`; decisions: DECISIONS rows dated 2026-10-21). It hasn't touched the corpus. Run from `FACCT27-workflow/`:

1. `uv run pytest` should show 58 passing.
2. Hubs by month and cumulatively:
   `uv run python -m facct27.hubs data/processed/2026-10-08 --out data/derived/2026-10-08/hubs`
   This prints two tables (in-degree, then out-degree; contexts-weighted; ER and CM hubs). `hubs.csv` holds all four variants (in/out × contexts/unweighted), and `hubs.json` adds the hub lists.
   *Rerun (updated 2026-10-21):* the printed table now shows ER and CM hubs, in-degree then out-degree. Only the printing changed, so rerun the same command; it takes seconds.
3. Pole-candidate cuts with Kirkley (CM) hubs as the candidates, computed from a Gomory–Hu tree. Don't run this without `--cuts tree`: 492 candidates means ~120k pairs.
   `uv run python -m facct27.network data/processed/2026-10-08 --out data/derived/2026-10-08/network-kirkley --candidates kirkley --cuts tree`
   Expected runtime: the tree took 12 s on a synthetic graph of similar size. Betweenness and closeness for the report run as before. (ER finds one hub, so no candidate pairs; that's read straight from the hubs output and needs no run.)
4. Share back the printed hubs tables, `hubs.csv`/`hubs.json` if you want the secondary runs looked at, and the network report's `candidates` and `cut_summary` blocks plus its `cuts` (non-degenerate pairs only). `gomory_hu.json` (pseudonyms and cut values) is what any look at satellite subtrees would need. All of these are counts and pseudonyms.

5. Figure: Kirkley cut-offs on the whole-period degree sequences (added 2026-10-21; Python analysis, R plotting). Rerun step 2 first so `degrees.csv` exists, then:
   `Rscript figures/hub_degrees.R data/derived/2026-10-08/hubs/degrees.csv data/derived/2026-10-08/figures/hub_degrees.png`
   It needs R with ggplot2 and dplyr only. The PNG is counts only, but keep it local.
6. Clickable hub views (same layout as the Louvain view; click a hub in the sidebar to light up it and its repliers):
   `uv run python -m facct27.viz data/processed/2026-10-08 --out data/derived/2026-10-08/network-hubs-ER.html --groups ER`
   `uv run python -m facct27.viz data/processed/2026-10-08 --out data/derived/2026-10-08/network-hubs-CM.html --groups CM`
   Local files only, like the Louvain view.

Reading the table:
- `ER<CM = yes` marks a window where ER compressed better, i.e. outside the regime where CM is guaranteed to win. Treat that window's *h*\* as low-confidence.
- *h*\* = 0 means the data don't justify hubs at that window's size. It isn't evidence that there are none.
- `*` after a pseudonym marks a moderator.

Flag: a table in which one pseudonym is the hub every month makes that person easy to identify for anyone who knows the community. It's part of the open naming decision with Elliott.

## Missing comments and orphaned replies

The collected comments fall 37 short of Arctic Shift's `time_series` counts, 0.18% of 20,877. By month: 2026-02 −1, 03 −3, 05 −3, 06 −5, 07 −13, 08 −8, 09 −4. Posts and all other months match. Separately, 23 comments reply to a parent comment that isn't in the corpus.

- **Hypothesis (Claude's guess):** some of the 23 missing parents are among the 37 missing comments. The search endpoint and `time_series` would then disagree about a small set of comments for one shared reason.
- **Test:** look up the 23 parent ids by id through Arctic Shift. This is an API call and doesn't require reading the corpus. If the parents come back, the gap and the orphans share a cause. If they don't, the parents were never archived.
- **Why it matters:** each orphan is a reply edge with no target. Deciding how the graph treats them is a stage-2 edge-definition call either way. The gap itself is probably one sentence in the limitations section.

## `was_deleted_later` doesn't line up with `removal_type`

| | `was_deleted_later` | Sum of non-null `removal_type` |
|---|---|---|
| Posts | 910 | 937 (deleted 200 + moderator 669 + reddit 58 + content_takedown 10) |
| Comments | 862 | 1,314 (deleted 521 + removed 791 + removed by reddit 2) |

The two are close for posts and well apart for comments. Arctic Shift doesn't document what `was_deleted_later` counts, or how it relates to `removal_type`.

- **Why it matters:** the paper reports a count of self-deleted items (see the 2026-10-08 DECISIONS row). Until this is understood, take that number from `removal_type == "deleted"`, not from `was_deleted_later`.
- **Possible check:** cross-tabulate `was_deleted_later` against `removal_type` in `verify`. That's count-only, and a one-line change if wanted.
