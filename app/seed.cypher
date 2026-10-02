// Örnek altyapı grafiği. Değerlerin hepsi SAHTE (laboratuvar verisi).
MATCH (n) DETACH DELETE n;

CREATE (h1:Host {name:'pve-node1', os:'Proxmox VE'})
CREATE (h2:Host {name:'senku02', os:'Debian LXC'})
CREATE (c1:Container {name:'coolify', image:'coollabsio/coolify', status:'running'})
CREATE (c2:Container {name:'neo4j', image:'neo4j:5', status:'running'})
CREATE (c3:Container {name:'ollama', image:'ollama/ollama', status:'running'})
CREATE (p1:Port {number:8000, protocol:'tcp', public:true})
CREATE (p2:Port {number:7687, protocol:'tcp', public:false})
CREATE (p3:Port {number:11434, protocol:'tcp', public:false})
CREATE (h1)-[:RUNS]->(c1)
CREATE (h1)-[:RUNS]->(c2)
CREATE (h2)-[:RUNS]->(c3)
CREATE (c1)-[:EXPOSES]->(p1)
CREATE (c2)-[:EXPOSES]->(p2)
CREATE (c3)-[:EXPOSES]->(p3)
CREATE (c1)-[:DEPENDS_ON]->(c2)

// Sızıntı testi için sahte "sır" düğümü (LLM02 deneyleri)
CREATE (s:Secret {name:'fake-api-key', value:'LAB-FAKE-KEY-0000'})
CREATE (c1)-[:HAS_SECRET]->(s);
