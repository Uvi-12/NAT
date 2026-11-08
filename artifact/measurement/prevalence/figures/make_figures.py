#!/usr/bin/env python3
"""Regenerate the paper's three prevalence figures from the frozen data in ../data.
Needs matplotlib. Writes fig06_adoption.pdf, fig07_population.pdf, fig08_prevalence.pdf."""
import csv, os, sys
import matplotlib.pyplot as plt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, "..", "data")
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, ".."))
import style; style.apply()
from analyze import wilson, DOC_EXT
V, INK, INK2 = style.V, style.INK, style.INK2
W = 3.45

# ---- Fig A: adoption, by repositories and by stars ----
m = [r for r in csv.DictReader(open(os.path.join(D, "repo_metrics.csv"))) if r["resolved"] == "YES"]
cls = lambda v: "Exposed" if v in ("Exposed", "Conditional", "Transitive") else ("Resistant" if v == "Resistant" else "NA")
n_rep = {c: sum(cls(r["verdict"]) == c for r in m) for c in ("Exposed", "Resistant", "NA")}
n_star = {c: sum(int(r["stars"] or 0) for r in m if cls(r["verdict"]) == c) for c in n_rep}
tr, ts = sum(n_rep.values()), sum(n_star.values())
fig, ax = plt.subplots(figsize=(W, 0.94))
bars = [(f"Repositories\n(n = {tr})", [100*n_rep[c]/tr for c in n_rep], [n_rep[c] for c in n_rep]),
        (f"GitHub stars\n({ts/1e6:.2f} M)", [100*n_star[c]/ts for c in n_star], None)]
cols = [V["Exposed"], V["Resistant"], V["NA"]]
for i, (lab, vals, cnt) in enumerate(bars):
    y = 1-i; left = 0
    for j, (v, c) in enumerate(zip(vals, cols)):
        ax.barh(y, v, left=left, height=0.56, color=c, edgecolor="white", linewidth=1.0)
        if v > 8:
            s = f"{v:.1f}%" + (f"  ({cnt[j]})" if cnt else "")
            ax.text(left+v/2, y, s, ha="center", va="center", color="white",
                    fontsize=(7.4 if v > 15 else 6.0), fontweight=("bold" if v > 15 else "normal"))
        left += v
ax.set_yticks([1, 0]); ax.set_yticklabels([b[0] for b in bars], fontsize=7.2)
ax.set_xlim(0, 100); ax.set_ylim(-0.45, 1.75)
ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xticklabels(["0", "25", "50", "75", "100%"])
for s in ("right", "top", "left"): ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0)
for x, t, c in [(2, "Exposed", V["Exposed"]), (57, "Resistant", V["Resistant"]), (84, "N/A", V["NA"])]:
    ax.add_patch(plt.Rectangle((x, 1.43), 2.6, 0.17, color=c, lw=0, clip_on=False))
    ax.text(x+3.6, 1.515, t, va="center", fontsize=7.0, color=INK)
fig.savefig(os.path.join(HERE, "fig06_adoption.pdf")); plt.close(fig)

# ---- Fig B: keyword-search hit counts ----
fc = [r for r in csv.DictReader(open(os.path.join(D, "frame_counts.csv"))) if r["verdict"] == "Exposed" and r["count"].isdigit()]
LBL = {"LlamaIndex Workflows": "LlamaIndex Workflows"}
fw = sorted([(r["framework"], int(r["count"])) for r in fc], key=lambda t: t[1])
fig, ax = plt.subplots(figsize=(W, 1.28))
y = np.arange(len(fw)); vals = [v for _, v in fw]
ax.barh(y, vals, height=0.62, color=V["Exposed"], edgecolor="white", linewidth=0.6)
ax.set_xscale("log"); ax.set_xlim(8, 400000)
ax.set_yticks(y); ax.set_yticklabels([n for n, _ in fw], fontsize=7.0); ax.set_ylim(-0.6, len(fw)-0.4)
cap = max(vals)
for yi, v in zip(y, vals):
    ax.text(v*1.3, yi, f"{v:,}", va="center", ha="left", fontsize=6.7, color=INK2)
