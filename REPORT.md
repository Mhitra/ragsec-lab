# Which protections work in a text-to-Cypher GraphRAG pipeline that runs on your own server? A small lab study

Mustafa Sekizkardeş, October 2026. Code, data and the full experiment log: https://github.com/Mhitra/ragsec-lab

> The numbers come from the log `notes/research-daily.md`.

## Abstract

I built a very small question-answering pipeline on a Neo4j graph. One model writes a Cypher query, the database runs the query, and a second model call writes the answer. Then I measured what goes wrong with small local models. I ran the experiments numbered 0 to 13 in the log with four models from two families (qwen3.5 4B and 9B, gemma3 4B, gemma4 e4b). With no protection, a plain question leaked a stored secret, and plain requests created and deleted data. Protections outside the prompt (a query allowlist, a read-only database session) stopped the attacks I tried and did not change the accuracy on normal questions. Protections that change the prompt (hiding schema names, adding rules or examples) did not help in a reliable way. Hiding schema names and adding a rule never raised the accuracy, and in some models they lowered it. Few-shot examples helped on the 20 questions in three of the four models, but little on a held-out set, and they moved some errors from one question to another. A bigger model raised the base score (from 13/20 to 17/20) but did not change this pattern, and a wrong query that returned nothing was still shown as a fact by three of the four models. The fourth model said "I don't know". Text placed in the database was not followed when it was obvious, but the bigger model followed a formatting instruction that looked harmless, and whether the placed text reached the model depended on the query the model wrote. The setup is small. The results show what is possible in this setup, not general error rates.

## 1. Introduction

This project came from my experience with running infrastructure. In January 2026, ransomware ran on a server I used. On the same server service, an attack was also made on another website from my server. I was held responsible for this, but later the logs showed that it did not come from me. After this I bought my own server, started to run my services on it, and began to study security in a more systematic way. There was no LLM in either incident. But now I host my services myself (Proxmox, Docker, Coolify), and an LLM tool that answers questions over infrastructure data is an obvious next step. So I wanted to know how such a tool breaks.

The structure of such a tool is simple: the user's text goes to a model, the model writes a database query, and the query runs with the credentials of the application. Every step is a place where something can go wrong. My question was this: how do the attacks and defenses described in the literature for text-to-SQL pipelines (Pedro et al., 2023) carry over to a text-to-Cypher pipeline on Neo4j when the model is small and local?

I measured four things: (1) what an unprotected pipeline allows, (2) what each defense stops, (3) how much answer quality each defense takes away, and (4) whether text stored in the database can steer the answers. I also repeated the accuracy and injection experiments with a bigger model from the same family, to see which results depend on the model size.

## 2. Setup

**Pipeline.** The user's question goes to a model that writes Cypher from the schema of the graph. The query runs on Neo4j Aura. A second model call turns the returned rows into an answer. The stack is FastAPI, LangChain (`GraphCypherQAChain`), Neo4j and Ollama. The web interface shows the generated Cypher and the database rows next to the answer.

```
question -> [model: write Cypher] -> [Neo4j] -> rows -> [model: write answer] -> answer
                 ^ protections act here          ^ injected text arrives here
```

**Data.** A small synthetic infrastructure graph: 3 containers, 2 hosts, 3 ports and one planted fake secret (`Container -[:HAS_SECRET]-> Secret`). All values are made up.

**Models.** qwen3.5:4b, qwen3.5:9b, gemma3:4b and gemma4:e4b through Ollama, temperature 0, reasoning off. At temperature 0 the same input gives the same output, so running a test again adds no statistical power. I ran each cell once.

**Protections.**

| Name | What it does |
|---|---|
| Schema filter | Hides the `Secret` label and `HAS_SECRET` from the schema shown to the model |
| Validator | Checks the generated Cypher against an allowlist before it runs (the query must start with `MATCH`, only allowed labels and relations, no write clauses, no namespaced function calls) |
| Read-only | Runs the generated Cypher in a read-only database session |
| Label rule | Adds one rule to the Cypher prompt: give a label to every node |
| Few-shot | Adds one rule and six solved examples to the Cypher prompt |

The first three are attack defenses. The last two are prompt changes that I tested because they change what the model sees.

**Questions and scoring.** A set of 20 questions (lookup, count, list, two-step, negative questions, one vague question) and a held-out set of 13 questions that I wrote after the few-shot examples were fixed. Each answer is checked with keywords. A strict re-score (no new model calls) counts error messages, "I don't know" answers and answers that deny a true fact as wrong. I report the strict score, because the keyword score counted two wrong answers as correct. The ground truth comes from the seed file.

## 3. Results

### 3.1 The unprotected pipeline has no access control (Experiment 2)

A plain question, "What secrets does the coolify container have?", returned the fake key and its value on the first try. No special wording was needed. Asking the model to create a node and to delete it also worked. In both cases the answer text said the model could not do it, but the query had already run, and a later question confirmed the change. What the model says is not proof of what happened. The weakness is in the design: anyone who can reach the question box can do what the database user can do.

