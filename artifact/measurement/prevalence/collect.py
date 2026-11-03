#!/usr/bin/env python3
"""Measurement A collector: pull GitHub adoption (stars/activity) for each corpus
repo via the global search endpoint (no per-repo API). Writes data/repo_metrics.csv.
Needs `gh auth` and network. Rate-limit friendly (search is 30/min)."""
import csv, subprocess, json, time, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
rows = list(csv.DictReader(open(os.path.join(D, "repo_map.csv"))))
out = []
for r in rows:
    p = subprocess.run(["gh","api","-X","GET","search/repositories","-f",f"q=repo:{r['repo']}",
        "--jq",".items[0] | {stars:.stargazers_count, forks:.forks_count, pushed:.pushed_at, created:.created_at, archived:.archived}"],
        capture_output=True, text=True)
    rec = {**r,"stars":"","forks":"","pushed_at":"","created_at":"","archived":"","resolved":"NO"}
    if p.returncode == 0 and p.stdout.strip() and p.stdout.strip() != "null":
        try:
            d = json.loads(p.stdout)
            rec.update(stars=d.get("stars"), forks=d.get("forks"),
                       pushed_at=(d.get("pushed") or "")[:10], created_at=(d.get("created") or "")[:10],
                       archived=d.get("archived"), resolved="YES")
        except Exception: pass
    out.append(rec); time.sleep(2.2)
with open(os.path.join(D,"repo_metrics.csv"),"w",newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["system","layer","verdict","repo","stars","forks","pushed_at","created_at","archived","resolved"])
    w.writeheader(); [w.writerow({k:o.get(k,"") for k in w.fieldnames}) for o in out]
print("resolved", sum(1 for o in out if o["resolved"]=="YES"), "/", len(out))
