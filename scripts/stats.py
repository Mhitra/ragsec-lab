"""Confidence intervals and paired tests for the ragsec-lab results (standard library only).

Why this exists: every cell in the report is one run over 13-20 questions, so a difference of one or two
questions is within noise. This script puts numbers on that.

Usage (repo root):
  python scripts/stats.py                       recorded runs (results/*_rescored.csv): Wilson CIs and exact McNemar tests
  python scripts/stats.py --out results/stats_existing.md
  python scripts/stats.py --sampled results/sampled.csv [--set large]
                                                repeated sampled runs (scripts/run_sampled.py): the unit is the
                                                question, intervals come from a cluster bootstrap over questions

Methods
  Wilson score interval (95%) for k correct out of n questions.
  Exact McNemar test (two-sided, binomial) for a setting against 'none' for the same model and the same
  questions: b = questions correct only with 'none', c = questions correct only with the setting.
  Cluster bootstrap (sampled data): resample questions with replacement, average the repeats of each question,
  take the 2.5th and 97.5th percentiles of 10000 resamples (fixed seed).
No multiple-comparison correction is applied; with many comparisons a few p < 0.05 are expected by chance.
"""
import argparse
import csv
import math
import os
import random
import sys
from collections import defaultdict

DEFAULT_MODEL = "qwen3.5:4b"


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value from the discordant counts."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def pct(x):
    return f"{100 * x:.0f}%"


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def existing(qset_files):
    out = []
    for qset, path in qset_files:
        if not os.path.exists(path):
            continue
        rows = read(path)
        for r in rows:
            r["model"] = r.get("model") or DEFAULT_MODEL
        models = list(dict.fromkeys(r["model"] for r in rows))
        labels = list(dict.fromkeys(r["label"] for r in rows))
        score = defaultdict(dict)  # (model, label) -> {id: strict}
        for r in rows:
            score[(r["model"], r["label"])][r["id"]] = int(r["strict"])
        out.append(f"### {qset} question set (strict score, 95% Wilson interval)\n")
        out.append("| Model | Setting | Correct | Interval | vs none: only none right (b) | only setting right (c) | exact McNemar p |")
        out.append("|---|---|---|---|---|---|---|")
        sig = 0
        comps = 0
        for m in models:
            base = score.get((m, "none"), {})
            for lab in labels:
                s = score.get((m, lab))
                if not s:
                    continue
                k, n = sum(s.values()), len(s)
                lo, hi = wilson(k, n)
                if lab == "none" or not base:
                    out.append(f"| {m} | {lab} | {k}/{n} | {pct(lo)}-{pct(hi)} | | | |")
                    continue
                ids = [i for i in s if i in base]
                b = sum(1 for i in ids if base[i] == 1 and s[i] == 0)
                c = sum(1 for i in ids if base[i] == 0 and s[i] == 1)
                p = mcnemar_exact(b, c)
                comps += 1
                sig += p < 0.05
                out.append(f"| {m} | {lab} | {k}/{n} | {pct(lo)}-{pct(hi)} | {b} | {c} | {p:.3f} |")
        out.append("")
        out.append(f"{comps} paired comparisons against 'none'; {sig} with p < 0.05 (uncorrected). "
                   f"With n = {len(next(iter(score.values())))} questions per cell, a difference of one or two questions "
                   "cannot be told from noise.\n")
    return "\n".join(out)


def sampled(path, qset=None):
    rows = read(path)
    if qset:
        rows = [r for r in rows if r.get("qset") == qset]
    if not rows:
        return "No sampled results yet."
    by = defaultdict(lambda: defaultdict(list))  # (model, setting) -> id -> [strict]
    for r in rows:
        by[(r["model"], r["setting"])][r["id"]].append(int(r["strict"]))
    rng = random.Random(20261029)

    def qmeans(d):
        return {i: sum(v) / len(v) for i, v in d.items()}

    def boot(vals, reps=10000):
        n = len(vals)
        res = []
        for _ in range(reps):
            res.append(sum(vals[rng.randrange(n)] for _ in range(n)) / n)
        res.sort()
        return res[int(0.025 * reps)], res[int(0.975 * reps)]

    out = ["| Model | Setting | Questions | Repeats per question | Mean strict accuracy | 95% bootstrap interval | Difference vs none (paired) | interval of the difference |",
           "|---|---|---|---|---|---|---|---|"]
    for (m, s), d in sorted(by.items()):
        qm = qmeans(d)
        ids = sorted(qm)
        vals = [qm[i] for i in ids]
        mean = sum(vals) / len(vals)
        lo, hi = boot(vals)
        reps = sorted({len(v) for v in d.values()})
        diff = dlo = ""
        if s != "none" and (m, "none") in by:
            bm = qmeans(by[(m, "none")])
            common = [i for i in ids if i in bm]
            dv = [qm[i] - bm[i] for i in common]
            if dv:
                diff_v = sum(dv) / len(dv)
                a, b = boot(dv)
                diff, dlo = f"{diff_v:+.3f}", f"[{a:+.3f}, {b:+.3f}]"
        out.append(f"| {m} | {s} | {len(ids)} | {'-'.join(map(str, reps))} | {mean:.3f} | [{lo:.3f}, {hi:.3f}] | {diff} | {dlo} |")
    out.append("")
    out.append("Repeats of one question are not independent; the interval treats the question as the unit.")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sampled", default=None, help="path to results/sampled.csv")
    ap.add_argument("--set", dest="qset", default=None, help="only this question set (sampled mode)")
    ap.add_argument("--out", default=None, help="also write the markdown to this file")
    args = ap.parse_args()
    if args.sampled:
        text = sampled(args.sampled, args.qset)
    else:
        text = existing([("20-question", os.path.join("results", "extended_rescored.csv")),
                         ("held-out (13 questions)", os.path.join("results", "heldout_rescored.csv"))])
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
        print(f"\nSaved {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
