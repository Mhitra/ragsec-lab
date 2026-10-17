# Ground truth (graph as of 9 Oct 2026, docs-portal removed)
- Hosts: pve-node1 (runs coolify, neo4j), senku02 (runs ollama)
- Containers (all running): coolify, neo4j, ollama
- DEPENDS_ON: coolify -> neo4j (no other dependencies)
- EXPOSES: coolify 8000 (public), neo4j 7687, ollama 11434
- HAS_SECRET: coolify -> fake-api-key (not used in this question set)

# Held-out set (questions/questions_heldout.csv, 17 Oct 2026)
Same graph as above. Extra properties used by this set (from app/seed.cypher):
- Host.os: pve-node1 = Proxmox VE, senku02 = Debian LXC
- Container.image: coolify = coollabsio/coolify, neo4j = neo4j:5, ollama = ollama/ollama; all status running
- Port.public: 8000 true, 7687 false, 11434 false
Expected answers: 1 Debian LXC | 2 ollama/ollama | 3 coolify and neo4j | 4 running | 5 one (8000) | 6 two | 7 pve-node1 and senku02 | 8 7687 | 9 pve-node1 | 10 coolify (it depends on neo4j, which runs on pve-node1) | 11 none (coolify depends on neo4j, nothing depends on coolify) | 12 none | 13 free text (image ollama/ollama, port 11434, host senku02)
Written for Experiment 10, after the few-shot examples of Experiment 9 were fixed. The few-shot examples use made-up names and the patterns host-to-containers, container-to-host, port-to-container, DEPENDS_ON, a boolean property, same-host. Held-out questions 1-4 (Host.os, Container.image, status) and 5 (count of public ports) use properties or shapes that no example shows; the others share a pattern with an example but use different entities.
