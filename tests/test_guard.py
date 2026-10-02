import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
from guard import check_query

ALLOWED = [
    "MATCH (c:Container)-[:EXPOSES]->(p:Port) WHERE p.number = 8000 RETURN c.name AS container_name",
    "MATCH (h:Host {name: 'pve-node1'})-[:RUNS]->(c:Container)\nRETURN c",
    "MATCH (c:Container {status: 'running'})\nRETURN c.name",
    "MATCH (c:Container {name: 'coolify'})\nMATCH (c)-[:DEPENDS_ON]->(dep:Container)\nRETURN dep.name AS dependency_name",
    "MATCH (p:Port {public: true})\nRETURN p",
    "MATCH (h:Host)-[:RUNS]->(c:Container) WHERE c.name = 'ollama' RETURN h.name;",
    "MATCH (c:Container) WHERE c.name = 'set create delete' RETURN count(c)",
]
BLOCKED = [
    "CREATE (c:Container {name: 'test-injection', status: 'running'});",
    "MATCH (c:Container {name: 'test-injection'})\nDETACH DELETE c",
    "MATCH (n) DETACH DELETE n",
    "MATCH (c:Container {name: 'coolify'})-[:HAS_SECRET]->(s:Secret) RETURN s.name, s.value",
    "MATCH (n) RETURN n",
    "MATCH (n) WHERE n:Secret RETURN n",
    "MATCH (c:Container)-[:RUNS|HAS_SECRET]->(x:Container) RETURN x",
    "MATCH (c:Container) SET c.status = 'stopped' RETURN c",
    "MATCH (c:Container) RETURN c; MATCH (s:Secret) RETURN s",
    "MATCH (c:Container) RETURN c // harmless\nCALL db.labels()",
    "MATCH (c:Container)-[:EXPOSES]->(p:Port) RETURN c, p UNION MATCH (s:`Secret`) RETURN s, s",
    "MATCH (h:Host)-[:RUNS]->(c) RETURN c",
    "MERGE (c:Container {name: 'x'})",
    "LOAD CSV FROM 'http://x/y.csv' AS row RETURN row",
    "SHOW DATABASES",
    "SHOW CURRENT USER",
    "TERMINATE TRANSACTIONS 'x'",
    "RETURN 1",
    "MATCH (c:Container) RETURN apoc.version()",
    "MATCH (c:Container) RETURN c.name, [p IN c.ports | p]",
    "",
]
fails = 0
for q in ALLOWED:
    r = check_query(q)
    if r is not None:
        fails += 1; print("FALSE POSITIVE:", repr(q), "->", r)
for q in BLOCKED:
    r = check_query(q)
    if r is None:
        fails += 1; print("MISSED:", repr(q))
print("allowed:", len(ALLOWED), "blocked:", len(BLOCKED), "failures:", fails)
sys.exit(1 if fails else 0)