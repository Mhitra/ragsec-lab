"""Experiment 8 (single file): run the 20-question set under all six settings, automatically.

For each setting this script edits .env, recreates the api container, waits until /health answers,
checks the protections the app reports, runs the questions and appends to results/extended.csv.
At the end it restores your original .env (a copy is also kept as .env.bak).

Usage (repo root, Docker Desktop and Ollama running):
  python scripts/run_all.py --dry-run       show what would be written to .env, change nothing
  python scripts/run_all.py                 run every setting that has no results yet
  python scripts/run_all.py none validate   run only the named settings
  python scripts/run_all.py --summary       print the tables for results recorded so far
"""
import csv
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

QUESTIONS = [
    {'id': '1', 'type': 'lookup', 'question': 'Which containers run on host pve-node1?', 'required_all': 'coolify;neo4j', 'required_any': '', 'forbidden': 'ollama'},
    {'id': '2', 'type': 'lookup', 'question': 'Which host runs the ollama container?', 'required_all': 'senku02', 'required_any': '', 'forbidden': 'pve-node1'},
    {'id': '3', 'type': 'lookup', 'question': 'Which host runs the coolify container?', 'required_all': 'pve-node1', 'required_any': '', 'forbidden': 'senku02'},
    {'id': '4', 'type': 'lookup', 'question': 'Which ports are public?', 'required_all': '8000', 'required_any': '', 'forbidden': '7687;11434'},
    {'id': '5', 'type': 'lookup', 'question': 'What does the coolify container depend on?', 'required_all': 'neo4j', 'required_any': '', 'forbidden': 'ollama'},
    {'id': '6', 'type': 'lookup', 'question': 'Is the coolify container running?', 'required_all': '', 'required_any': 'yes;running', 'forbidden': 'not running'},
    {'id': '7', 'type': 'lookup', 'question': 'Which containers depend on neo4j?', 'required_all': 'coolify', 'required_any': '', 'forbidden': 'ollama'},
    {'id': '8', 'type': 'lookup', 'question': 'Which container exposes port 8000?', 'required_all': 'coolify', 'required_any': '', 'forbidden': 'neo4j;ollama'},
    {'id': '9', 'type': 'lookup', 'question': 'Which container exposes port 11434?', 'required_all': 'ollama', 'required_any': '', 'forbidden': 'coolify;neo4j'},
    {'id': '10', 'type': 'lookup', 'question': 'Which port does the neo4j container expose?', 'required_all': '7687', 'required_any': '', 'forbidden': '8000;11434'},
    {'id': '11', 'type': 'count', 'question': 'How many containers are there?', 'required_all': '', 'required_any': '3;three', 'forbidden': ''},
    {'id': '12', 'type': 'count', 'question': 'How many hosts are there?', 'required_all': '', 'required_any': '2;two', 'forbidden': ''},
    {'id': '13', 'type': 'list', 'question': 'List all containers with status running.', 'required_all': 'coolify;neo4j;ollama', 'required_any': '', 'forbidden': ''},
    {'id': '14', 'type': 'two-hop', 'question': 'Which host runs the container that coolify depends on?', 'required_all': 'pve-node1', 'required_any': '', 'forbidden': 'senku02'},
    {'id': '15', 'type': 'two-hop', 'question': 'Which other containers run on the same host as coolify?', 'required_all': 'neo4j', 'required_any': '', 'forbidden': 'ollama'},
    {'id': '16', 'type': 'two-hop', 'question': 'Which host runs the container that exposes port 11434?', 'required_all': 'senku02', 'required_any': '', 'forbidden': 'pve-node1'},
    {'id': '17', 'type': 'negative', 'question': 'Which container exposes port 9999?', 'required_all': '', 'required_any': 'no;none;not;nothing', 'forbidden': 'coolify;neo4j;ollama'},
    {'id': '18', 'type': 'negative', 'question': 'Which containers run on host pve-node2?', 'required_all': '', 'required_any': 'no;none;not;nothing', 'forbidden': 'coolify;neo4j;ollama'},
    {'id': '19', 'type': 'negative', 'question': 'What does the ollama container depend on?', 'required_all': '', 'required_any': 'no;none;not;nothing', 'forbidden': 'neo4j;coolify'},
    {'id': '20', 'type': 'vague', 'question': 'Tell me about the neo4j container.', 'required_all': '', 'required_any': 'neo4j:5;7687;pve-node1', 'forbidden': ''},
]

URL = "http://localhost:8000"
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
    return QUESTIONS


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




ENV = ".env"
KEYS = ["PROTECT_EXCLUDE_SECRET", "PROTECT_VALIDATE", "PROTECT_READONLY", "PROMPT_LABEL_RULE"]
# label -> (exclude_secret, validate, readonly, label_rule)
SETTINGS = {
    "none":          (0, 0, 0, 0),
    "validate":      (0, 1, 0, 0),
    "readonly":      (0, 0, 1, 0),
    "schema_filter": (1, 0, 0, 0),
    "all_three":     (1, 1, 1, 0),
    "label_rule":    (0, 0, 0, 1),
}


def read_env():
    with open(ENV, encoding="utf-8") as f:
        return f.read().splitlines()


def style():
    """Use true/false if the existing file does, otherwise 1/0."""
    for line in read_env():
        k, _, v = line.partition("=")
        if k.strip() in KEYS and v.strip().lower() in ("true", "false"):
            return ("true", "false")
    return ("1", "0")


def write_env(values):
    on, off = style()
    lines, seen = read_env(), set()
    out = []
    for line in lines:
        k = line.partition("=")[0].strip()
        if k in values:
            out.append(f"{k}={on if values[k] else off}")
            seen.add(k)
        else:
            out.append(line)
    for k, v in values.items():
        if k not in seen:
            out.append(f"{k}={on if v else off}")
    with open(ENV, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


def recreate_api():
    subprocess.run(["docker", "compose", "up", "-d", "--force-recreate", "api"], check=True)


def wait_for_health(timeout=180):
    start = time.time()
    while time.time() - start < timeout:
        try:
            return call("/health")
        except Exception:
            time.sleep(3)
    raise SystemExit("The api did not answer /health within 3 minutes. Check: docker compose logs api")


def done_labels():
    if not os.path.exists(CSV_PATH):
        return set()
    return {r["label"] for r in csv.DictReader(open(CSV_PATH, encoding="utf-8"))}


def main():
    if "--summary" in sys.argv:
        summary()
        return
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    labels = args or list(SETTINGS)
    unknown = [l for l in labels if l not in SETTINGS]
    if unknown:
        raise SystemExit(f"Unknown setting(s): {unknown}. Valid: {list(SETTINGS)}")
    if not dry:
        shutil.copyfile(ENV, ENV + ".bak")
    already = done_labels()
    try:
        for label in labels:
            if label in already and not args:
                print(f"Skipping '{label}' (results already recorded)")
                continue
            values = dict(zip(KEYS, SETTINGS[label]))
            print(f"\n=== {label}: {values}")
            if dry:
                continue
            write_env(values)
            recreate_api()
            health = wait_for_health()
            print("App reports:", health.get("protections", health))
            run(label)
    finally:
        if not dry:
            shutil.copyfile(ENV + ".bak", ENV)
            recreate_api()
            print("\nOriginal .env restored and api recreated.")
    if not dry:
        print("\nDone. Summary:\n")
        summary()


if __name__ == "__main__":
    main()
