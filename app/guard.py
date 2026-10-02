"""Query guard for the ragsec-lab pipeline.

The LLM writes Cypher; this module decides whether that Cypher may run.
It is a deliberately strict allowlist validator, not a full Cypher parser.
Known limits are documented in notes/research-daily.md as part of the experiments.
"""
import re

ALLOWED_LABELS = {"Host", "Container", "Port"}
ALLOWED_RELS = {"RUNS", "EXPOSES", "DEPENDS_ON"}
FORBIDDEN_KEYWORDS = {
    "CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP",
    "CALL", "LOAD", "FOREACH", "USE", "START", "COPY",
}

_STRING_OR_COMMENT = re.compile(
    r"""'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/""", re.S
)
_MAP = re.compile(r"\{[^{}]*\}")
_TYPE_AFTER_COLON = re.compile(r":\s*([A-Za-z_]\w*)")
_NODE_PATTERN = re.compile(
    r"(?<![\w])\(\s*([A-Za-z_]\w*)?\s*((?::\s*[A-Za-z_]\w*\s*)*)\)"
)


class QueryBlocked(Exception):
    def __init__(self, reason: str, query: str):
        super().__init__(reason)
        self.reason = reason
        self.query = query


def _clean(query: str) -> str:
    def repl(m):
        text = m.group(0)
        return "''" if text[0] in "'\"" else " "
    return _STRING_OR_COMMENT.sub(repl, query)


def check_query(query: str):
    """Return None if the query is allowed, otherwise a short reason string."""
    if not query or not query.strip():
        return "empty query"
    s = _clean(query)
    if "`" in s:
        return "backtick-quoted identifiers are not allowed"
    s = s.strip().rstrip(";").strip()
    if ";" in s:
        return "multiple statements are not allowed"
    if "|" in s:
        return "relationship type alternation is not allowed"

    words = {w.upper() for w in re.findall(r"[A-Za-z_]+", s)}
    bad = sorted(words & FORBIDDEN_KEYWORDS)
    if bad:
        return f"forbidden clause: {bad[0]}"

    prev = None
    while prev != s:
        prev = s
        s = _MAP.sub(" ", s)

    for t in _TYPE_AFTER_COLON.findall(s):
        if t not in ALLOWED_LABELS and t not in ALLOWED_RELS:
            return f"label or relationship type not allowed: {t}"

    labeled = set()
    for var, labels in ((m.group(1), m.group(2)) for m in _NODE_PATTERN.finditer(s)):
        if labels.strip():
            if var:
                labeled.add(var)
        else:
            if not var:
                return "anonymous node without a label"
            if var not in labeled:
                return f"node '{var}' has no label"
    return None


def validate(query: str) -> None:
    reason = check_query(query)
    if reason:
        raise QueryBlocked(reason, query)