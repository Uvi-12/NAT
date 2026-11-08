# APF in public code, results

Collected from public GitHub on 2026-11-02 with the scripts and frozen data in this
directory. `METHODOLOGY.md` gives the protocol and its limits. `python3 analyze.py`
recomputes every number below from `data/` (standard library only, no network). 
`figures/make_figures.py` redraws the paper's Figures 3–5 from the same data.

## Headline

| | Measurement | Result |
| --- | --- | --- |
| **D** | **Repository-level verification (primary)** | Of **310** public repositories that genuinely call an exposed framework's human-in-the-loop API, **181 (58.4%)** contain no provenance-verification token in any file near their approval or resume code (Wilson 95% [52.8%, 63.7%]), **154 (49.7%)** contain none anywhere. The lexical token test errs toward crediting a verifier, so these bound absence from below. |
| **A** | Adoption within the audited corpus | Exposed systems (including conditional and transitive outcomes) are **72.6%** of the 73 resolved repositories (53) but **88.4%** of their 1,428,446 GitHub stars, resistant systems are 24.7% of repositories and 10.0% of stars. |
| **B** | Keyword-search hits | Keyword searches for eight exposed frameworks' human-in-the-loop APIs return **116,046** hits in total. These are approximate counts that include documentation, forks, and vendored copies. |
| C | Sampled files (supporting) | Of **209** search-ranked files that use an exposed framework's human-in-the-loop API, **201 (96.2%)** contain no provenance-verification signal (Wilson 95% interval [92.6%, 98.0%]). Restricted to the **111 source-code files**, **108 (97.3%)** contain none ([92.4%, 99.1%]). |

The intervals describe this search-ranked sample. They are not confidence
intervals for all public code.

## D. Repository-level verification (primary)

A file-ranked sample (C) cannot tell whether a verifier simply lives in another
file. D removes that blind spot by scanning whole repositories. For each of the
eight exposed frameworks we take code-search results for its human-in-the-loop API,
drop forks, vendored trees, framework copies, and first-party organizations, keep
one repository per owner, shuffle with a fixed seed, and for a fixed per-framework
sample confirm the API is really called, shallow-clone the repository (read-only. 
nothing from a clone is executed), and search all of its code for a
provenance-verification token (the predicate of `classify.py`) both anywhere and in
a file that also concerns approval or resume.

```
repositories that genuinely call an exposed API: 310
no provenance token NEAR approval/resume: 181/310 = 58.4%  (Wilson 95% [52.8, 63.7])
no provenance token ANYWHERE in repo:     154/310 = 49.7%  (Wilson 95% [44.1, 55.2])
carries a durable-resume mechanism:        206/310 = 66.5%
```

The token predicate has errors in both directions: a loose match credits a
repository with a verifier it does not have, and a genuine verifier that avoids the
matched tokens is missed. So 58.4% is a detected-signal rate for this sample, not a
measure of true absence or a population estimate. `data/repo_scan.csv` holds one row per repository, keyed
only by a salted hash of owner/name. `data/repo_scan_frame.json` holds the frame
sizes. `python3 analyze.py` recomputes these as measurement D. `repo_scan.py`
regenerates the scan from GitHub (needs a token and network).

## A. Adoption within the audited corpus

```
exposed    repos= 53 stars= 1,263,062 (88.4% of corpus stars)
resistant  repos= 18 stars=   143,256 (10.0% of corpus stars)
na         repos=  2 stars=    22,128 ( 1.5% of corpus stars)
corpus total stars = 1,428,446   (resolved 73/78; AWS Step Functions is closed-source)
```

Stars measure adoption, not installations, and the population is the audited corpus,
not all software. The finding is comparative: exposure is concentrated in the most
adopted projects of the corpus. Two exposed projects (n8n and Dify) account for about
a quarter of all corpus stars.

## B. Keyword-search hits

```
LangGraph            80,000*     OpenAI Agents SDK      614
AutoGen              13,024      LlamaIndex Workflows   633
CrewAI               11,712      Haystack               159
n8n                   9,888      Semantic Kernel         16
                                 sum                116,046
```

