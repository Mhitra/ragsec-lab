# Experiment 18: a database role instead of a string check

Findings 5 and 6 of the log say that the model, the prompt and the validator are the only things between a
question and the data. A database role moves the limit to a place the model cannot argue with:
the account the app connects with simply cannot read the `Secret` label or write anything.

**Status: run on 29 Oct 2026** against a local Neo4j 5.26.32 Enterprise container (`docker compose --profile enterprise up -d neo4j-enterprise`, evaluation licence; read the Neo4j licence terms yourself first). The nine original statements ran without change. The first run showed that the built-in PUBLIC role still grants `EXECUTE PROCEDURE *`, `EXECUTE USER DEFINED FUNCTION *` and `LOAD ON ALL DATA`, so a hardening block of `DENY` statements was added to `setup_rbac.cypher`. Results and limits are in `notes/research-daily.md` (Experiment 18) and `results/attacks.csv` (settings `rbac` and `rbac_hardened`). With the Docker route below, the app reaches the database at `bolt://neo4j-enterprise:7687` and the host-side scripts at `bolt://localhost:7688`.

## What you need
- A Neo4j that supports custom roles and fine-grained privileges (Enterprise Edition, or an Aura tier that
  offers them; Aura Free does not). A local Neo4j next to the app also works: `docker compose --profile local`
  starts the Community image, which has no custom roles, so use an Enterprise DBMS you are licensed to run
  (for example the one in Neo4j Desktop, if its licence allows development use) and point `NEO4J_URI` at it,
  for example `neo4j://host.docker.internal:7687` from the container.
- Admin credentials, only for creating the role, reseeding and probing the database state.

## Steps
1. Run `rbac/setup_rbac.cypher` as admin, statement by statement. Fix any statement your version rejects and
   write the fix down in the log.
2. In `.env`: set `NEO4J_USERNAME=ragapp` and its password for the app, and put the admin account in
   `PROBE_NEO4J_USERNAME` / `PROBE_NEO4J_PASSWORD` (used only by `scripts/run_attacks.py`). Seed the graph once as
   admin (the restricted user cannot write): `python scripts/run_attacks.py` reseeds through the admin account.
3. Start the app by hand: `docker compose up -d --build`, then check `curl localhost:8000/health`.
4. Run the attack battery against the restricted account, with the validator off, so the database is the only barrier:
   `python scripts/run_attacks.py --assume-running --setting-label rbac none`
5. Run the same battery with the validator on (`--setting-label rbac_validate`, `.env` edited by hand with
   `PROTECT_VALIDATE=1`) to see both layers together.
6. Accuracy with the restricted account: the graph must already be seeded (the attack script leaves the small graph
   seeded when it ends). `scripts/run_all.py` only rewrites the protection switches and the model in `.env`, so the
   restricted credentials stay: `python scripts/run_all.py --no-seed none validate`. Without `--no-seed` it would try to
   reseed through the app, which the restricted user cannot do.

## Route with Neo4j Desktop (no cost; read its licence text first)
1. Stop the Docker Neo4j so that port 7687 is free: `docker compose --profile local stop neo4j`.
2. In Neo4j Desktop create a DBMS (version 5.x) with an admin password and start it. Under its plugins install APOC
   (LangChain's `Neo4jGraph` needs it). The default database is called `neo4j`, which the setup script assumes.
3. Seed once as admin: open Neo4j Browser on that DBMS and run the statements of `app/seed.cypher` (the file is split on `;`).
4. Open the `system` database in Browser and run `rbac/setup_rbac.cypher` statement by statement
   (`:param password => '...'` first). Then run `SHOW USER ragapp PRIVILEGES AS COMMANDS;` and read the result.
5. Put the lines of `rbac/env.rbac.example` into `.env`. The container reaches the DBMS through `host.docker.internal`
   the same way it already reaches Ollama; if the connection is refused, the DBMS may listen on loopback only and Docker
   cannot see it: check the listen address setting of the DBMS before changing anything, because opening it to all
   interfaces exposes the database to your network.
6. `docker compose up -d --build`, `curl localhost:8000/health`, then the steps 4-6 above.

When finished, restore your `.env` (the Docker-Neo4j settings are in the backup you made) and stop the DBMS.

## What to look at, not what to expect
- Whether leaks and writes fail at the database (error or empty result) instead of at the string check.
- Whether a hidden label returns an empty result and the answer step states "there are no secrets" as a fact
  (finding 4: empty results become facts). That would be a new kind of silent error.
- Whether schema introspection still shows the hidden label name to the model.
- Whether accuracy on the benign question sets changes.
