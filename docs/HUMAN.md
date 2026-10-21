# Parked for the authors

Questions set aside for human thought. They aren't tasks for Claude, and nothing here has been acted on. When one is settled, move the outcome to `DECISIONS.md` and delete it here. The Reference section at the end holds run commands for analyses already done.

Figures are from `verify` on the 2026-10-08 snapshot, run 2026-10-19.

## To look at: Gomory–Hu cuts (Kirkley CM candidates)

The run is done (Reference, step 2), and the output is in `data/derived/2026-10-08/network-kirkley/`. `cut_summary` and the satellite list (each candidate's cut from the top hub) have been summarized, but you haven't looked at the cuts yourself yet. Known problem: the report's `cuts` list keeps every non-degenerate pair, about 75k rows, so `report.json` is 14.5 MB. The informative measures are the smaller side's size and cut ÷ strength, not the degenerate flag, which misses "candidate plus private following" cuts. `gomory_hu.json` (pseudonyms and cut values) is what a look at satellite subtrees would need.

## Identifiability of the central hub

A table in which one pseudonym is the hub every month makes that person easy to identify for anyone who knows the community. This is part of the open naming decision with Elliott.

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

## Reference: replicating the Kirkley hub analysis

Plan: `docs/plans/2026-10-21-kirkley-hub-identification.md`. Decisions: the DECISIONS rows dated 2026-10-21. Run from `FACCT27-workflow/`, after `uv run pytest`, which should show 46 passing.

1. **Hubs by month and cumulatively:**
   `uv run python -m facct27.hubs data/processed/2026-10-08 --out data/derived/2026-10-08/hubs`
   This prints two tables, in-degree and then out-degree, both contexts-weighted with ER and CM hubs. `hubs.csv` holds all four variants (in/out × contexts/unweighted), `hubs.json` adds the hub lists, and `degrees.csv` feeds the figure. It takes seconds.
2. **Pole-candidate cuts**, with the CM hubs as candidates and computed from a Gomory–Hu tree. Never run this without `--cuts tree`, since 492 candidates means ~120k pairs. The tree took 80 s on the corpus graph.
   `uv run python -m facct27.network data/processed/2026-10-08 --out data/derived/2026-10-08/network-kirkley --candidates kirkley --cuts tree`
   ER finds only one hub, so it has no candidate pairs. That result comes straight from the hubs output and needs no run.
3. **Figure: Kirkley cut-offs** on the whole-period degree sequences. Step 1 has to run first. Needs R with ggplot2 and dplyr. The PNG is counts only, but keep it local.
   `Rscript figures/hub_degrees.R data/derived/2026-10-08/hubs/degrees.csv data/derived/2026-10-08/figures/hub_degrees.png`
4. **Clickable hub views.** These use the same layout as the Louvain view. Clicking a hub in the sidebar highlights it and the people who replied to it. They're local files only.
   `uv run python -m facct27.viz data/processed/2026-10-08 --out data/derived/2026-10-08/network-hubs-ER.html --groups ER`
   `uv run python -m facct27.viz data/processed/2026-10-08 --out data/derived/2026-10-08/network-hubs-CM.html --groups CM`

Reading the hubs table:
- `ER<CM = yes` marks a window where ER compressed better, which is outside the regime where CM is guaranteed to win. Treat that window's *h*\* as low-confidence.
- *h*\* = 0 means the data don't justify hubs at that window's size. It isn't evidence that there are none.
- `*` after a pseudonym marks a moderator.
