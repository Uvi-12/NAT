# APF in public code, methodology

This study asks how far the exposed default spreads beyond the audited corpus, using
only public GitHub data. It uses only the global search endpoints and the public raw
CDN, so anyone with a GitHub account can re-run it. There are three measurements,
each answering a narrow question.

## A. Adoption within the audited corpus

- **Population:** the 79-system corpus. 78 systems have a public repository. AWS Step
  Functions is closed-source.
- **Data:** `stargazers_count` for each repository, read from `search/repositories`
  (`collect.py`). 73 of the 78 repositories resolved.
- **Classes:** exposed means Exposed, Conditional, or Transitive. The other classes
  are resistant and N/A.
- **Output:** each class's share of repositories and of stars.
- **Scope:** stars measure adoption, not installations. The claim is comparative and
  holds only within the corpus.

## B. Keyword-search hits

- **Query:** for each exposed framework, a keyword query for its human-in-the-loop
  API (`data/frame_queries.csv`).
- **Data:** `total_count` from `search/code` (`collect_bc.py`).
- **What the counts include:** the queries are bags of words, and hits include
  documentation, forks, and vendored copies. Large counts are approximate.
- **Use:** B is an order-of-magnitude indicator, not a census of deployed gates.
- **Query mismatch:** for CrewAI, Haystack, and AutoGen the queried API differs from
  the surface on which the corpus verdict rests. `RESULTS.md` lists the mismatch and
  reports C for the five matching frameworks separately.

## C. Sampled files

**Frame.** The first page (up to 30 results) of each B query, in GitHub's ranking.
This is a convenience sample.

**Predicate.** `classify.py` is lexical and works at file level:
- **Gated:** the file contains an approval/resume keyword.
- **Verified:** it also contains a cryptographic-provenance or fresh-re-authorization
  token. The tokens are HMAC, Ed25519, ECDSA, `verify_signature`, `jwt.decode`,
  `compare_digest`, X.509, public or private key, nonce, reauth, Sigstore, cosign, and
  in-toto.
- **Trusts-state:** a gated file without such a token.
- **Not applicable:** a file with no gate keyword.

**Estimator.**
- The proportion of trusts-state among applicable files, with a Wilson 95% interval.
- Reported for all files and for source-code files. Documentation/data extensions are
  defined as `DOC_EXT` in `analyze.py`.
- The interval describes the sample, not all public code.

**Error directions.**
- A false verified label lowers the estimate.
- A verifier located outside the sampled file produces a false trusts-state label,
  which raises it.
- The predicate does not confirm that the approval is read from persisted state.

**Validation.**
- The 25-file sample was re-read at pinned commits (2026-11-03). None of the 11 files
  the predicate marked *verified* actually verifies approval evidence (their crypto
  serves transport, blob-URL, OAuth, or app-key purposes). 11 of 25 sampled files are
  not approval gates at all. Of the 14 that are genuine gates, all 14 trust stored
  state (0 verified).
- An earlier, looser predicate was replaced after it matched Python function
  signatures.
- The predicate errs in both directions (unrelated crypto counts as verified; a
  verifier that avoids the tokens is missed), so the figures are detected-signal
  rates for the sampled repositories, not measures of true absence or population
  estimates. The repository-level measurement (D) is reported the same way.
- Per-file judgments, review status, and pinned commits are in `data/validation.csv`.

## Limits

- GitHub is the measured universe. Closed-source and non-GitHub deployments are out
  of frame.
- B counts are approximate keyword hits.
- C is a ranked convenience sample with a lexical, file-level predicate. Its result
  describes public material that uses these APIs, not exploitable deployments.
- The frozen data are a snapshot from 2026-11-02, and live searches will differ.

## Privacy

Released per-file data identify files only by a truncated SHA-256 of
`repository/path`. No repository or path names are published.