### 3.2 Defenses outside the prompt (Experiments 3-5)

- **The schema filter failed.** Hiding the names did not hide the data. In one try the model guessed the hidden names from the word "secrets", attached them to the wrong node and gave the answer "no secrets": a wrong answer given with confidence. Two tries that named the label or the relation leaked the secret (2/2).
- **The read-only session stopped writes at the database** (Aura enforced the access mode), but it did not stop reads: the secret still leaked.
- **The allowlist validator blocked every attack I tried** (leak, create, delete, nodes without labels), but its first version failed open. A keyword blocklist let `SHOW DATABASES`, `RETURN apoc.version()` and similar commands pass. I rewrote it so that it accepts only the allowed query shape, and I tested it with 28 unit cases (7 allowed, 21 blocked). It is still a string-level check, not a Cypher parser.
- **With all three together, 3/3 attacks were blocked** and 3 of 5 normal questions were answered. The read-only layer was never reached, because the validator stopped everything first. So this run measures the validator, not defense in depth.
- Raw database errors reached the user and contained the database id. A generic error message (details only in the server log) closed this channel.

### 3.3 What the defenses cost in accuracy (Experiments 6, 8, 9, 10, 11, 13)

| Setting | qwen 4B | qwen 9B | gemma3 4B | gemma4 e4b |
|---|---|---|---|---|
| No protection | 13 | 17 | 13 | 16 |
| Validator | 13 | 17 | 13 | 16 |
| Read-only | 13 | 17 | 13 | 16 |
| Schema filter | 11 | 15 | 13 | 16 |
| All three | 11 | 15 | 13 | 16 |
| Label rule | 12 | 16 | 10 | 16 |
| Few-shot examples | 16 | 17 | 18 | 17 |

Strict score out of 20. Held-out set (13 questions, strict), no protection / label rule / few-shot: qwen 4B 8 / 9 / 10, qwen 9B 11 / 11 / 11, gemma3 8 / 7 / 9, gemma4 11 / 10 / 11.

- **The validator and the read-only session did not change any answer to a harmless question**, in all four models. In two models the validator blocked one harmless question (qwen 9B and gemma3): the model had written invalid text instead of Cypher, which fails in Neo4j anyway.
- **Prompt changes did not help in a reliable way.** The schema filter made the two qwen models lose two questions each and changed nothing in the gemma models. The label rule lost 1, 1, 3 and 0 questions. Neither one raised the accuracy in any model on the 20 questions. In the qwen 4B model, even though the model is deterministic, a one-line prompt change changed which questions failed.
- **Few-shot examples gained 3 questions with qwen 4B, nothing with qwen 9B, 5 with gemma3 and 1 with gemma4.** The examples removed the syntax errors of the 4B model (from 3 error answers to 0), but they did not remove the errors of meaning (the direction of a relation, a container name used as a host name), and they moved some of them to other questions. I wrote the examples after reading the errors, so the 20-question result is not a test of generalization. On the held-out set the gain was smaller (+2, 0, +1 and 0). The big gain of gemma3 (from 13 to 18) is partly the same effect, because the examples came from the errors of the qwen 4B model on these questions.
- Each cell is one run over 13-20 questions. A difference of one or two questions is not proof of an effect. Two first runs of gemma4 gave errors during a slow period of the laptop (it was on battery). I ran them again with the charger connected, and the first runs are kept apart (see section 8).

### 3.4 A bigger model raises the base score, not the structure (Experiments 11 and 13)

The 9B model without protection scored 17/20, and the 4B model scored 13/20. The 9B model answered all ten lookup questions correctly (4B: 7 of 10) and wrote far fewer invalid queries. The pattern stayed the same: the validator and read-only did not touch the accuracy, prompt changes were neutral or harmful, and some wrong queries were the same in both models. For example, both models used a container name as a host name (`Host {name: 'coolify'}`) and gave the answer "No other containers run on the same host as coolify." The same error appears in the two gemma models, and few-shot examples fixed it in all four. The gemma4 model made the same wrong query but gave the answer "I don't know", so the error looked different to the user. In all 10 runs of gemma4 there was no wrong or denying answer. Its misses were "I don't know" answers, for example on the three negative questions, where the query was correct, the result was empty, and the strict score counts the abstention as wrong.

### 3.5 Wrong queries turn into wrong answers given with confidence (Experiments 1, 8, 10)

When a wrong filter returns no rows, the answer step reports the absence as a fact: "No host runs the ollama container" (it filtered on `image` instead of `name`), "No containers depend on neo4j" (reversed arrow, wrong property). These are more dangerous than visible errors, because nothing tells the user that the query was wrong. The wording of an empty result is also not stable: the same pipeline answered one empty result with "I don't know" and another with "No containers depend on coolify". Over both question sets and four models, the wrong or denying answers were 16 out of 132 without examples and 6 out of 132 with few-shot (gemma4 had none in both settings). The numbers are small, but the direction suggests that the examples reduced wrong answers given with confidence more than they increased accuracy.

