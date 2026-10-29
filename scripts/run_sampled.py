"""Experiment 17: repeated, sampled runs (temperature > 0) of a question set, scored strictly, with resume.

Why: at temperature 0 a repeat adds nothing. Here every question is asked several times at a temperature
above 0, and stats.py takes the question as the unit (cluster bootstrap), so the intervals are honest.

Usage (repo root, Docker Desktop and Ollama running):
  python scripts/run_sampled.py --dry-run
  python scripts/run_sampled.py --set large --reps 5 --temperature 0.7 none fewshot
  python scripts/run_sampled.py --set large --sample 60 --reps 3 --model qwen3.5:9b none validate
  python scripts/run_sampled.py --summary [--set large]
  python scripts/run_sampled.py --assume-running --set heldout --reps 2 none    app already started by hand with the
                                                                                 wanted .env; nothing is edited or restarted
Rows go to results/sampled.csv. A run that stops can be started again with the same command: finished
(set, model, setting, temperature, rep, question) rows are skipped. Time: about 10-15 s per question for a 4B model,
so 157 questions x 5 repeats x 1 setting is roughly 2-3 hours; use --sample and fewer repeats first.
"""
import argparse
import csv
import datetime
import json
import os
import random
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_all import (DEFAULT_MODEL, ENV, KEYS, SETS, SETTINGS, call, env_value, is_correct, load_questions,  # noqa: E402
                     recreate_api, seed_graph, wait_for_health, write_env)
from rescore import classify  # noqa: E402

CSV_PATH = os.path.join("results", "sampled.csv")
FIELDS = ["time", "qset", "model", "setting", "temperature", "rep", "id", "type", "question", "correct", "strict",
          "category", "blocked", "answer", "cypher"]


def done_keys():
    if not os.path.exists(CSV_PATH):
        return set()
    return {(r["qset"], r["model"], r["setting"], r["temperature"], r["rep"], r["id"])
            for r in csv.DictReader(open(CSV_PATH, encoding="utf-8"))}


def main():
    ap = argparse.ArgumentParser(description="Sampled repeated runs with resume.")
    ap.add_argument("settings", nargs="*", help=f"settings (default: none). Valid: {list(SETTINGS)}")
    ap.add_argument("--set", dest="qset", choices=list(SETS), default="large")
    ap.add_argument("--model", default=None)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--sample", type=int, default=0, help="use only N questions (fixed random choice, seed 1)")
    ap.add_argument("--assume-running", action="store_true", help="do not edit .env or restart the api")
    ap.add_argument("--no-seed", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()
    if args.summary:
        from stats import sampled
        print(sampled(CSV_PATH, args.qset))
        return
    settings = args.settings or ["none"]
    bad = [s for s in settings if s not in SETTINGS]
    if bad:
        raise SystemExit(f"Unknown setting(s): {bad}. Valid: {list(SETTINGS)}")
    model = args.model or (None if args.assume_running else env_value("OLLAMA_MODEL", DEFAULT_MODEL))
    questions = load_questions(args.qset)
    if args.sample and args.sample < len(questions):
        rng = random.Random(1)
        questions = sorted(rng.sample(questions, args.sample), key=lambda q: int(q["id"]))
    total = len(settings) * args.reps * len(questions)
    print(f"Set {args.qset}: {len(questions)} questions x {args.reps} repeats x {len(settings)} settings = {total} calls "
          f"| temperature {args.temperature} | model {model or '(whatever the running app uses)'}")
    if args.dry_run:
        for s in settings:
            print(f"  {s}: {dict(zip(KEYS, SETTINGS[s]))}")
        return
    os.makedirs("results", exist_ok=True)
    by_id = {q["id"]: q for q in questions}
    if not args.assume_running:
        shutil.copyfile(ENV, ENV + ".bak")
    new_file = not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0
    done = done_keys()
    try:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new_file:
                w.writeheader()
            for setting in settings:
                if not args.assume_running:
                    write_env(dict(zip(KEYS, SETTINGS[setting])),
                              {"OLLAMA_MODEL": model, "OLLAMA_TEMPERATURE": str(args.temperature)})
                    recreate_api()
                health = wait_for_health()
                print(f"\n=== {setting}: app reports {health}")
                run_model = health.get("model")
                if model and run_model != model:
                    raise SystemExit(f"The app reports model {run_model!r}, expected {model!r}. Stopping.")
                if not args.assume_running and float(health.get("temperature", -1)) != args.temperature:
                    raise SystemExit(f"The app reports temperature {health.get('temperature')!r}, expected {args.temperature}. "
                                     "Rebuild the api image (main.py changed) and try again.")
                if not args.no_seed:
                    print("Seeded:", seed_graph(SETS[args.qset]["graph"]))
                for rep in range(1, args.reps + 1):
                    ok_n = 0
                    for q in questions:
                        key = (args.qset, run_model, setting, str(args.temperature), str(rep), q["id"])
                        if key in done:
                            continue
                        try:
                            r = call("/ask", {"question": q["question"]})
                            answer, cypher, blocked = r.get("answer"), r.get("generated_cypher"), r.get("blocked")
                        except Exception as e:
                            answer, cypher, blocked = f"ERROR: {e}", None, None
                        strict, cat = classify(answer, q)
                        ok_n += int(strict)
                        w.writerow({"time": datetime.datetime.now().isoformat(timespec="seconds"), "qset": args.qset,
                                    "model": run_model, "setting": setting, "temperature": args.temperature, "rep": rep,
                                    "id": q["id"], "type": q["type"], "question": q["question"],
                                    "correct": int(is_correct(answer, q)), "strict": int(strict), "category": cat,
                                    "blocked": blocked, "answer": answer, "cypher": cypher})
                        f.flush()
                    print(f"  repeat {rep}: strict {ok_n}/{len(questions)} (new rows only)")
    finally:
        if not args.assume_running:
            shutil.copyfile(ENV + ".bak", ENV)
            recreate_api()
            print("\nOriginal .env restored and api recreated.")
    print("\nDone. Summary:\n")
    from stats import sampled
    print(sampled(CSV_PATH, args.qset))


if __name__ == "__main__":
    main()
