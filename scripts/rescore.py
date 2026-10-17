"""Re-score a results file with a stricter scorer (no new model calls).

Run from the repo root:  python scripts/rescore.py [--set heldout]
Reads results/extended.csv (default) or results/heldout.csv and writes the matching *_rescored.csv.
Rows are grouped by setting and model.

Stricter than run_all.py in three ways:
  1. Error text ("could not be completed", ERROR:) is never correct, even on negative questions.
  2. Abstentions ("I don't know") are never correct.
  3. On positive questions (required_all set) an answer that denies the fact
     ("does not", "no containers", ...) is wrong even if it names the right container.
Negative questions accept only no / none / nothing (the word "not" is dropped).
"""
import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_all import SETS, display, ensure_model_column, has, load_questions, words  # same questions and matching

ERR = re.compile(r"could not be completed|^error", re.I)
ABSTAIN = re.compile(r"\b(i don'?t know|i do not know|not sure|cannot determine)\b", re.I)
DENY = re.compile(r"\b(does not|do not|doesn'?t|don'?t|no containers?|no other|none|not expose)\b", re.I)


def classify(answer, q):
    """Return (strict_ok, category). Categories: ok, error, abstain, denial, wrong."""
    a = answer or ""
    if ERR.search(a):
        return False, "error"
    if ABSTAIN.search(a):
        return False, "abstain"
    al = a.lower()
    must_all, must_any, must_not = words(q["required_all"]), words(q["required_any"]), words(q["forbidden"])
    if q["type"] == "negative":
        must_any = [w for w in must_any if w != "not"]
    if must_all and DENY.search(a):
        return False, "denial"
    if not all(has(al, w) for w in must_all):
        return False, "wrong"
    if must_any and not any(has(al, w) for w in must_any):
        return False, "wrong"
    if any(has(al, w) for w in must_not):
        return False, "wrong"
    return True, "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", dest="qset", choices=list(SETS), default="extended")
    args = ap.parse_args()
    src = SETS[args.qset]["csv"]
    dst = src.replace(".csv", "_rescored.csv")
    by_id = {q["id"]: q for q in load_questions(args.qset)}
    ensure_model_column(src)
    rows = list(csv.DictReader(open(src, encoding="utf-8")))
    for r in rows:
        ok, cat = classify(r["answer"], by_id[r["id"]])
        r["strict"], r["category"] = int(ok), cat
        r["_key"] = display(r["label"], r.get("model"))
    with open(dst, "w", newline="", encoding="utf-8") as f:
        fields = [k for k in rows[0].keys() if k != "_key"]
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    labels = list(dict.fromkeys(r["_key"] for r in rows))
    cats = ["ok", "error", "abstain", "denial", "wrong"]
    print("| Setting | Keyword | Strict | " + " | ".join(cats[1:]) + " |")
    print("|---|---|---|" + "---|" * (len(cats) - 1))
    for lab in labels:
        s_ = [r for r in rows if r["_key"] == lab]
        kw = sum(int(r["correct"]) for r in s_)
        st = sum(r["strict"] for r in s_)
        print(f"| {lab} | {kw}/{len(s_)} | {st}/{len(s_)} | " + " | ".join(str(sum(r["category"] == c for r in s_)) for c in cats[1:]) + " |")
    print("\nCells that changed (keyword -> strict):")
    for r in rows:
        if int(r["correct"]) != r["strict"]:
            print(f"  {r['_key']:<24} Q{r['id']:>2} {r['correct']} -> {r['strict']} ({r['category']}): {r['answer'][:70]}")
    print(f"\nSaved {dst}")


if __name__ == "__main__":
    main()
