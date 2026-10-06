# Decisions log

Conventions and methods-relevant implementation choices, one line of rationale each. Newest last.

| Date | Decision | Decided by | Rationale |
|---|---|---|---|
| 2026-10-06 | Claude drafts code; open-weight models perform corpus classification. Claude does not classify corpus content. | Acacia | Avoids the model classifying discourse about jailbreaking itself (value leakage, Betley et al. 2026); pinned weights aid reproducibility; may reduce refusals on jailbreak content. |
| 2026-10-06 | Submission core = network structure (Zachary-style community detection + nodes of influence) + close reading + structural comparison. Embedding/classifier pipeline is a secondary scaffold for possible revision. | Acacia | Network + close reading is a complete argument on its own and fits the Nov 3 deadline; classifier scaffold allows a fast response if reviewers request more systematic classification. |
| 2026-10-06 | Structural analysis is poles-first: identify the community's poles, then model partition between them (Zachary's flow/min-cut approach); community detection and centrality are cross-checks. | Acacia | Closer methodological fidelity to Zachary 1977 than centrality ranking. |
