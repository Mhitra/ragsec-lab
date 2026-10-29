"""Query guard for the ragsec-lab pipeline.

The LLM writes Cypher; this module decides whether that Cypher may run.
It is a deliberately strict allowlist validator, not a full Cypher parser.
Known limits are documented in notes/research-daily.md as part of the experiments.

Version history
  1  Experiments 3c to 14. Allowlist of labels and relationship types, write clauses blocked, node patterns must
     carry a label. Experiment 15 showed that it let subquery expressions (COLLECT { }, EXISTS { }, COUNT { }),
     label expressions (:!X, :%, :A&B), and untyped variable-length paths through at the string level.
  2  Experiment 15 fixes: subquery braces, label expression operators, variable-length patterns and non-identifier
     labels are blocked; a query length limit is added.
Resource use (cartesian products, expensive but allowed patterns) is NOT limited here; use database timeouts.
"""
import re

GUARD_VERSION = 2
MAX_QUERY_LENGTH = 2000

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
_START = re.compile(r"(?is)^(OPTIONAL\s+)?MATCH\b")
_NAMESPACED_FUNCTION = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+\s*\(")
_SUBQUERY_EXPR = re.compile(r"(?i)\b(?:EXISTS|COUNT|COLLECT)\s*\{")
_BRACE_GROUP = re.compile(r"\{[^{}]*\}")
_BRACE_CLAUSE = re.compile(r"(?i)\b(?:MATCH|RETURN|WITH|UNWIND|WHERE|UNION)\b")
_LABEL_EXPR_CHARS = re.compile(r"[&%!]")
_VAR_LENGTH = re.compile(r"\[[^\]]*\*")
_COLON_NOT_IDENT = re.compile(r":\s*(?![A-Za-z_])")
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
    if len(query) > MAX_QUERY_LENGTH:
        return "query is too long"
    s = _clean(query)
    if "`" in s:
        return "backtick-quoted identifiers are not allowed"
    s = s.strip().rstrip(";").strip()
    if ";" in s:
        return "multiple statements are not allowed"
    if not _START.match(s):
        return "query must start with MATCH"
    if _NAMESPACED_FUNCTION.search(s):
        return "namespaced function calls are not allowed"
    if "|" in s:
        return "the pipe character is not allowed (relationship alternation or list comprehension)"
    if _LABEL_EXPR_CHARS.search(s):
        return "label expression operators are not allowed"
    if _VAR_LENGTH.search(s):
        return "variable-length relationship patterns are not allowed"
    if _SUBQUERY_EXPR.search(s):
        return "subquery expressions are not allowed"
    for group in _BRACE_GROUP.findall(s):
        if _BRACE_CLAUSE.search(group):
            return "clauses inside braces are not allowed"

    words = {w.upper() for w in re.findall(r"[A-Za-z_]+", s)}
    bad = sorted(words & FORBIDDEN_KEYWORDS)
    if bad:
        return f"forbidden clause: {bad[0]}"

    prev = None
    while prev != s:
        prev = s
        s = _MAP.sub(" ", s)

    if _COLON_NOT_IDENT.search(s):
        return "a label or relationship type must be a plain identifier"
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