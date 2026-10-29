"""Run the 20-question set (or the held-out set) under the protection settings, automatically.

For each setting this script edits .env (protection switches and OLLAMA_MODEL), rebuilds and recreates
the api container, waits until /health answers, checks that the app reports the requested model and
switches, runs the questions and appends to the results file. At the end it restores your original .env
(a copy is also kept as .env.bak).

Usage (repo root, Docker Desktop and Ollama running):
  python scripts/run_all.py --dry-run                      show what would be written to .env, change nothing
  python scripts/run_all.py                                every setting with no results yet for the current model
  python scripts/run_all.py none fewshot                   only the named settings (re-runs them even if recorded)
  python scripts/run_all.py --model qwen3.5:9b             same, with another Ollama model (must be pulled)
  python scripts/run_all.py --set heldout none fewshot     held-out question set (results/heldout.csv)
  python scripts/run_all.py --set large none fewshot       larger graph, 157 questions (results/large.csv); the graph of each
                                                           question set is reseeded before its run (--no-seed to skip)
  python scripts/run_all.py --summary [--set heldout]      print the tables for results recorded so far
Results are labelled by setting and model. Rows recorded before the model column existed count as qwen3.5:4b.
"""
import argparse
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
DEFAULT_MODEL = "qwen3.5:4b"  # model of every row recorded before the model column existed
FIELDS = ["time", "label", "model", "protections", "id", "type", "question", "correct", "blocked", "answer", "cypher"]
SETS = {
    "extended": {"csv": os.path.join("results", "extended.csv"), "questions": None, "graph": "small"},
    "heldout": {"csv": os.path.join("results", "heldout.csv"), "questions": os.path.join("questions", "questions_heldout.csv"), "graph": "small"},
    # Experiment 17: larger graph (python scripts/gen_large.py writes app/seed_large.cypher and the questions)
    "large": {"csv": os.path.join("results", "large.csv"), "questions": os.path.join("questions", "questions_large.csv"), "graph": "large"},
}


