"""Experiment 15: string-level bypass corpus for app/guard.py.

Each entry is (category, cypher). ATTACKS must be blocked, BENIGN must pass. The corpus is hand-written for the
lab graph (labels Host, Container, Port, Secret). It tests the validator only, as a string check: a query that
passes here is not proof that the database would run it or leak anything, and a blocked query is not proof that
no other bypass exists.
"""

ATTACKS = [
    # direct access to the secret
    ("secret-label", "MATCH (s:Secret) RETURN s.value"),
    ("secret-rel", "MATCH (c:Container)-[:HAS_SECRET]->(s:Secret) RETURN s.value"),
    ("secret-backtick", "MATCH (s:`Secret`) RETURN s"),
    ("secret-lowercase", "MATCH (s:secret) RETURN s"),
    ("secret-homoglyph", "MATCH (s:Sеcret) RETURN s"),
    ("secret-where-label", "MATCH (n) WHERE n:Secret RETURN n"),
    ("secret-anon-node", "MATCH (c:Container)-[:HAS_SECRET]->() RETURN c"),
    # subquery expressions hide a MATCH inside braces
    ("subquery-collect", "MATCH (c:Container) RETURN COLLECT { MATCH (s:Secret) RETURN s.value } AS v"),
    ("subquery-exists", "MATCH (c:Container) WHERE EXISTS { MATCH (s:Secret) } RETURN c.name"),
    ("subquery-exists-pattern", "MATCH (c:Container) WHERE EXISTS { (c)-[:HAS_SECRET]->() } RETURN c.name"),
    ("subquery-count", "MATCH (c:Container) RETURN c.name, COUNT { (c)-[:HAS_SECRET]->() } AS n"),
    ("subquery-lowercase", "MATCH (c:Container) RETURN collect { match (s:Secret) return s.value }"),
    ("subquery-spaced", "MATCH (c:Container) RETURN COLLECT\n{ MATCH (s:Secret) RETURN s.name }"),
    ("subquery-call", "MATCH (c:Container) CALL { MATCH (s:Secret) RETURN s } RETURN s"),
    # label expressions
    ("labelexpr-negation", "MATCH (n:!Host) RETURN n"),
    ("labelexpr-wildcard", "MATCH (n:%) RETURN n"),
    ("labelexpr-and", "MATCH (n:Container&Secret) RETURN n"),
    ("labelexpr-paren", "MATCH (n:(Container|Secret)) RETURN n"),
    ("labelexpr-rel-negation", "MATCH (c:Container)-[:!RUNS]->(x:Container) RETURN x"),
    ("labelexpr-rel-wildcard", "MATCH (c:Container)-[:%]->(x:Container) RETURN x"),
    ("labelexpr-pipe", "MATCH (n:Container|Secret) RETURN n"),
    # paths and variable-length patterns
    ("varlen-untyped", "MATCH p=(a:Container)-[*1..3]-(b:Container) RETURN nodes(p)"),
    ("varlen-unbounded", "MATCH p=(a:Container)-[*]-(b:Container) RETURN p"),
    ("varlen-typed", "MATCH (a:Container)-[:DEPENDS_ON*1..50]->(b:Container) RETURN count(b)"),
    ("path-anon-end", "MATCH p=(a:Container)-[r]->(b) RETURN p"),
    # writes and admin
    ("write-create", "CREATE (c:Container {name: 'x'})"),
    ("write-merge", "MERGE (c:Container {name: 'x'}) RETURN c"),
    ("write-set", "MATCH (c:Container) SET c.status = 'stopped' RETURN c"),
    ("write-set-map", "MATCH (c:Container) SET c += {status: 'stopped'} RETURN c"),
    ("write-remove", "MATCH (c:Container) REMOVE c.status RETURN c"),
    ("write-delete", "MATCH (c:Container) DETACH DELETE c"),
    ("write-foreach", "MATCH (c:Container) FOREACH (x IN [1] | SET c.a = x)"),
    ("write-lowercase", "match (c:Container) detach delete c"),
    ("write-after-comment", "MATCH (c:Container) RETURN c // ok\nDELETE c"),
    ("write-block-comment", "MATCH (c:Container) /* x */ SET c.a = 1"),
    ("admin-show", "SHOW DATABASES"),
    ("admin-show-user", "SHOW CURRENT USER"),
    ("admin-create-user", "CREATE USER x SET PASSWORD 'y'"),
    ("admin-call-labels", "MATCH (c:Container) CALL db.labels() YIELD label RETURN label"),
    ("admin-call-apoc", "MATCH (c:Container) CALL apoc.meta.data() YIELD label RETURN label"),
    ("admin-load-csv", "LOAD CSV FROM 'http://x/y.csv' AS row RETURN row"),
    ("admin-use", "USE system MATCH (c:Container) RETURN c"),
    ("admin-explain", "EXPLAIN MATCH (c:Container) RETURN c"),
    ("admin-profile", "PROFILE MATCH (c:Container) RETURN c"),
    # statement shape
    ("shape-two-statements", "MATCH (c:Container) RETURN c; MATCH (s:Secret) RETURN s"),
    ("shape-return-only", "RETURN 1"),
    ("shape-namespaced-fn", "MATCH (c:Container) RETURN apoc.version()"),
    ("shape-namespaced-fn-space", "MATCH (c:Container) RETURN apoc.text.join ( ['a'], ',' )"),
    ("shape-list-comprehension", "MATCH (c:Container) RETURN [p IN [1,2] | p]"),
    ("shape-pattern-comprehension", "MATCH (c:Container) RETURN [(c)-[:HAS_SECRET]->(s) | s.value]"),
    ("shape-unlabeled-node", "MATCH (n) RETURN n"),
    ("shape-unlabeled-after-labeled", "MATCH (c:Container)-[r]->(x) RETURN x"),
    ("shape-union-secret", "MATCH (c:Container) RETURN c.name AS n UNION MATCH (s:Secret) RETURN s.value AS n"),
    ("shape-leading-bom", "﻿MATCH (c:Container) RETURN c"),
    ("shape-empty", ""),
    ("shape-whitespace", "   \n  "),
    ("shape-too-long", "MATCH (c:Container) RETURN c.name " + "// padding\n" * 300),
]

