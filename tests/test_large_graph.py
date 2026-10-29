"""Check that questions_large.csv agrees with app/seed_large.cypher (parsed independently of gen_large.py)."""
import csv
import os
import re
import sys

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
cy = open(os.path.join(root, "app", "seed_large.cypher"), encoding="utf-8").read()
node = {}  # var -> (label, props)
for m in re.finditer(r"CREATE \((\w+):(\w+) \{([^}]*)\}\)", cy):
    props = dict(re.findall(r"(\w+):\s*('[^']*'|[\w.]+)", m.group(3)))
    node[m.group(1)] = (m.group(2), {k: v.strip("'") for k, v in props.items()})
rel = [(a, t, b) for a, t, b in re.findall(r"CREATE \((\w+)\)-\[:(\w+)\]->\((\w+)\)", cy)]
name = lambda v: node[v][1]["name"]
ctn = {v for v, (l, _) in node.items() if l == "Container"}
hosts = {v for v, (l, _) in node.items() if l == "Host"}
runs = {c: name(h) for h, t, c in rel if t == "RUNS"}
deps = {}
for a, t, b in rel:
    if t == "DEPENDS_ON":
        deps.setdefault(name(a), []).append(name(b))
ports = {}
for a, t, p in rel:
    if t == "EXPOSES":
        ports.setdefault(name(a), []).append(node[p][1]["number"])
status = {name(c): node[c][1]["status"] for c in ctn}

qs = list(csv.DictReader(open(os.path.join(root, "questions", "questions_large.csv"), encoding="utf-8")))
fails = 0
checked = 0


def req(q):
    return {w for w in q["required_all"].split(";") if w}


for q in qs:
    t = q["question"]
    exp = None
    m = re.match(r"(?:Which containers run on host|List the containers on host) (\S+?)[.?]$", t)
    if m:
        exp = {name(c) for c in ctn if runs[c] == m.group(1)}
    m = m or None
    m2 = re.match(r"What does the (\S+) container depend on\?", t)
    if m2 and q["type"] == "lookup":
        exp = set(deps.get(m2.group(1), []))
    m3 = re.match(r"Which containers depend on (\S+)\?", t)
    if m3:
        exp = {a for a, d in deps.items() if m3.group(1) in d}
    m4 = re.match(r"Which containers expose port (\d+)\?", t)
    if m4:
        exp = {name(c) for c in ctn if m4.group(1) in ports.get(name(c), [])}
    m5 = re.match(r"Which (?:ports does|port does) the (\S+) container expose\?", t)
    if m5:
        exp = set(ports[m5.group(1)])
    m6 = re.match(r"Which host runs the (\S+) container\?|On which host does the (\S+) container run\?", t)
    if m6:
        c = m6.group(1) or m6.group(2)
        exp = {runs[v] for v in ctn if name(v) == c}
    if re.match(r"List all stopped containers", t):
        exp = {n for n, s in status.items() if s != "running"}
    if exp is not None:
        checked += 1
        if exp != req(q):
            fails += 1
            print("MISMATCH", t, "seed:", sorted(exp), "csv:", sorted(req(q)))
    if t == "How many containers are running?":
        checked += 1
        n = sum(1 for s in status.values() if s == "running")
        if str(n) not in q["required_any"].split(";"):
            fails += 1; print("MISMATCH", t)
    if t == "How many hosts are there?":
        checked += 1
        if str(len(hosts)) not in q["required_any"].split(";"):
            fails += 1; print("MISMATCH", t)
    # no forbidden word may also be required
    both = req(q) & {w for w in q["forbidden"].split(";") if w}
    if both:
        fails += 1; print("REQUIRED AND FORBIDDEN", t, both)
print(f"questions: {len(qs)}, checked against the seed file: {checked}, failures: {fails}")
sys.exit(1 if fails else 0)
