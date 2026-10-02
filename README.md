# ragsec-lab

A small lab for testing security weaknesses in self-hosted GraphRAG pipelines.

**Status:** Work in progress. Experiments are logged in [`notes/research-daily.md`](notes/research-daily.md) as they are run.

## What it is

A minimal question-answering app over a Neo4j graph:

1. A user asks a question in a web UI.
2. An LLM (via Ollama) writes a Cypher query using the graph schema.
3. The query runs on Neo4j and a second LLM call turns the rows into an answer.

The stack is FastAPI, LangChain (`GraphCypherQAChain`), Neo4j Aura and Ollama. The app is intentionally minimal. Protections are meant to be added and removed one at a time during the experiments.

**Research question:** Which common misconfigurations and design flaws in self-hosted LLM/RAG systems create security risks?

The UI shows the generated Cypher and the raw database result next to the answer, because those are the main data for the research.

## Responsible use

All data in this repository is synthetic. Run it only on infrastructure you own. The `/seed` endpoint deletes everything in the connected database, so use a dedicated Neo4j instance.

## Setup

Requirements: Docker Desktop, Ollama running on the host machine, and a Neo4j Aura instance (or a local Neo4j, see below).

1. Pull a model, for example: `ollama pull qwen3.5:4b`
2. Copy `.env.example` to `.env` and fill in your Neo4j credentials. Never commit `.env`.
3. Start the app: `docker compose up -d --build`
4. Load the sample graph: `curl -X POST localhost:8000/seed`
5. Open http://localhost:8000 and ask a question, for example "Which containers run on host pve-node1?"

To use a local Neo4j instead of Aura: `docker compose --profile local up -d` and set the `NEO4J_*` variables accordingly.

## Project layout
app/main.py FastAPI app and the LangChain pipeline
app/static/index.html Minimal web UI
app/seed.cypher Synthetic infrastructure graph
notes/research-daily.md Experiment log and findings


## Planned experiments

- Prompt injection that leads to write or delete Cypher (OWASP LLM01)
- Leakage of sensitive data stored in the graph (LLM02)
- Unvalidated model output reaching the user or the database (LLM05)
- Vector and graph retrieval weaknesses (LLM08)

## License

Not yet chosen.