BENIGN = [
    "MATCH (h:Host {name: 'pve-node1'})-[:RUNS]->(c:Container) RETURN c.name",
    "MATCH (h:Host)-[:RUNS]->(c:Container {name: 'ollama'}) RETURN h.name",
    "MATCH (c:Container)-[:EXPOSES]->(p:Port {number: 8000}) RETURN c.name",
    "MATCH (c:Container {name: 'coolify'})-[:DEPENDS_ON]->(d:Container) RETURN d.name",
    "MATCH (p:Port) WHERE p.public = false RETURN p.number",
    "MATCH (c:Container {name: 'coolify'})<-[:RUNS]-(h:Host)-[:RUNS]->(o:Container) WHERE o.name <> 'coolify' RETURN o.name",
    "MATCH (c:Container) RETURN count(c) AS n",
    "MATCH (h:Host) RETURN count(h)",
    "MATCH (c:Container {status: 'running'}) RETURN c.name ORDER BY c.name",
    "MATCH (c:Container) WHERE c.name = 'a;b' RETURN c.name",
    "MATCH (c:Container) WHERE c.name = 'COLLECT { MATCH (s:Secret) }' RETURN c.name",
    "MATCH (c:Container) WHERE c.name = 'x!y%z&w' RETURN c.name",
    "MATCH (c:Container) WHERE c.name = \"it's\" RETURN c",
    "OPTIONAL MATCH (c:Container {name: 'nothing'}) RETURN c.name",
    "MATCH (h:Host {os: 'Proxmox VE'})-[:RUNS]->(c:Container) RETURN c.name",
    "MATCH (c:Container {name: 'coolify'})-[:DEPENDS_ON]->(d:Container)<-[:RUNS]-(h:Host) RETURN h.name",
    "MATCH (c:Container)-[:EXPOSES]->(p:Port) WHERE p.public = true RETURN count(p)",
    "MATCH (c:Container) RETURN c.name, c.image LIMIT 10",
    "MATCH (c:Container)-[:EXPOSES]->(p:Port) RETURN c.name, collect(p.number) AS ports",
    "MATCH (c:Container) RETURN c.name AS name UNION MATCH (h:Host) RETURN h.name AS name",
    "MATCH (h:Host {name: 'pve-node1'})-[:RUNS]->(c:Container) // list them\nRETURN c.name",
]
