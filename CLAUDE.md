# FACCT27-workflow — data and analysis code

Code for a FAccT 2027 paper: a structural, computational discourse analysis of r/ClaudeAIJailbreak arguing that persona jailbreaks (e.g. ENI) work relationally and that the community's discursive architecture replicates grooming / coercive-control mechanics. The paper and full project overview live in `github.com/alackles/FACCT27-draft` (`PROJECT.md`).

## Planned pipeline (not yet built)

The submission rests on network structure plus close reading; classifier work is secondary and exists so it can be expanded if reviewers ask for it (decided 2026-10-06; see `docs/DECISIONS.md`). Build the core first and keep the secondary track to minimal, working stubs until the core is done.

### Core (submission)

1. **Collect** posts and comments from r/ClaudeAIJailbreak, keeping reply structure and timestamps. Scope (size, date range, access route) is not yet determined.
2. **Build the interaction graph.** What counts as an edge (a comment replying to a parent author, a mention, a co-thread) and whether edges are directed or weighted are authors' calls.
3. **Structural analysis in the style of Zachary, starting from the poles.** Identify the poles first: the figures the community organizes around, such as the creator of ENI, or whoever anchors a competing technique or a critical faction. Then model how the community partitions between them, using flow or minimum cut as Zachary did. Community detection (Girvan–Newman, with alternatives) and centrality (Freeman) act as cross-checks. They are not the primary method. Identifying the poles is the authors' call, and the method used to identify them goes in `docs/DECISIONS.md`. The question is what the structure shows that individual posts don't announce.
4. **Select texts for close reading** by network position: high-influence nodes, bridges between communities, and threads where techniques spread. The close reading and the structural comparison with accounts of coercive control and grooming are done by the authors. Claude builds retrieval and sampling tooling and does not interpret.

### Secondary (scaffold for possible revision)

Adapted from Pataranutaporn et al. 2025 ("My Boyfriend is AI"):

5. Embeddings → UMAP → k-means (elbow method) for thematic clusters.
6. LLM-assisted interpretation of clusters.
7. Open-weight classifiers over structured dimensions (see "Division of labor between models" below). **Classifier dimensions are undecided and are the authors' call**, because they encode the analytical lens.

Every implementation choice that could shape findings counts as methods documentation. Examples: sampling window, filtering, edge definition, centrality measure, the rule for selecting close-reading texts, cluster count, prompt wording, thresholds. Record each in `docs/DECISIONS.md` and mention it in the response.

## Data ethics — surface, don't decide

These decisions belong to the authors. Flag them whenever code touches them; never resolve them silently:

- Reddit Data API terms and the access route used.
- IRB scope for public community data.
- De-identification: hashing usernames vs. naming public creators (e.g. Spiritual Spell, who publishes ENI under that handle).
- Retention, storage location, and what (if anything) is released with the paper.

Fixed rules: raw and derived data are never committed (`data/` is gitignored); API keys go through `python-dotenv` and `.env`, never printed, logged, or committed.

## Jailbreak content

The corpus contains working jailbreak prompts. Code here classifies and analyzes them as text; it never executes them against a model to test whether they work.

## Division of labor between models

Decided by the authors (2026-10-06; see `docs/DECISIONS.md`): **Claude writes code; open-weight models do the classification.** Claude does not classify corpus content.

Why: if Claude were the classifier, it would be classifying discourse about jailbreaking Claude. Betley et al. 2026 (value leakage, in the paper bib) shows a model's own values can silently shape its answers. Open-weight models also give pinned, reproducible weights, can run locally so corpus data needn't go to a third-party API, and may refuse less on jailbreak content.

Implications for Claude's work here:

- Classifier prompts and codebook wording shape findings. Authors write them; if Claude drafts any, mark them as Claude-drafted and log it.
- Safety-tuned open-weight models can still refuse or hedge. Record refusals and non-answers as their own outcome; never silently drop or retry them.
- Model-model agreement measures consistency, not validity. How classifiers are validated (human-coded gold subset, exploratory/confirmatory split, etc.) is **open** — don't build evaluation code that presumes one design.
- Compute: Acacia's machine runs ~8B models locally; larger models go on the Lawrence cluster.
- Open: whether the same rule covers step 6 (LLM-assisted cluster interpretation). Ask before using Claude for it.

## Conventions

- Python. Prefer the simplest mechanism that does the job.
- Tests sized to stakes: data integrity, de-identification, sampling, and anything the paper reports a number from — not every branch.
- Commits by Claude: author `Claude <noreply@anthropic.com>` (Acacia stays committer), small, with messages that say what and why. End every message with a `Co-Authored-By: Claude <model name> <noreply@anthropic.com>` trailer. The trailer is how the model is recorded.
