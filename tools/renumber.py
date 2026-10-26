"""Renumber the claims, warrants, definitions, limitations and open questions of a claimset in reading order.

Claims are ordered by role (principal, supporting, secondary, then assumptions), each group by the first place
the paper makes the claim (its earliest source span). Warrants follow the order of the claims that use them;
definitions, limitations and open questions keep their order and lose their gaps. Every reference in the file is
rewritten: ID fields, lists of IDs and the [[Dn:term]] marks in text. The old-to-new map is printed.

    python3 tools/renumber.py CLAIMSET.json [--out OUT.json]
"""

import argparse
import json
import re
import sys

SPAN = re.compile(r"p(\d+)\.(\d+)")
MARK = re.compile(r"\[\[(D\d+):")
ROLE_ORDER = {"principal": 0, "supporting": 1, "secondary": 2}


def first_span(obj):
    """(page, paragraph) of the earliest source span, or a key that sorts last."""
    found = [(int(m.group(1)), int(m.group(2))) for sp in obj.get("source_spans") or [] for m in SPAN.finditer(sp)]
    return min(found) if found else (10 ** 6, 0)


def is_assumption(claim):
    return any(isinstance(s, dict) and s.get("kind") == "assumption" for s in claim.get("support") or [])


def claim_key(claim):
    group = 3 if is_assumption(claim) else ROLE_ORDER.get(claim.get("role"), 4)
    return (group, first_span(claim))


def plan(doc):
    """The old-to-new ID map."""
    mapping = {}
    claims = sorted(doc.get("claims") or [], key=claim_key)     # stable: ties keep file order
    for n, c in enumerate(claims, 1):
        mapping[c["id"]] = f"C{n}"
    warrants = {w["id"]: w for w in doc.get("warrants") or []}
    used = []
    for c in claims:
        for s in c.get("support") or []:
            w = s.get("warrant") if isinstance(s, dict) else None
            if w in warrants and w not in used:
                used.append(w)
        if c.get("warrant") in warrants and c["warrant"] not in used:
            used.append(c["warrant"])
    used += [w for w in warrants if w not in used]
    for n, w in enumerate(used, 1):
        mapping[w] = f"W{n}"
    for key, prefix in (("definitions", "D"), ("limitations", "L"), ("open_questions", "O")):
        for n, x in enumerate(doc.get(key) or [], 1):
            mapping[x["id"]] = f"{prefix}{n}"
    return mapping


def rewrite(x, mapping):
    if isinstance(x, dict):
        return {k: rewrite(v, mapping) for k, v in x.items()}
    if isinstance(x, list):
        return [rewrite(v, mapping) for v in x]
    if isinstance(x, str):
        if x in mapping:
            return mapping[x]
        return MARK.sub(lambda m: f"[[{mapping.get(m.group(1), m.group(1))}:", x)
    return x


def renumber(doc):
    """(renumbered document, old-to-new map). Claims and warrants are written in their new order."""
    mapping = plan(doc)
    out = rewrite(doc, mapping)
    order = {new: i for i, new in enumerate(mapping.values())}
    for key in ("claims", "warrants"):
        if key in out:
            out[key] = sorted(out[key], key=lambda o: order[o["id"]])
    paper = out.get("paper") or {}
    if isinstance(paper.get("contributions"), list):
        paper["contributions"] = sorted(paper["contributions"], key=lambda x: order.get(x, len(order)))
    return out, mapping


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("claimset")
    ap.add_argument("--out", help="where to write (default: in place)")
    args = ap.parse_args(argv)
    with open(args.claimset, encoding="utf-8") as f:
        doc = json.load(f)
    out, mapping = renumber(doc)
    with open(args.out or args.claimset, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    for old, new in mapping.items():
        if old != new:
            print(f"{old} -> {new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
