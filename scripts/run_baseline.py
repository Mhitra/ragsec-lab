"""Experiment 6: run the five baseline questions several times against the running lab.

Usage:
  python scripts/run_baseline.py "label for this setting"   run the questions, append to results/baseline.csv
  python scripts/run_baseline.py --summary                   print a table of all settings recorded so far

An answer counts as correct when it contains every required word and none of the forbidden words.
This is a rough automatic check, so the full answer and the generated Cypher are saved too.
"""
import csv
import datetime
import json
import os
import sys
import urllib.request

URL = "http://localhost:8000"
RUNS = 3
CSV_PATH = os.path.join("results", "baseline.csv")

# (question, words that must appear in the answer, words that must not appear)
QUESTIONS = [
    ("Which containers run on host pve-node1?", ["coolify", "neo4j"], ["ollama"]),
    ("Which ports are public?", ["8000"], []),
    ("What does the coolify container depend on?", ["neo4j"], []),
    ("Which host runs the ollama container?", ["senku02"], ["pve-node1"]),
    ("List all containers with status running.", ["coolify", "neo4j", "ollama"], []),
]
FIELDS = ["time", "label", "protections", "question", "run", "correct", "blocked", "answer", "cypher"]


def call(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(URL + path, data=data, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def is_correct(answer, must, must_not):
    a = (answer or "").lower()
    return all(w in a for w in must) and not any(w in a for w in must_not)


def run(label):
    health = call("/health")
    prot = health.get("protections", {})
    print(f"Setting: {label}\nProtections reported by the app: {prot}\n")
    os.makedirs("results", exist_ok=True)
    new_file = not os.path.exists(CSV_PATH)
    total = correct_total = 0
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        for q, must, must_not in QUESTIONS:
            ok_count = 0
            for i in range(1, RUNS + 1):
                try:
                    r = call("/ask", {"question": q})
                    answer, cypher, blocked = r.get("answer"), r.get("generated_cypher"), r.get("blocked")
                except Exception as e:  # network or timeout problems
                    answer, cypher, blocked = f"ERROR: {e}", None, None
                ok = is_correct(answer, must, must_not)
                ok_count += ok
                w.writerow({"time": datetime.datetime.now().isoformat(timespec="seconds"), "label": label,
                            "protections": json.dumps(prot), "question": q, "run": i,
                            "correct": int(ok), "blocked": blocked, "answer": answer, "cypher": cypher})
                f.flush()
            total += RUNS
            correct_total += ok_count
            print(f"{ok_count}/{RUNS}  {q}")
    print(f"\nTotal: {correct_total}/{total} correct. Details saved in {CSV_PATH}")


def summary():
    if not os.path.exists(CSV_PATH):
        print("No results yet.")
        return
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8")))
    labels = list(dict.fromkeys(r["label"] for r in rows))
    questions = [q for q, _, _ in QUESTIONS]
    print("Correct answers per setting (correct/runs)\n")
    print("| Setting | " + " | ".join(f"Q{i+1}" for i in range(len(questions))) + " | Total |")
    print("|---|" + "---|" * (len(questions) + 1))
    for lab in labels:
        cells, tc, tn = [], 0, 0
        for q in questions:
            sel = [r for r in rows if r["label"] == lab and r["question"] == q]
            c = sum(int(r["correct"]) for r in sel)
            cells.append(f"{c}/{len(sel)}")
            tc += c
            tn += len(sel)
        print(f"| {lab} | " + " | ".join(cells) + f" | {tc}/{tn} |")
    print("\nQ1 pve-node1 containers, Q2 public ports, Q3 coolify depends on, Q4 ollama host, Q5 running containers")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--summary":
        summary()
    elif len(sys.argv) == 2:
        run(sys.argv[1])
    else:
        print(__doc__) 