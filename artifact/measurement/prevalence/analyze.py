#!/usr/bin/env python3
"""Aggregate the three APF-prevalence measurements and print headline numbers.

A: adoption/reach (data/repo_metrics.csv), stars by exposure class.
B: downstream population (data/frame_counts.csv), approximate keyword-search hit counts.
C: sampled files (data/sample_classified.csv), fraction of search-ranked files
   using an exposed framework's human-in-the-loop API that contain no provenance-
   verification signal, for all files and for source code only, with Wilson 95%
   intervals that describe the sample. Stdlib only."""
import csv, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (p, max(0, c-h), min(1, c+h))


def A():
    rows = list(csv.DictReader(open(os.path.join(D, "repo_metrics.csv"))))
    res = [r for r in rows if r.get("resolved") == "YES"]
    cls = lambda v: "exposed" if v in ("Exposed", "Conditional", "Transitive") else ("resistant" if v == "Resistant" else "na")
    agg = {}
    for r in res:
        c = cls(r["verdict"]); a = agg.setdefault(c, {"n": 0, "stars": 0})
        a["n"] += 1; a["stars"] += int(r["stars"] or 0)
    print("== A. Adoption / reach (GitHub stars, resolved repos) ==")
    tot = sum(a["stars"] for a in agg.values())
    for c in ("exposed", "resistant", "na"):
        a = agg.get(c, {"n": 0, "stars": 0})
        sh = 100*a["stars"]/tot if tot else 0
        print(f"   {c:10} repos={a['n']:3} stars={a['stars']:>10,} ({sh:4.1f}% of corpus stars)")
    print(f"   corpus total stars={tot:,}  (resolved {len(res)}/{len(rows)})")
    return agg


def B():
    p = os.path.join(D, "frame_counts.csv")
    if not os.path.isfile(p):
        print("\n== B. (frame_counts.csv not yet collected) =="); return
    rows = list(csv.DictReader(open(p)))
    print("\n== B. Keyword-search hits (approximate counts) ==")
    exp = sum(int(r["count"] or 0) for r in rows if r["verdict"] == "Exposed" and (r["count"] or "").isdigit())
    for r in rows:
        if r["verdict"] == "Exposed" and (r["count"] or "").isdigit():
            print(f"   {r['framework']:22} {r['verdict']:9} hits={int(r['count']):>8,}")
        else:
            # resistant frameworks are the contrast set; their APIs re-verify on
            # resume, so they are not part of the exposed downstream population.
            print(f"   {r['framework']:22} {r['verdict']:9} (contrast set, not searched)")
    print(f"   exposed-framework approval-API hits: {exp:,}  (approximate keyword-search hit counts; include docs and copies)")


# File extensions treated as documentation/data rather than source code.
DOC_EXT = {".md", ".mdx", ".rst", ".txt", ".csv", ".json", ".yaml", ".yml", ".html", ".htm", "(none)"}


def _prev(rows, title):
    app = [r for r in rows if r["label"] in ("TRUSTS_STATE", "VERIFIED")]
    k = sum(r["label"] == "TRUSTS_STATE" for r in app)
    p, lo, hi = wilson(k, len(app))
    print(f"   {title:34} no provenance signal: {k}/{len(app)} = {p*100:.1f}%  "
          f"Wilson95% [{lo*100:.1f}%, {hi*100:.1f}%]")


def C():
    p = os.path.join(D, "sample_classified.csv")
    if not os.path.isfile(p):
        print("\n== C. (sample_classified.csv not yet collected) =="); return
    rows = list(csv.DictReader(open(p)))
    no_gate = sum(r["label"] == "NO_GATE" for r in rows)
    fail = sum(r["label"] == "FETCH_FAIL" for r in rows)
    print("\n== C. Sampled files using an exposed framework's human-in-the-loop API ==")
    print(f"   sampled={len(rows)}  no_gate={no_gate}  fetch_fail={fail}")
    _prev(rows, "all applicable files")
    _prev([r for r in rows if r["ext"] not in DOC_EXT], "source-code files only")
    print("   (intervals describe this search-ranked sample, not all public code)")
    print("   per framework (all files):")
    for fw in sorted({r["framework"] for r in rows}):
        _prev([r for r in rows if r["framework"] == fw], "  " + fw)



def D_repo():
    import os
    f = os.path.join(HERE, "data", "repo_scan.csv")
    if not os.path.exists(f):
        print("\n== D. (repo_scan.csv not yet collected) =="); return
    rows = [r for r in csv.DictReader(open(f)) if r["status"] == "ok"]
    n = len(rows)
    no_near = sum(r["verifier_near_approval"] != "True" for r in rows)
    no_any  = sum(r["verifier_anywhere"] != "True" for r in rows)
    dur     = sum(r["durable"] == "True" for r in rows)
    pn, ln, hn = wilson(no_near, n); pa, la, ha = wilson(no_any, n)
    print("\n== D. Repository-level verification (whole-repo scan) ==")
    print(f"   repositories that genuinely call an exposed API: {n}")
    print(f"   no provenance token NEAR approval/resume: {no_near}/{n} = {pn*100:.1f}%  (Wilson 95% [{ln*100:.1f}, {hn*100:.1f}])")
    print(f"   no provenance token ANYWHERE in repo:     {no_any}/{n} = {pa*100:.1f}%  (Wilson 95% [{la*100:.1f}, {ha*100:.1f}])")
    print(f"   carries a durable-resume mechanism:        {dur}/{n} = {dur/n*100:.1f}%")
    print("   detected-signal rates for this sample; the token test errs in both directions (unrelated crypto counts; untokenized verifiers missed)")
    print("   per framework (no token near approval):")
    for fw in sorted({r["framework"] for r in rows}):
        g = [r for r in rows if r["framework"] == fw]; k = sum(r["verifier_near_approval"] != "True" for r in g)
        print(f"     {fw:22} {k:3}/{len(g):3} = {k/len(g)*100:4.0f}%")

if __name__ == "__main__":
    A(); B(); C(); D_repo()
