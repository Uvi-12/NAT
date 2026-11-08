#!/usr/bin/env python3
"""Measurement B (population) + C (sample collection) via GitHub code search.

For each exposed-framework approval-API query: record the total_count (B, a
approximate keyword-search count), and collect candidate files (repo+path+branch) to
sample for classification (C). Spaced + backoff to respect search rate limits.
Fetches file text from the raw CDN (not the gated per-repo API) and classifies
with the conservative classifier. Writes data/frame_counts.csv and
data/sample_classified.csv."""
import csv, subprocess, json, time, urllib.request, os, sys, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classify import classify

D = "data"
queries = list(csv.DictReader(open(os.path.join(D, "frame_queries.csv"))))

def gh_search_code(q, per_page=30, retries=6):
    for a in range(retries):
        p = subprocess.run(["gh","api","-X","GET","search/code","-f",f"q={q}",
                            "-f",f"per_page={per_page}"], capture_output=True, text=True)
        if p.returncode == 0:
            try: return json.loads(p.stdout)
            except Exception: pass
        if "rate limit" in (p.stdout+p.stderr).lower() or "403" in p.stderr or "secondary" in (p.stdout+p.stderr).lower():
            time.sleep(20*(a+1)); continue
        time.sleep(8*(a+1))
    return None

def raw(repo, branch, path, timeout=12):
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None

def rec(fw, repo, path, label):
    """Released rows are pseudonymous: a hash of repository/path, never the name."""
    return {"file_id": hashlib.sha256(f"{repo}/{path}".encode()).hexdigest()[:16],
            "framework": fw, "ext": os.path.splitext(path)[1].lower() or "(none)", "label": label}

counts=[]; samples=[]
for row in queries:
    if row["verdict"] != "Exposed":   # sample frame = downstream users of EXPOSED APIs
        counts.append({"framework":row["framework"],"verdict":row["verdict"],"count":""}); continue
    res = gh_search_code(row["query"])
    time.sleep(7)
    if not res:
        counts.append({"framework":row["framework"],"verdict":row["verdict"],"count":"ERR"}); continue
    counts.append({"framework":row["framework"],"verdict":row["verdict"],"count":res.get("total_count",0)})
    for it in res.get("items", []):
        repo = it.get("repository",{}).get("full_name"); path = it.get("path")
        br = it.get("repository",{}).get("default_branch") or "main"
        if not repo or not path: continue
        txt = None
        for b in (br, "main", "master"):
            txt = raw(repo, b, path)
            if txt: break
        if txt is None: 
            samples.append(rec(row["framework"],repo,path,"FETCH_FAIL")); continue
        samples.append(rec(row["framework"],repo,path,classify(txt)))
        time.sleep(0.3)

with open(os.path.join(D,"frame_counts.csv"),"w",newline="") as fh:
    w=csv.DictWriter(fh,fieldnames=["framework","verdict","count"]); w.writeheader(); w.writerows(counts)
with open(os.path.join(D,"sample_classified.csv"),"w",newline="") as fh:
    w=csv.DictWriter(fh,fieldnames=["file_id","framework","ext","label"]); w.writeheader(); w.writerows(samples)
from collections import Counter
print("B counts:", {c["framework"]:c["count"] for c in counts if c["verdict"]=="Exposed"})
print("C sample labels:", dict(Counter(s["label"] for s in samples)), "n=",len(samples))
