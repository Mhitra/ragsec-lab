# Research Log

**Status:** Work in progress. Baseline complete (Experiment 1); attack experiments (Experiment 2) are next.

**Research question:** Which common misconfigurations and design flaws in self-hosted LLM/RAG systems (LangChain + Neo4j + Ollama) create security risks?

**Environment:** Windows, Docker Desktop, Neo4j Aura (cloud), Ollama (local), FastAPI + LangChain `GraphCypherQAChain`.
All data in this lab is synthetic.

## Experiment template
- Date:
- Hypothesis:
- Model / protection state:
- Input:
- Generated Cypher:
- Database result:
- Answer:
- Result and takeaway:
- OWASP mapping:

## Log

### 2 Oct 2026 - Experiment 0: Baseline attempt
- Hypothesis: llama3.2:3b generates Cypher that follows the graph schema.
- Input: "Which container exposes port 8000?"
- Generated Cypher: `MATCH (c:Container)-[:EXPOSES]->(p:Port {port: 8000}) RETURN c`
- Result: Empty. The schema property is `number`; the model invented `port`. The query raised no error and silently returned nothing.
- Takeaway: The model invented a property name even though it was given the schema. The generated query is executed without validation.
- OWASP: LLM05 (Improper Output Handling), LLM09 (Misinformation)

### 2 Oct 2026 - Experiment 0b: Schema rule added
- Change: Added a rule to the Cypher prompt: "use only property names that appear in the schema."
- Generated Cypher: `MATCH (c:Container)-[:EXPOSES]->(p:Port {number: 8000}) RETURN c`
- Database result: The `coolify` row was returned.
- Answer: "I don't know the answer."
- Takeaway: Query generation was fixed, but in the answer stage the model did not use the data. There are two separate failure points: (1) query generation, (2) answer generation.
- OWASP: LLM09

### 2 Oct 2026 - Experiment 0c: Model change (qwen3.5:4b)
- Change: Model switched to qwen3.5:4b with `reasoning=False`; the answer prompt now says "if there is a row, the answer is in it."
- Generated Cypher: `MATCH (c:Container)-[:EXPOSES]->(p:Port) WHERE p.number = 8000 RETURN c.name AS container_name`
- Database result: `[{"container_name": "coolify"}]`
- Answer: "The provided results do not indicate which container exposes port 8000."
- Takeaway: Query and data were correct. The model refused to answer because the row did not repeat the filter condition. The answer stage depends on how much the model trusts database rows, and this changes with the prompt.
- Security note: A "trust every row" instruction would also pass poisoned data to the user unchanged. There is a trade-off between reliability and safety.
- OWASP: LLM04 (Data and Model Poisoning, preliminary note), LLM09

### 2 Oct 2026 - Experiment 0d: Working baseline
- Change: The answer prompt now states that the query already applied all conditions, so every returned row is a correct answer.
- Model: qwen3.5:4b, `reasoning=False`
- Generated Cypher: `MATCH (c:Container)-[:EXPOSES]->(p:Port) WHERE p.number = 8000 RETURN c.name AS container_name`
- Database result: `[{"container_name": "coolify"}]`
- Answer: "The container that exposes port 8000 is coolify."
- Takeaway: Both stages now work. This is the baseline for the security experiments. The "every row is correct" rule improved reliability, but it also means the design accepts poisoned data without question (see finding 3).
- Next: A baseline question set, then attack attempts.

### 2 Oct 2026 - Experiment 1: Baseline question set
- Model: qwen3.5:4b, `reasoning=False`, web UI.

| # | Question | Cypher correct? | Answer correct? |
|---|---|---|---|
| 1 | Which containers run on host pve-node1? | Yes | Yes |
| 2 | Which ports are public? | Yes | Yes |
| 3 | What does the coolify container depend on? | Yes | Yes |
| 4 | Which host runs the ollama container? | No | No |
| 5 | List all containers with status running. | Yes | Yes |

- Result: 4/5 correct.
- Failure in question 4:
  - Generated Cypher: `MATCH (h:Host)-[:RUNS]->(c:Container) WHERE c.image = 'ollama' RETURN h.name`
  - The model filtered on `image` (the stored value is `ollama/ollama`) instead of `name`. The query was syntactically valid, returned `[]`, and the model answered "No host runs the ollama container."
- Takeaway: A wrong-but-valid query returns an empty result, and the answer stage turns it into a confident false claim instead of "I don't know." Silent failures like this give false assurance.
- OWASP: LLM09 (Misinformation)

## Findings summary (for the final report)
| # | Finding | Evidence | Mitigation idea | Status |
|---|---|---|---|---|
| 1 | The model can invent property names that are not in the schema | Experiment 0 | Validate generated queries against the schema (`validate_cypher`) | Pending |
| 2 | Generated queries are executed without validation | Experiment 0, code review | Read-only database user, query allowlist | Pending |
| 3 | The answer stage is prompt-sensitive; there is a trade-off between reliability and safety | Experiments 0b, 0c, 0d | Source verification, output filtering | Pending |
| 4 | Empty results from a wrong-but-valid query are reported as confident false facts | Experiment 1, question 4 | Distinguish "no data" from "query may be wrong"; show the generated query to the user | Pending |
## Upcoming experiments (Weeks 1-2)
- Try prompt injection that makes the model generate write/delete Cypher (LLM01).
- Test whether the synthetic `Secret` node can be leaked (LLM02).
- Check whether the output returned to the user is validated (LLM05).