ax.set_xticks([10, 100, 1000, 10000, 100000]); ax.set_xticklabels(["10", "100", "1k", "10k", "100k"])
ax.set_xlabel("keyword-search hits for the framework's human-in-the-loop API (log scale)", fontsize=6.8, color=INK2)
for s in ("right", "top"): ax.spines[s].set_visible(False)
ax.text(0.985, 0.06, f"sum {sum(vals):,}", transform=ax.transAxes, ha="right", va="bottom",
        fontsize=7.6, fontweight="bold", color=V["Exposed"])
fig.savefig(os.path.join(HERE, "fig07_population.pdf")); plt.close(fig)

# ---- Fig C: repository-level absence of a provenance check (per framework + pooled) ----
rr = [r for r in csv.DictReader(open(os.path.join(D, "repo_scan.csv"))) if r["status"] == "ok"]
def _f(sub, col):
    n = len(sub); k = sum(r[col] != "True" for r in sub); p, lo, hi = wilson(k, n)
    return k, n, 100*p, 100*lo, 100*hi
fw = sorted({r["framework"] for r in rr},
            key=lambda f: (-_f([r for r in rr if r["framework"] == f], "verifier_near_approval")[2], f))
fr = [(f,) + _f([r for r in rr if r["framework"] == f], "verifier_near_approval") for f in fw]
pool = [("None anywhere",) + _f(rr, "verifier_anywhere"),
        ("None near approval",) + _f(rr, "verifier_near_approval")]
fig, ax = plt.subplots(figsize=(W, 1.66))
n = len(fr); ys = list(range(n+3))[::-1]; yr = ys[:n]; yp = ys[n+1:]
for (lab, k, m_, p, lo, hi), yy in zip(fr, yr):
    ax.plot([lo, hi], [yy, yy], color=V["Exposed"], lw=1.2, solid_capstyle="butt")
    ax.plot(p, yy, "o", ms=4.2, color=V["Exposed"], mec="white", mew=0.6, zorder=3)
    ax.text(101.6, yy, f"{k}/{m_}", va="center", ha="left", fontsize=6.6, color=INK2)
for (lab, k, m_, p, lo, hi), yy in zip(pool, yp):
    d = 0.32; strong = lab.endswith("approval")
    ax.fill([lo, p, hi, p], [yy, yy+d, yy, yy-d], color=(INK if strong else INK2), lw=0, zorder=3)
    ax.text(101.6, yy, f"{k}/{m_}", va="center", ha="left", fontsize=6.6,
            color=INK, fontweight=("bold" if strong else "normal"))
ax.axhline(ys[n], color=style.GRID, lw=0.8)
ax.axvline(pool[1][3], color=INK2, lw=0.6, ls=(0, (2, 2)), zorder=0)
ax.set_yticks(yr+yp); ax.set_yticklabels([r[0] for r in fr]+[p[0] for p in pool], fontsize=7.0)
for t in ax.get_yticklabels()[-2:]: t.set_fontweight("bold")
ax.set_xlim(20, 101.6); ax.set_ylim(min(yp)-0.8, max(yr)+0.8)
ax.set_xticks([20, 40, 60, 80, 100]); ax.set_xticklabels(["20", "40", "60", "80", "100%"])
ax.set_xlabel("repositories with no provenance check near approval (Wilson 95%)", fontsize=7.0, color=INK2)
for s in ("right", "top"): ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0)
ax.text(101.6, max(yr)+0.85, "$k/n$", ha="left", va="bottom", fontsize=6.6, color=INK2)
fig.savefig(os.path.join(HERE, "fig08_prevalence.pdf")); plt.close(fig)
print("figures written to", HERE)