Each count is GitHub code search's `total_count` for the keyword query in
`data/frame_queries.csv`. The queries are bags of words, not call matches. Hits
include documentation, forks, and vendored copies. And `*` marks a value the search
API reports as approximate. Treat B as an order-of-magnitude indicator of how much
public material references each API, not as a count of deployed gates.

For three frameworks the queried human-in-the-loop API differs from the surface on
which the corpus verdict rests:

| Framework | Corpus verdict rests on | Query targets |
| --- | --- | --- |
| CrewAI | FlowPersistence state | `Task(human_input=True)` |
| Haystack | `AgentSnapshot` | `ConditionalRouter` human branch |
| AutoGen | serialized agent-chat state | `UserProxyAgent human_input_mode` |

Restricted to the five frameworks whose query matches the exposed surface, C gives
129/135 for all files and 68/70 for source code.

## C. Sampled files

**Frame.** For each framework, the first page (up to 30 results) of GitHub code
search for the B query, ranked by GitHub. This is a convenience sample, not a random
sample. 226 files were fetched from the raw CDN. 15 had no gate keyword and 2 could
not be fetched, leaving 209.

**Predicate** (`classify.py`). It works at file level and is lexical:
- A file counts as **gated** if it contains an approval/resume keyword.
- It is labelled **verified** if it also contains a cryptographic-provenance or
  fresh-re-authorization signal, and **trusts-state** otherwise.

It does not trace data flow, so it does not confirm that the approval is read from
persisted state, and a verifier kept in a different file is missed. About half the
209 files are documentation (98) rather than code (111). The code-only subset is the
primary reading for downstream code.

**Errors run in both directions.**
- A loose keyword can mislabel a file **verified**. This lowers the estimate.
- A verifier in another file can be labelled **trusts-state**. This raises it.

**Hand validation** (`data/validation.csv`, 25 files, identified by hash. re-read at
pinned commits on 2026-11-03):
1. A first predicate also matched the bare token `signature` (Python function
   signatures). It was replaced by crypto- and re-authorization-specific tokens.
2. The 11 files the classifier labelled **verified** were each opened and read. None
   verifies approval evidence before continuing: 9 gate on mutable state while their
   cryptography serves an unrelated purpose (transport/ingest HMAC, signed blob URLs,
   OAuth re-authentication, or application keys), and 2 are not approval gates. The
   lexical **verified** label did not hold in this sample.
3. Of the 14 files labelled **trusts-state**, 9 are not approval gates on inspection
   (data-model declarations, vendored human-in-the-loop engine code, tutorials, a
   resume). The other 5 are genuine gates.
4. Of the 14 sampled files that are genuine approval gates, all 14 trust stored
   state with no origin check (0 verified).

Implication: the lexical test both over-credits **verified** (unrelated crypto) and
can under-credit it (a verifier that avoids the matched tokens), and its search frame
admits non-gates, so C is reported as a detected-signal rate for this sample only,
not a measure of true absence. The audit above covers only the over-crediting
direction. Per-file notes and pinned commits are in `data/validation.csv`.

**Per framework** (all files): Haystack 15/15, LangGraph 30/30, LlamaIndex Workflows
30/30, CrewAI 29/30, OpenAI Agents SDK 29/30, AutoGen 28/29, Semantic Kernel 14/15,
n8n 26/30. LangGraph's 30 sampled files are all documentation.

## What this supports, and what it does not

It supports the following: in public material that uses these frameworks'
human-in-the-loop APIs, an explicit provenance-verification signal is rare in the
sampled files, for documentation and code alike. This matches the corpus-level
finding that the frameworks do not ask for one.

It does not support the following:
- a population prevalence for all deployments. 
- a claim that each sampled file is exploitable. 
- a claim that the sampled errors understate exposure.

## Privacy

Released per-file rows carry only `file_id` (the first 16 hex digits of SHA-256 of
`repository/path`), the framework, the file extension, and the label. No repository
or path names are published, so no individual developer's code is labelled.
Re-running `collect_bc.py` re-derives the same identifiers from live search results.

## Reproduce

```
python3 analyze.py                     # offline, recomputes A, B, C from data/ (= claim 10)
python3 figures/make_figures.py        # redraws Figs 3-5 (needs matplotlib)
python3 collect.py; python3 collect_bc.py   # re-collect from GitHub (needs gh auth + network;
                                            # live results will differ from the frozen data)
```
