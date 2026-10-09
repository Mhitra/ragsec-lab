"""Experiment 8: run the 20-question set once per setting against the running lab.

Usage (from the repo root):
  python scripts/run_extended.py "label for this setting"   run all questions, append to results/extended.csv
  python scripts/run_extended.py --summary                   print tables for all settings recorded so far

Questions come from questions/questions_extended.csv. An answer counts as correct when it contains
every word in required_all, at least one word in required_any (if any are listed), and none of the
forbidden words. This is a rough keyword check, so the full answer and generated Cypher are saved too.
The model is deterministic at temperature 0, so each question is asked once per setting.
"""
import csv
import datetime
import json
import os
import re
import sys
import urllib.request

URL = "http://localhost:8000"
QUESTIONS_PATH = os.path.join("questions", "questions_extended.csv")
CSV_PATH = os.path.join("results", "extended.csv")
FIELDS = ["time", "label", "protections", "id", "type", "question", "correct", "blocked", "answer", "cypher"]


def call(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(URL + path, data=data, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def words(cell):
    return [w.strip().lower() for w in (cell or "").split(";") if w.strip()]


def load_questions():
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def has(a, w):
    """Whole-word match, so 'no' does not match inside 'pve-node1' and '2' not inside 'senku02'."""
    return re.search(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])", a) is not None


def is_correct(answer, q):
    a = (answer or "").lower()
    must_all, must_any, must_not = words(q["required_all"]), words(q["required_any"]), words(q["forbidden"])
    if not all(has(a, w) for w in must_all):
        return False
    if must_any and not any(has(a, w) for w in must_any):
        return False
    return not any(has(a, w) for w in must_not)


def run(label):
    health = call("/health")
    prot = health.get("protections", {})
    print(f"Setting: {label}\nProtections reported by the app: {prot}\n")
    os.makedirs("results", exist_ok=True)
    new_file = not os.path.exists(CSV_PATH)
    questions = load_questions()
    correct_total = 0
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        for q in questions:
            try:
                r = call("/ask", {"question": q["question"]})
                answer, cypher, blocked = r.get("answer"), r.get("generated_cypher"), r.get("blocked")
            except Exception as e:  # network or timeout problems
                answer, cypher, blocked = f"ERROR: {e}", None, None
            ok = is_correct(answer, q)
            correct_total += ok
            w.writerow({"time": datetime.datetime.now().isoformat(timespec="seconds"), "label": label,
                        "protections": json.dumps(prot), "id": q["id"], "type": q["type"],
                        "question": q["question"], "correct": int(ok), "blocked": blocked,
                        "answer": answer, "cypher": cypher})
            f.flush()
            print(f"{'OK  ' if ok else 'FAIL'} Q{q['id']:>2} {q['type']:<9} {q['question']}")
    print(f"\nTotal: {correct_total}/{len(questions)} correct. Details saved in {CSV_PATH}")


def summary():
    if not os.path.exists(CSV_PATH):
        print("No results yet.")
        return
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8")))
    labels = list(dict.fromkeys(r["label"] for r in rows))
    ids = sorted({int(r["id"]) for r in rows})
    types = list(dict.fromkeys(r["type"] for r in sorted(rows, key=lambda r: int(r["id"]))))
    print("Per question (1 = correct)\n")
    print("| Setting | " + " | ".join(f"Q{i}" for i in ids) + " | Total |")
    print("|---|" + "---|" * (len(ids) + 1))
    for lab in labels:
        sel = {int(r["id"]): r for r in rows if r["label"] == lab}
        cells = [sel[i]["correct"] if i in sel else "-" for i in ids]
        tot = sum(int(sel[i]["correct"]) for i in ids if i in sel)
        print(f"| {lab} | " + " | ".join(cells) + f" | {tot}/{len(sel)} |")
    print("\nPer question type (correct/asked)\n")
    print("| Setting | " + " | ".join(types) + " | Blocked |")
    print("|---|" + "---|" * (len(types) + 1))
    for lab in labels:
        cells = []
        for t in types:
            sel = [r for r in rows if r["label"] == lab and r["type"] == t]
            cells.append(f"{sum(int(r['correct']) for r in sel)}/{len(sel)}")
        blocked = sum(1 for r in rows if r["label"] == lab and r["blocked"] == "True")
        print(f"| {lab} | " + " | ".join(cells) + f" | {blocked} |")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--summary":
        summary()
    elif len(sys.argv) == 2:
        run(sys.argv[1])
    else:
        print(__doc__)