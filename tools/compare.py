"""Compare a candidate claimset (e.g. a converter's output) with a gold claimset of the same paper.

No model calls. Objects are matched one to one (Hungarian assignment) on text similarity (TF-IDF cosine over
words) combined with source-span overlap, where both sides give spans and the paper's text is supplied to
expand ranges. The report gives, per kind of object, how much of the gold the candidate recovers (recall), how
much of the candidate is in the gold (precision), agreement on coding for matched pairs, and the links between
claims mapped through the matching.

    python3 tools/compare.py GOLD.json CANDIDATE.json [--text papers/text/X.txt] [--json OUT.json]
"""

import argparse
import json
import math
import re
import sys
from collections import Counter

TERM = re.compile(r"\[\[D\d+:([^\]]+)\]\]")
WORD = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
MARKER = re.compile(r"^\[(p\d+\.\d+)\]", re.M)
STOP = set("the a an of and or in on to for by with is are be as at that this from its it than which".split())


# ---------- text and spans ----------

def tokens(text):
    text = TERM.sub(lambda m: m.group(1), text or "").lower()
    return [w for w in WORD.findall(text) if w not in STOP]


def tfidf(docs):
    df = Counter(t for d in docs for t in set(d))
    n = len(docs)
    vecs = []
    for d in docs:
        tf = Counter(d)
        v = {t: (c / len(d)) * math.log((1 + n) / (1 + df[t]) + 1) for t, c in tf.items()} if d else {}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm for t, x in v.items()})
    return vecs


