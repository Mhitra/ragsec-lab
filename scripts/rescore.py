"""Re-score results/extended.csv with a stricter scorer (no new model calls).

Run from the repo root:  python scripts/rescore.py
Writes results/extended_rescored.csv and prints tables.

Stricter than run_all.py in three ways:
  1. Error text ("could not be completed", ERROR:) is never correct, even on negative questions.
  2. Abstentions ("I don't know") are never correct.
  3. On positive questions (required_all set) an answer that denies the fact
     ("does not", "no containers", ...) is wrong even if it names the right container.
Negative questions accept only no / none / nothing (the word "not" is dropped).
"""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_all import QUESTIONS, has, words  # reuse the same question set and matching

SRC = os.path.join("results", "extended.csv")
DST = os.path.join("results", "extended_rescored.csv")
BY_ID = {q["id"]: q for q in QUESTIONS}
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
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
    for r in rows:
        ok, cat = classify(r["answer"], BY_ID[r["id"]])
        r["strict"], r["category"] = int(ok), cat
    with open(DST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    labels = list(dict.fromkeys(r["label"] for r in rows))
    cats = ["ok", "error", "abstain", "denial", "wrong"]
    print("| Setting | Keyword | Strict | " + " | ".join(cats[1:]) + " |")
    print("|---|---|---|" + "---|" * (len(cats) - 1))
    for lab in labels:
        s = [r for r in rows if r["label"] == lab]
        kw = sum(int(r["correct"]) for r in s)
        st = sum(r["strict"] for r in s)
        print(f"| {lab} | {kw}/{len(s)} | {st}/{len(s)} | " + " | ".join(str(sum(r["category"] == c for r in s)) for c in cats[1:]) + " |")
    print("\nCells that changed (keyword -> strict):")
    for r in rows:
        if int(r["correct"]) != r["strict"]:
            print(f"  {r['label']:<14} Q{r['id']:>2} {r['correct']} -> {r['strict']} ({r['category']}): {r['answer'][:70]}")
    print(f"\nSaved {DST}")


if __name__ == "__main__":
    main()
