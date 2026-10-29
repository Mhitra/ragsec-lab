"""Experiment 15: run the bypass corpus against a guard version and print a table (no database, no model).

Usage (repo root):
  python scripts/validator_bypass.py                       current app/guard.py
  python scripts/validator_bypass.py --guard path/to/guard_v1.py   another copy, e.g. from git history:
      git show dfba224:app/guard.py > /tmp/guard_v1.py
Exit code 1 if an attack passes or a benign query is blocked.
"""
import argparse
import importlib.util
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests"))
from bypass_corpus import ATTACKS, BENIGN  # noqa: E402


def load(path):
    spec = importlib.util.spec_from_file_location("guard_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--guard", default=os.path.join("app", "guard.py"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    g = load(args.guard)
    version = getattr(g, "GUARD_VERSION", 1)
    passed = [(c, q) for c, q in ATTACKS if g.check_query(q) is None]
    blocked_benign = [(q, g.check_query(q)) for q in BENIGN if g.check_query(q) is not None]
    cats = {}
    for c, q in ATTACKS:
        grp = c.split("-")[0]
        cats.setdefault(grp, [0, 0])
        cats[grp][1] += 1
        if g.check_query(q) is None:
            cats[grp][0] += 1
    print(f"Guard version {version} ({args.guard})")
    print(f"Attacks that PASSED the guard: {len(passed)} of {len(ATTACKS)}")
    print(f"Benign queries blocked:        {len(blocked_benign)} of {len(BENIGN)}\n")
    print("| Group | passed | total |\n|---|---|---|")
    for grp, (p, t) in cats.items():
        print(f"| {grp} | {p} | {t} |")
    if not args.quiet:
        for c, q in passed:
            print(f"\nPASSED  [{c}] {q!r}")
        for q, why in blocked_benign:
            print(f"\nFALSE POSITIVE {q!r} -> {why}")
    sys.exit(1 if passed or blocked_benign else 0)


if __name__ == "__main__":
    main()
