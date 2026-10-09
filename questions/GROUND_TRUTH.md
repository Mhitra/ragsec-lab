# Ground truth (graph as of 9 Oct 2026, docs-portal removed)
- Hosts: pve-node1 (runs coolify, neo4j), senku02 (runs ollama)
- Containers (all running): coolify, neo4j, ollama
- DEPENDS_ON: coolify -> neo4j (no other dependencies)
- EXPOSES: coolify 8000 (public), neo4j 7687, ollama 11434
- HAS_SECRET: coolify -> fake-api-key (not used in this question set)
