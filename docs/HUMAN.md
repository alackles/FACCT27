# Parked for the authors

Questions set aside for human thought. They aren't tasks for Claude, and nothing here has been acted on. When one is settled, move the outcome to `DECISIONS.md` and delete it here. The Reference section at the end holds run commands for analyses already done.

Figures are from `verify` on the 2026-10-08 snapshot, run 2026-10-19.

## To look at: the June 2026 hub surge

Seen 2026-10-21 in the ER month view (`--months --track 7`). In May and July 2026, C653 is the only ER hub. In June, a dozen or more other hubs appear alongside it: C1929 (a moderator, a hub only in June), C2713, C1211, C2914, and others. Two kinds of shape are involved. One is a dense region east of C653 where people tied together across the whole period are busy among themselves. The other is small stars at the edge of the layout, which most likely means June-only hubs whose repliers barely appear in any other month (inferred from how the whole-period layout places people).

C653, from the card (contexts-weighted). M is derived as in-degree ÷ share, so it is only good to about ±5:

| | C653 in-degree | Share | Repliers | M (derived) | Everyone else |
|---|---|---|---|---|---|
| 2026-05 | 571 | 27.2% | 408 | ~2,100 | ~1,530 |
| 2026-06 | 508 | 20.9% | 381 | ~2,430 | ~1,920 |
| 2026-07 | 435 | 25.3% | 333 | ~1,720 | ~1,280 |

Reading so far (Claude's, to check):
- C653's in-degree falls steadily, by about a quarter over two months. Repeat engagement per replier barely changes, so the loss is in repliers.
- June's drop in share is mostly the rest of the network growing (about +400 contexts against −60 for C653): new activity on top, with a modest decline at the center.
- July's recovery in share is relative. C653 fell again, but the June surge elsewhere fell faster.
- So far this looks like a shrinking single center with a one-month surge around it, not attention moving away from C653 and back.

Next checks, cheapest first:
1. Add up the in-degree of June's other ER hubs from the sidebar. Most of the ~+400 means the surge was concentrated in those hubs; a small part means it was spread thinly.
2. Compare May and June M in the monthly figure's strips. If they're similar, May (one hub) against June (many) is roughly volume-matched, and June isn't a volume effect.
3. Click C1929 in June: are its repliers eastern-region regulars or newcomers?
4. Newcomer share: the fraction of June's active people who first appear in June. This needs a small count-only addition to `hubs.py`, which Claude can build.
5. Is the July→August shift you saw in the monthly grid a separate event from June, or the same one seen through a different measure?

Caveat: the other six tracked hubs (C1923, C2534, C3456, C973, C3286, C3937) are the earliest hubs. They come from small early months and sit together at the edge of the layout. Check those months' strips for ER-wins flags before reading anything into them.

## To look at: Gomory–Hu cuts (Kirkley CM candidates)

The run is done (Reference, step 2), and the output is in `data/derived/2026-10-08/network-kirkley/`. `cut_summary` and the satellite list (each candidate's cut from the top hub) have been summarized, but you haven't looked at the cuts yourself yet. Known problem: the report's `cuts` list keeps every non-degenerate pair, about 75k rows, so `report.json` is 14.5 MB. The informative measures are the smaller side's size and cut ÷ strength, not the degenerate flag, which misses "candidate plus private following" cuts. `gomory_hu.json` (pseudonyms and cut values) is what a look at satellite subtrees would need.

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
   This prints two tables, in-degree and then out-degree, both contexts-weighted with ER and CM hubs. `hubs.csv` holds all four variants (in/out × contexts/unweighted), `hubs.json` adds the hub lists, and `degrees.csv` and `degrees_monthly.csv` feed the figures. It takes seconds.
2. **Pole-candidate cuts**, with the CM hubs as candidates and computed from a Gomory–Hu tree. Never run this without `--cuts tree`, since 492 candidates means ~120k pairs. The tree took 80 s on the corpus graph.
   `uv run python -m facct27.network data/processed/2026-10-08 --out data/derived/2026-10-08/network-kirkley --candidates kirkley --cuts tree`
   ER finds only one hub, so it has no candidate pairs. That result comes straight from the hubs output and needs no run.
3. **Figure: Kirkley cut-offs** on the whole-period degree sequences. Step 1 has to run first. Needs R with ggplot2 and dplyr. The PNG is counts only, but keep it local.
   `Rscript figures/hub_degrees.R data/derived/2026-10-08/hubs/degrees.csv data/derived/2026-10-08/figures/hub_degrees.png`
   **Monthly version:** one panel per calendar month, axes shared across panels, and each strip giving that month's N, M, and *h*\*. In-degree, contexts-weighted by default. Add `out` and/or `unweighted` as extra arguments for the other variants, each as a separate file.
   `Rscript figures/hub_degrees_monthly.R data/derived/2026-10-08/hubs data/derived/2026-10-08/figures/hub_degrees_monthly.png`
4. **Clickable hub views.** These use the same layout as the Louvain view. Clicking a hub in the sidebar highlights it and the people who replied to it. They're local files only.
   `uv run python -m facct27.viz data/processed/2026-10-08 --out data/derived/2026-10-08/network-hubs-ER.html --groups ER`
   `uv run python -m facct27.viz data/processed/2026-10-08 --out data/derived/2026-10-08/network-hubs-CM.html --groups CM`
   **By month:** add `--months` for a month selector (‹ › or the arrow keys) over the same fixed layout: each month lights who was active and lists that month's hubs, and a chosen hub is followed from month to month.
   `uv run python -m facct27.viz data/processed/2026-10-08 --out data/derived/2026-10-08/network-hubs-ER-months.html --groups ER --months --track 7`
   `--track 7` gives the first seven people to become ER hubs a fixed color each (filled = hub that month, ring = active but not a hub), and every other hub that month is dark grey. The sidebar lists the seven with their status each month.
   `uv run python -m facct27.viz data/processed/2026-10-08 --out data/derived/2026-10-08/network-hubs-CM-months.html --groups CM --months`
   Separate files per window (each with its own layout) still work with `--start`/`--end`.

Reading the hubs table:
- `ER<CM = yes` marks a window where ER compressed better, which is outside the regime where CM is guaranteed to win. Treat that window's *h*\* as low-confidence.
- *h*\* = 0 means the data don't justify hubs at that window's size. It isn't evidence that there are none.
- `*` after a pseudonym marks a moderator.
