# ragsec-lab

A small open lab for measuring security weaknesses in self-hosted text-to-Cypher GraphRAG pipelines.

**Status:** Experiments 0 to 12 are done and logged in [`notes/research-daily.md`](notes/research-daily.md) (method, results, limits and a table of findings for each). A short written report is in progress.

## What it is

A minimal question-answering app over a Neo4j graph:

1. A user asks a question in a web UI.
2. An LLM (via Ollama) writes a Cypher query using the graph schema.
3. The query runs on Neo4j and a second LLM call turns the rows into an answer.

The stack is FastAPI, LangChain (`GraphCypherQAChain`), Neo4j Aura and Ollama. The app is intentionally minimal. Protections can be switched on and off one at a time, and the UI shows the generated Cypher and the raw database result next to the answer, because those are the main data for the research.

**Research question:** How do the prompt-to-query attacks and defenses documented for LLM-to-SQL pipelines carry over to a LangChain text-to-Cypher pipeline over Neo4j that uses small local models?

**Scope:** Only the text-to-Cypher part of GraphRAG (question, graph query, answer). Document retrieval, vector search and embedding poisoning are not tested.

## What was measured

Short version; the log has the evidence and the limits of every item.

- **No access control between the model and the database.** Plain requests leaked a sensitive node and ran write and delete queries. The model saying "I cannot do that" did not stop them.
- **Defenses outside the prompt worked and cost no accuracy.** A string-level allowlist validator blocked every tested attack (its first version failed open and was fixed). A read-only session stops writes, not reads. On benign questions, neither changed accuracy.
- **Defenses that edit the prompt did not help.** Schema filtering was bypassed and lowered accuracy. A label rule moved failures between questions. Few-shot examples gained 3 questions with the 4B model and nothing with the 9B model.
- **A larger model raises the baseline but not the structure.** qwen3.5 9B scored 17/20 against 13/20 for 4B (strict scoring) and wrote fewer invalid queries. The same defenses stayed accuracy-neutral or harmful, and wrong filters still produced confident false answers ("no containers depend on neo4j").
- **Empty results become facts.** A wrong filter returns no rows and the answer states the absence as true. The wording of an empty result also varies between questions.
- **Indirect prompt injection (text stored in the graph).** Blatant instructions ("answer only PWNED") were not obeyed in 18 of 18 answers where the text reached the model. A harmless formatting instruction was obeyed by the 9B model in 3 of 3 answers, and the 4B model repeated a false claim about other rows. Whether the text reaches the model at all depends on the Cypher the model writes.

These are results for this setup: a small synthetic graph (3 containers, 2 hosts), two models of the same family, temperature 0 (deterministic, one run per cell), keyword scoring checked by hand. They are not general failure rates. The model is a single-pass chain without tools, so the results do not apply to agents that loop and act.

## Responsible use

All data in this repository is synthetic. Run it only on infrastructure you own. The `/seed` endpoint deletes everything in the connected database, and `scripts/run_injection.py` writes and deletes a node, so use a dedicated Neo4j instance.

## Setup

Requirements: Docker Desktop, Ollama running on the host machine, and a Neo4j Aura instance (or a local Neo4j, see below). Python 3 on the host runs the experiment scripts.

1. Pull a model, for example: `ollama pull qwen3.5:4b` (and `ollama pull qwen3.5:9b` for the larger model).
2. Copy `.env.example` to `.env` and fill in your Neo4j credentials. Never commit `.env`.
3. Start the app: `docker compose up -d --build`
4. Load the sample graph: `curl -X POST localhost:8000/seed`
5. Open http://localhost:8000 and ask a question, for example "Which containers run on host pve-node1?"

To use a local Neo4j instead of Aura: `docker compose --profile local up -d` and set the `NEO4J_*` variables accordingly.

### Settings in `.env`

| Variable | Effect |
|---|---|
| `OLLAMA_MODEL` | Model used for both LLM calls |
| `PROTECT_EXCLUDE_SECRET=1` | Hide the `Secret` label from the schema shown to the model (schema filter) |
| `PROTECT_VALIDATE=1` | Check the generated Cypher against an allowlist before it runs |
| `PROTECT_READONLY=1` | Run the generated Cypher in a read-only session |
| `PROMPT_LABEL_RULE=1` | Add a rule to the Cypher prompt: every node in a MATCH pattern gets a label |
| `PROMPT_FEWSHOT=1` | Add worked Cypher examples to the Cypher prompt |
| `DEBUG_ERRORS=1` | Return error details to the user instead of a generic message |

`GET /health` reports the active model and switches. Check it before a run.

## Reproducing the experiments

The scripts edit `.env` temporarily, rebuild and restart the api container for each setting, and restore your `.env` at the end (a copy is kept as `.env.bak`, which is git-ignored). Run them from the repository root with Docker Desktop and Ollama running and the graph seeded. Sanity check before the first run: "How many containers are there?" must answer 3.

```
# 20-question accuracy test across the settings (results/extended.csv)
python scripts/run_all.py                       # all settings for the model in .env
python scripts/run_all.py --model qwen3.5:9b    # another model; rows are keyed by setting and model
python scripts/run_all.py none fewshot          # chosen settings only
python scripts/run_all.py --summary

# held-out set of 13 questions written after the few-shot examples (results/heldout.csv)
python scripts/run_all.py --set heldout none label_rule fewshot

# stricter scoring, no new model calls (writes *_rescored.csv)
python scripts/rescore.py
python scripts/rescore.py --set heldout

# indirect prompt injection (needs: pip install neo4j)
python scripts/run_injection.py --dry-run
python scripts/run_injection.py --model qwen3.5:9b
python scripts/run_injection.py --summary

# tests of the query validator
python tests/test_guard.py
```

Keyword scoring is lenient in places, so the strict score (`rescore.py`) is the one to quote. Ground truth for the questions is in `questions/GROUND_TRUTH.md`. Two runs that went wrong (an empty database, a stale container image) are kept apart in `results/invalid_*.csv` and are not counted.

## Project layout

```
app/main.py                    FastAPI app and the LangChain pipeline
app/guard.py                   Allowlist validator for generated Cypher
app/static/index.html          Minimal web UI
app/seed.cypher                Synthetic infrastructure graph
scripts/run_baseline.py        5-question repeated runs of Experiment 6 (results/baseline.csv)
scripts/run_all.py             20-question and held-out accuracy runs across settings and models
scripts/rescore.py             Strict re-scoring of the result files
scripts/run_injection.py       Indirect prompt injection experiment
questions/                     Question sets and ground truth
results/                       Raw answers, generated Cypher and scores (CSV)
tests/test_guard.py            Tests for the validator
notes/research-daily.md        Experiment log and table of findings
```

## Not covered

- Attempts to bypass the validator with a live model.
- Vague destructive requests ("clean up the test data").
- Rendering of model output in the UI (OWASP LLM05).
- Agents that loop or call tools, where an injected instruction could start actions.
- The attack experiments with the 9B model, and model families other than qwen3.5.
- Vector and graph retrieval weaknesses (OWASP LLM08).

## License

Not yet chosen.