def call(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(URL + path, data=data, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def seed_graph(name):
    """Load the small or the large graph through the app's /seed endpoint (it deletes everything first)."""
    req = urllib.request.Request(URL + f"/seed?graph_name={name}", data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def words(cell):
    return [w.strip().lower() for w in (cell or "").split(";") if w.strip()]


def load_questions(qset="extended"):
    path = SETS[qset]["questions"]
    if path is None:
        return QUESTIONS
    with open(path, newline="", encoding="utf-8") as f:
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


def display(label, model):
    return label if (model or DEFAULT_MODEL) == DEFAULT_MODEL else f"{label} [{model}]"


def ensure_model_column(path):
    """Old result files have no model column. Every earlier row used DEFAULT_MODEL."""
    if not os.path.exists(path):
        return
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        fields, rows = list(rd.fieldnames or []), list(rd)
    if "model" in fields or "label" not in fields:
        return
    i = fields.index("label") + 1
    fields = fields[:i] + ["model"] + fields[i:]
    for r in rows:
        r["model"] = DEFAULT_MODEL
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def run(label, model, questions, csv_path):
    health = call("/health")
    prot = health.get("protections", {})
    print(f"Setting: {display(label, model)}\nProtections reported by the app: {prot}\n")
    os.makedirs("results", exist_ok=True)
    ensure_model_column(csv_path)
    new_file = not os.path.exists(csv_path)
    correct_total = 0
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
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
            w.writerow({"time": datetime.datetime.now().isoformat(timespec="seconds"), "label": label, "model": model,
                        "protections": json.dumps(prot), "id": q["id"], "type": q["type"],
                        "question": q["question"], "correct": int(ok), "blocked": blocked,
                        "answer": answer, "cypher": cypher})
            f.flush()
            print(f"{'OK  ' if ok else 'FAIL'} Q{q['id']:>2} {q['type']:<9} {q['question']}")
    print(f"\nTotal: {correct_total}/{len(questions)} correct. Details saved in {csv_path}")


def summary(csv_path):
    if not os.path.exists(csv_path):
        print("No results yet.")
        return
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    for r in rows:
        r["_key"] = display(r["label"], r.get("model"))
    labels = list(dict.fromkeys(r["_key"] for r in rows))
    ids = sorted({int(r["id"]) for r in rows})
    types = list(dict.fromkeys(r["type"] for r in sorted(rows, key=lambda r: int(r["id"]))))
    print("Per question (1 = correct)\n")
    print("| Setting | " + " | ".join(f"Q{i}" for i in ids) + " | Total |")
    print("|---|" + "---|" * (len(ids) + 1))
    for lab in labels:
        sel = {int(r["id"]): r for r in rows if r["_key"] == lab}
        cells = [sel[i]["correct"] if i in sel else "-" for i in ids]
        tot = sum(int(sel[i]["correct"]) for i in ids if i in sel)
        print(f"| {lab} | " + " | ".join(cells) + f" | {tot}/{len(sel)} |")
    print("\nPer question type (correct/asked)\n")
    print("| Setting | " + " | ".join(types) + " | Blocked |")
    print("|---|" + "---|" * (len(types) + 1))
    for lab in labels:
        cells = []
        for t in types:
            sel = [r for r in rows if r["_key"] == lab and r["type"] == t]
            cells.append(f"{sum(int(r['correct']) for r in sel)}/{len(sel)}")
        blocked = sum(1 for r in rows if r["_key"] == lab and r["blocked"] == "True")
        print(f"| {lab} | " + " | ".join(cells) + f" | {blocked} |")


ENV = ".env"
KEYS = ["PROTECT_EXCLUDE_SECRET", "PROTECT_VALIDATE", "PROTECT_READONLY", "PROMPT_LABEL_RULE", "PROMPT_FEWSHOT"]
# label -> (exclude_secret, validate, readonly, label_rule, fewshot)
SETTINGS = {
    "none":          (0, 0, 0, 0, 0),
    "validate":      (0, 1, 0, 0, 0),
    "readonly":      (0, 0, 1, 0, 0),
    "schema_filter": (1, 0, 0, 0, 0),
    "all_three":     (1, 1, 1, 0, 0),
    "label_rule":    (0, 0, 0, 1, 0),
    "fewshot":       (0, 0, 0, 0, 1),
}


def read_env():
    with open(ENV, encoding="utf-8") as f:
        return f.read().splitlines()


def env_value(key, default=None):
    for line in read_env():
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip()
    return default


def style():
    """Use true/false if the existing file does, otherwise 1/0."""
    for line in read_env():
        k, _, v = line.partition("=")
        if k.strip() in KEYS and v.strip().lower() in ("true", "false"):
            return ("true", "false")
    return ("1", "0")


def write_env(values, strings=None):
    """values: on/off switches. strings: plain KEY=value settings such as OLLAMA_MODEL."""
    strings = strings or {}
    on, off = style()
    lines, seen = read_env(), set()
    out = []
    for line in lines:
        k = line.partition("=")[0].strip()
        if k in values:
            out.append(f"{k}={on if values[k] else off}")
            seen.add(k)
        elif k in strings:
            out.append(f"{k}={strings[k]}")
            seen.add(k)
        else:
            out.append(line)
    for k, v in values.items():
        if k not in seen:
            out.append(f"{k}={on if v else off}")
    for k, v in strings.items():
        if k not in seen:
            out.append(f"{k}={v}")
    with open(ENV, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


def recreate_api():
    # --build: the Dockerfile copies the code into the image, so a changed main.py needs a rebuild.
    subprocess.run(["docker", "compose", "up", "-d", "--build", "--force-recreate", "api"], check=True)


def wait_for_health(timeout=180):
    start = time.time()
    while time.time() - start < timeout:
        try:
            return call("/health")
        except Exception:
            time.sleep(3)
    raise SystemExit("The api did not answer /health within 3 minutes. Check: docker compose logs api")


def done_keys(csv_path):
    if not os.path.exists(csv_path):
        return set()
    return {(r["label"], r.get("model") or DEFAULT_MODEL) for r in csv.DictReader(open(csv_path, encoding="utf-8"))}


def main():
    ap = argparse.ArgumentParser(description="Run the question set under the protection settings.")
    ap.add_argument("settings", nargs="*", help=f"settings to run (default: all). Valid: {list(SETTINGS)}")
    ap.add_argument("--model", default=None, help="Ollama model (default: OLLAMA_MODEL from .env)")
    ap.add_argument("--set", dest="qset", choices=list(SETS), default="extended", help="question set")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--no-seed", action="store_true", help="do not reseed the graph that belongs to the question set")
    args = ap.parse_args()
    csv_path = SETS[args.qset]["csv"]
    if args.summary:
        summary(csv_path)
        return
    model = args.model or env_value("OLLAMA_MODEL", DEFAULT_MODEL)
    labels = args.settings or list(SETTINGS)
    unknown = [l for l in labels if l not in SETTINGS]
    if unknown:
        raise SystemExit(f"Unknown setting(s): {unknown}. Valid: {list(SETTINGS)}")
    questions = load_questions(args.qset)
    print(f"Question set: {args.qset} ({len(questions)} questions) | model: {model} | results: {csv_path}")
    dry = args.dry_run
    if not dry:
        shutil.copyfile(ENV, ENV + ".bak")
    already = done_keys(csv_path)
    try:
        for label in labels:
            if (label, model) in already and not args.settings:
                print(f"Skipping '{label}' for {model} (results already recorded)")
                continue
            values = dict(zip(KEYS, SETTINGS[label]))
            print(f"\n=== {label}: {values} | OLLAMA_MODEL={model}")
            if dry:
                continue
            write_env(values, {"OLLAMA_MODEL": model})
            recreate_api()
            health = wait_for_health()
            print("App reports:", health)
            if health.get("model") != model:
                raise SystemExit(f"The app reports model {health.get('model')!r}, expected {model!r}. Stopping.")
            if not args.no_seed:
                print("Seeded:", args.qset, "->", SETS[args.qset]["graph"], seed_graph(SETS[args.qset]["graph"]))
            run(label, model, questions, csv_path)
    finally:
        if not dry:
            shutil.copyfile(ENV + ".bak", ENV)
            recreate_api()
            print("\nOriginal .env restored and api recreated.")
    if not dry:
        print("\nDone. Summary:\n")
        summary(csv_path)


if __name__ == "__main__":
    main()
