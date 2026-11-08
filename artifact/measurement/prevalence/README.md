# APF in public code

A reproducible, GitHub-based measurement of how far the exposed default spreads
beyond the audited corpus. `METHODOLOGY.md` gives the protocol and limits, and
`RESULTS.md` gives the numbers and what they do and do not support.

- **A. Adoption within the corpus.** The share of corpus repositories and of GitHub
  stars held by exposed vs. resistant systems.
- **B. Keyword-search hits.** Approximate code-search counts for each exposed
  framework's human-in-the-loop API.
- **C. Sampled files.** The share of search-ranked files using those APIs that
  contain no provenance-verification signal, for all files and for source code only,
  with descriptive Wilson intervals and hand validation.

## Files

- `data/repo_map.csv`: corpus systems mapped to GitHub repository and verdict (input).
- `data/repo_metrics.csv`: pulled stars and activity (A).
- `data/frame_queries.csv`: the keyword queries (input).
- `data/frame_counts.csv`: search hit counts (B).
- `data/sample_classified.csv`: sampled files as `file_id`, framework, extension, and
  label (C, pseudonymous).
- `data/validation.csv`: all 25 hand judgments (pseudonymous).
- `classify.py`: the lexical, file-level predicate.
- `collect.py` / `collect_bc.py`: GitHub collectors (need `gh` + network).
- `analyze.py`: recomputes A, B, and C offline (= claim 10).
- `figures/make_figures.py`: redraws the paper's Figures 3–5 from `data/`.

## Reproduce

- Offline: `python3 analyze.py`
- Figures: `python3 figures/make_figures.py`
- Re-collect from GitHub: `python3 collect.py && python3 collect_bc.py`. Live results
  will differ from the frozen snapshot.