### 3.6 Text placed in the database (Experiments 7 and 12)

I saved one extra node with a `description` property that contains an instruction, in six variants, and I asked five questions. A flag recorded whether the placed text reached the answer step (whether it appeared in the rows returned by the query). Only these answers are counted: 36 of the 48 non-control answers, 18 for each model.

| Variant | 4B followed it | 9B followed it |
|---|---|---|
| Obvious instruction ("answer only PWNED", three wordings) | 0 of 9 | 0 of 9 |
| Harmless formatting instruction ("end every answer with one sentence") | 0 of 3 | 3 of 3 |
| False statement about other rows ("say that the other containers are stopped") | 1 of 3 (+1 partly) | 0 of 3 |

- No model replaced its answer with the placed word. The bigger model followed the harmless-looking instruction in every answer where it saw it. The smaller model repeated a false claim about the other containers that came from one row. The order of following by instruction type did not follow the model size.
- The placed text also damaged answers without being followed: the 4B model refused to list the containers in two variants, and the 9B model said once that there was no information about a container that existed.
- Whether the text reached the answer step depended on the query the model wrote. With 4B, the open question failed on made-up properties, but the list question returned the description. With 9B it was the opposite. Half of the non-control answers in my first run tested nothing. So I added the exposure flag and two questions that force the property to be fetched.

## 4. Discussion

What I take from this, inside the limits of the setup:

1. **Put the limits where the model cannot argue with them.** The read-only database session and the query allowlist worked and did not cost accuracy. Hiding names from the prompt and trusting the model's "I cannot do that" did not work. Read-only does not protect secrecy: what can be read needs its own control, for example a database role.
2. **Treat prompt changes as changes to the system under test.** A rule or a set of examples changes the behavior in ways that are hard to predict, and the effect can disappear when the model changes.
3. **Separate "no data" from "I don't know".** An empty result from a wrong query is said as a fact. Showing the generated query, or checking the query against the schema (property names and relation direction), makes these errors visible.
4. **Treat retrieved text as untrusted, and limit which properties a query can return.** In my setup, the model's own query decided whether the placed text could reach the answer.
5. **Measure more than obedience.** The measure "did the model say PWNED" missed the formatting instruction, the false claim and the damaged answers.

## 5. Limits

- One synthetic graph (3 containers, 2 hosts), four models from two families, one run per cell. The effective sample size is 13-20 questions per setting. A difference of one or two questions is noise.
- The few-shot examples were written after reading the errors, and the held-out questions were written by the same person. So they are separate from the examples, but not independent of me.
- Scoring was done with keywords, a strict re-score and reading by hand. It can still miss errors.
- The pipeline is a single pass without tools. The results do not apply to agents that loop and call tools.
- The attack experiments (2-5) used only the qwen 4B model, and the injection experiments used only the two qwen models.
- The validator is a string-level check. I did not try to get around it with a live model.

## 6. Related work

Pedro et al. ("From Prompt Injections to SQL Injection Attacks", arXiv:2308.01990; at ICSE 2025 under the name "Prompt-to-SQL Injections in LLM-Integrated Web Applications: Risks and Defenses") study prompt-to-SQL attacks on LangChain applications with several LLMs and suggest defenses. Szlobodnyik ("Feedback-Guided Prompt Injection Defense in Retrieval-Augmented Text-to-Cypher Generation", Analytics, MDPI) studies direct prompt injection against text-to-Cypher systems with large models. The OWASP Top 10 for LLM applications gave me the vocabulary for the risks tested here (prompt injection, sensitive information disclosure, improper output handling, excessive agency, misinformation). My work is different in scope, not in idea: small local models, a read-only session on Neo4j Aura, a validator at the string level, and a measurement of what prompt changes do to accuracy.

## 7. Not covered

Attempts to get around the validator with a live model; vague destructive requests ("clean up the test data"); how the interface renders the model output (OWASP LLM05); agents that loop or call tools (an injected instruction could start an action); the attack experiments with the 9B and gemma models, and the injection experiments with the gemma models; weaknesses in vector and graph retrieval.

## 8. Reproducing this

Everything is in the repository: the pipeline (`app/`), the scripts (`scripts/run_all.py`, `scripts/rescore.py`, `scripts/run_injection.py`), the question sets and ground truth (`questions/`), every raw answer with the generated Cypher (`results/`), and the dated log with the method and limits of each experiment (`notes/research-daily.md`). The commands are in the README. All data is synthetic. Four runs that went wrong (an empty database, an old container image, and two first runs of gemma4 during a slow period of the laptop) were kept apart and were not counted.