def cosine(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def marker_order(text):
    return {m: i for i, m in enumerate(MARKER.findall(text))} if text else {}


def expand(spans, order):
    out = set()
    for s in spans or []:
        if not isinstance(s, str):
            continue
        a, _, b = s.partition("-")
        if b and a in order and b in order:
            lo, hi = sorted((order[a], order[b]))
            out.update(range(lo, hi + 1))
        elif a in order:
            out.add(order[a])
        else:
            out.add(s)
    return out


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


# ---------- assignment ----------

def hungarian(cost):
    """Minimum-cost assignment for a rectangular matrix (rows <= cols after padding). Returns {row: col}."""
    n_rows, n_cols = len(cost), len(cost[0]) if cost else 0
    n = max(n_rows, n_cols)
    if n == 0:
        return {}
    big = 1.0
    c = [[cost[i][j] if i < n_rows and j < n_cols else big for j in range(n)] for i in range(n)]
    u, v, p, way = [0.0] * (n + 1), [0.0] * (n + 1), [0] * (n + 1), [0] * (n + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minv, used = [math.inf] * (n + 1), [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], math.inf, 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = c[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    return {p[j] - 1: j - 1 for j in range(1, n + 1) if p[j] and p[j] - 1 < n_rows and j - 1 < n_cols}


def similarity(gold, cand, text_of, spans_of, order, contain=False):
    """Similarity matrix gold x candidate: TF-IDF cosine of the texts, averaged with span overlap when both
    sides have spans (Jaccard, or with contain=True the share of the gold object's paragraphs the candidate covers)."""
    vecs = tfidf([tokens(text_of(o)) for o in gold + cand])
    gv, cv = vecs[:len(gold)], vecs[len(gold):]
    gs = [expand(spans_of(o), order) for o in gold]
    cs = [expand(spans_of(o), order) for o in cand]
    sim = []
    for i in range(len(gold)):
        row = []
        for j in range(len(cand)):
            s = cosine(gv[i], cv[j])
            if order and gs[i] and cs[j]:
                ov = len(gs[i] & cs[j]) / len(gs[i]) if contain else jaccard(gs[i], cs[j])
                s = 0.5 * s + 0.5 * ov
            row.append(s)
        sim.append(row)
    return sim


def coverage(gold, cand, text_of, spans_of, order, threshold):
    """Many-to-one: each gold object's best candidate, if similar enough. Returns {gold id: (cand id, score)}."""
    if not gold or not cand:
        return {}
    sim = similarity(gold, cand, text_of, spans_of, order, contain=True)
    out = {}
    for i, g in enumerate(gold):
        j = max(range(len(cand)), key=lambda k: sim[i][k])
        if sim[i][j] >= threshold:
            out[g["id"]] = (cand[j]["id"], sim[i][j])
    return out


def match(gold, cand, text_of, spans_of, order, threshold):
    """Match two lists of objects; returns [(gold_obj, cand_obj, score)] for pairs at or above threshold."""
    if not gold or not cand:
        return []
    sim = similarity(gold, cand, text_of, spans_of, order)
    pairs = hungarian([[1.0 - x for x in row] for row in sim])
    return [(gold[i], cand[j], sim[i][j]) for i, j in pairs.items() if sim[i][j] >= threshold]


# ---------- per kind ----------

def is_assumption(c):
    return any(s.get("kind") == "assumption" for s in c.get("support", []))


def category(c):
    return "assumption" if is_assumption(c) else c.get("role", "?")


def support_kinds(c):
    return {s.get("kind") for s in c.get("support", [])}


def pr(n_match, n_gold, n_cand):
    return {"gold": n_gold, "candidate": n_cand, "matched": n_match,
            "recall": round(n_match / n_gold, 3) if n_gold else None,
            "precision": round(n_match / n_cand, 3) if n_cand else None}


def edges(claims, also_limitations=None):
    out = set()
    for c in claims:
        for k in ("depends_on", "assumptions"):
            for t in c.get(k, []) or []:
                out.add((c["id"], t))
    return out


def compare(gold, cand, text="", threshold=0.3):
    order = marker_order(text)
    rep = {}

    # claims
    gc, cc = gold.get("claims", []), cand.get("claims", [])
    pairs = match(gc, cc, lambda c: c.get("statement", ""), lambda c: c.get("source_spans"), order, threshold)
    g2c = {g["id"]: c["id"] for g, c, _ in pairs}
    rep["claims"] = {"all": pr(len(pairs), len(gc), len(cc))}
    for cat in ("principal", "supporting", "secondary", "assumption"):
        gn = sum(1 for c in gc if category(c) == cat)
        cn = sum(1 for c in cc if category(c) == cat)
        found = sum(1 for g, _, _ in pairs if category(g) == cat)
        rep["claims"][cat] = {"gold": gn, "candidate": cn, "gold found": found,
                              "recall": round(found / gn, 3) if gn else None}
    agree = {f: sum(1 for g, c, _ in pairs if g.get(f) == c.get(f)) for f in ("type", "role", "novelty")}
    agree["category"] = sum(1 for g, c, _ in pairs if category(g) == category(c))
    agree["support kinds"] = sum(1 for g, c, _ in pairs if support_kinds(g) == support_kinds(c))
    rep["claims"]["agreement on matched"] = {k: round(v / len(pairs), 3) if pairs else None for k, v in agree.items()}
    cov = coverage(gc, cc, lambda c: c.get("statement", ""), lambda c: c.get("source_spans"), order, threshold)
    by_cand = Counter(cid for cid, _ in cov.values())
    rep["claims"]["coverage"] = {
        "note": "many-to-one: a candidate claim may cover several gold claims (a bundle)",
        "gold covered": len(cov), "recall": round(len(cov) / len(gc), 3) if gc else None,
        "bundles": {cid: sorted((g for g, (c, _) in cov.items() if c == cid), key=lambda x: int(x[1:]))
                    for cid, n in by_cand.items() if n > 1},
        "not covered": [c["id"] for c in gc if c["id"] not in cov]}
    rep["claims"]["missed"] = [{"id": c["id"], "category": category(c), "statement": c.get("statement")}
                               for c in gc if c["id"] not in g2c]
    matched_c = set(g2c.values())
    rep["claims"]["extra"] = [{"id": c["id"], "category": category(c), "statement": c.get("statement")}
                              for c in cc if c["id"] not in matched_c]
    rep["claims"]["coding differences"] = [
        {"gold": g["id"], "candidate": c["id"], "score": round(s, 3),
         **{f: [g.get(f), c.get(f)] for f in ("type", "role", "novelty") if g.get(f) != c.get(f)},
         **({"category": [category(g), category(c)]} if category(g) != category(c) else {}),
         **({"support": [sorted(support_kinds(g)), sorted(support_kinds(c))]}
            if support_kinds(g) != support_kinds(c) else {})}
        for g, c, s in pairs
        if any(g.get(f) != c.get(f) for f in ("type", "role", "novelty"))
        or category(g) != category(c) or support_kinds(g) != support_kinds(c)]

    # links between claims, mapped through the matching
    ge = {(g2c[a], g2c[b]) for a, b in edges(gc) if a in g2c and b in g2c}
    ce = {(a, b) for a, b in edges(cc) if a in matched_c and b in matched_c}
    rep["links"] = {**pr(len(ge & ce), len(ge), len(ce)),
                    "note": "edges between matched claims only (depends_on and assumptions)",
                    "gold edges total": len(edges(gc)), "candidate edges total": len(edges(cc)),
                    "missing": sorted(ge - ce), "extra": sorted(ce - ge)}

    # definitions
    gd, cd = gold.get("definitions", []), cand.get("definitions", [])
    dpairs = match(gd, cd, lambda d: f"{d.get('term', '')} {d.get('term', '')} {d.get('definition', '')}",
                   lambda d: None, {}, threshold)
    rep["definitions"] = {**pr(len(dpairs), len(gd), len(cd)),
                          "missed": [d["term"] for d in gd if d["id"] not in {g["id"] for g, _, _ in dpairs}],
                          "extra": [d["term"] for d in cd if d["id"] not in {c["id"] for _, c, _ in dpairs}]}
    gd2c = {g["id"]: c["id"] for g, c, _ in dpairs}

    # evidence, tables and setup
    ge_, ce_ = gold.get("evidence", []), cand.get("evidence", [])
    epairs = match(ge_, ce_, lambda e: e.get("description", ""), lambda e: e.get("source_spans"), order, threshold)
    tables = {"gold cells": 0, "found": 0}
    setup = {"gold parts": 0, "found": 0}
    for g, c, _ in epairs:
        cvals = Counter(v for t in c.get("tables", []) for r in t.get("rows", []) for v in r.get("values", [])
                        if v is not None)
        for t in g.get("tables", []):
            for r in t.get("rows", []):
                for v in r.get("values", []):
                    if v is None:
                        continue
                    tables["gold cells"] += 1
                    if cvals[v] > 0:
                        cvals[v] -= 1
                        tables["found"] += 1
        cset = {(role, d) for role, ds in (c.get("setup") or {}).items() for d in ds}
        for role, ds in (g.get("setup") or {}).items():
            for d in ds:
                setup["gold parts"] += 1
                if (role, gd2c.get(d)) in cset:
                    setup["found"] += 1
    rep["evidence"] = {**pr(len(epairs), len(ge_), len(ce_)),
                       "profiles agree": sum(1 for g, c, _ in epairs if g.get("profile") == c.get("profile")),
                       "table cells recovered": tables, "setup parts recovered": setup}

    # limitations
    gl, cl = gold.get("limitations", []), cand.get("limitations", [])
    lpairs = match(gl, cl, lambda l: l.get("statement", ""), lambda l: l.get("source_spans"), order, threshold)
    gaff = {(l["id"], a) for l in gl for a in l.get("affects", [])}
    gl2c = {g["id"]: c["id"] for g, c, _ in lpairs}
    gaff_m = {(gl2c[l], g2c[a]) for l, a in gaff if l in gl2c and a in g2c}
    caff = {(l["id"], a) for l in cl for a in l.get("affects", []) if l["id"] in gl2c.values() and a in matched_c}
    rep["limitations"] = {**pr(len(lpairs), len(gl), len(cl)), "affects links": pr(len(gaff_m & caff), len(gaff_m), len(caff)),
                          "missed": [l["statement"] for l in gl if l["id"] not in gl2c]}

    # references and relations
    def ref_text(r):
        return f"{r.get('target', '')}"
    gr, cr = gold.get("references", []), cand.get("references", [])
    rpairs = match(gr, cr, ref_text, lambda r: None, {}, 0.5)
    gr2c = {g["id"]: c["id"] for g, c, _ in rpairs}
    rep["references"] = {**pr(len(rpairs), len(gr), len(cr)),
                         "missed": [r["target"] for r in gr if r["id"] not in gr2c],
                         "extra": [r["target"] for r in cr if r["id"] not in gr2c.values()]}
    grel = {(g2c[c["id"]], r.get("type"), gr2c.get(r.get("reference"))) for c in gc if c["id"] in g2c
            for r in c.get("relations", [])}
    crel = {(c["id"], r.get("type"), r.get("reference")) for c in cc if c["id"] in matched_c
            for r in c.get("relations", [])}
    rep["relations"] = pr(len(grel & crel), len(grel), len(crel))
    rep["settings"] = {"threshold": threshold, "spans used": bool(order)}
    return rep


# ---------- report ----------

def pct(x):
    return "  -  " if x is None else f"{100 * x:5.1f}%"


def print_report(rep, out=sys.stdout):
    w = out.write
    c = rep["claims"]
    w(f"CLAIMS  matched {c['all']['matched']} of {c['all']['gold']} gold, {c['all']['candidate']} candidate"
      f"  recall {pct(c['all']['recall'])}  precision {pct(c['all']['precision'])}\n")
    for cat in ("principal", "supporting", "secondary", "assumption"):
        x = c[cat]
        w(f"  {cat:<11} gold {x['gold']:>3}  candidate {x['candidate']:>3}  gold found {x['gold found']:>3}"
          f"  recall {pct(x['recall'])}\n")
    cv = c["coverage"]
    w(f"  coverage (many-to-one) {cv['gold covered']} of {c['all']['gold']} gold  recall {pct(cv['recall'])}"
      f"; bundles: " + (", ".join(f"{k} covers {'+'.join(v)}" for k, v in cv["bundles"].items()) or "none") + "\n")
    w("  agreement on matched pairs: " + ", ".join(f"{k} {pct(v)}" for k, v in c["agreement on matched"].items()) + "\n")
    for name in ("links", "definitions", "evidence", "limitations", "references", "relations"):
        x = rep[name]
        w(f"{name.upper():<12} matched {x['matched']} of {x['gold']} gold, {x['candidate']} candidate"
          f"  recall {pct(x['recall'])}  precision {pct(x['precision'])}\n")
    e = rep["evidence"]
    t, s = e["table cells recovered"], e["setup parts recovered"]
    w(f"  table cells recovered {t['found']} of {t['gold cells']}; setup parts recovered {s['found']} of {s['gold parts']}\n")
    a = rep["limitations"]["affects links"]
    w(f"  limitation 'affects' links: recall {pct(a['recall'])}  precision {pct(a['precision'])}\n")
    if c["missed"]:
        w("\nGOLD CLAIMS WITHOUT A ONE-TO-ONE MATCH (* = not covered by any candidate claim either)\n")
        for m in c["missed"]:
            m = dict(m, id=m["id"] + ("*" if m["id"] in cv["not covered"] else ""))
            w(f"  {m['id']} [{m['category']}] {m['statement']}\n")
    if c["extra"]:
        w("\nCANDIDATE CLAIMS NOT IN THE GOLD\n")
        for m in c["extra"]:
            w(f"  {m['id']} [{m['category']}] {m['statement']}\n")
    if c["coding differences"]:
        w("\nCODING DIFFERENCES (gold, candidate)\n")
        for d in c["coding differences"]:
            rest = "; ".join(f"{k} {v[0]} vs {v[1]}" for k, v in d.items() if k not in ("gold", "candidate", "score"))
            w(f"  {d['gold']} ~ {d['candidate']} ({d['score']}): {rest}\n")
    for name in ("definitions", "limitations", "references"):
        if rep[name].get("missed"):
            w(f"\nMISSED GOLD {name.upper()}\n")
            for m in rep[name]["missed"]:
                w(f"  {m}\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("gold")
    ap.add_argument("candidate")
    ap.add_argument("--text", help="the paper's extracted text with [pN.M] markers, to compare source spans")
    ap.add_argument("--threshold", type=float, default=0.3, help="minimum similarity for a match (default 0.3)")
    ap.add_argument("--json", help="also write the full report as JSON to this file")
    a = ap.parse_args(argv)
    with open(a.gold, encoding="utf-8") as f:
        gold = json.load(f)
    with open(a.candidate, encoding="utf-8") as f:
        cand = json.load(f)
    text = open(a.text, encoding="utf-8").read() if a.text else ""
    rep = compare(gold, cand, text, a.threshold)
    print_report(rep)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
