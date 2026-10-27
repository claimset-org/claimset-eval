import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import compare  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
GOLD = os.path.join(FIXTURES, "invented.claimset.json")      # an invented paper, independent of the pilot papers
TEXT = os.path.join(FIXTURES, "invented.txt")


def load():
    with open(GOLD, encoding="utf-8") as f:
        return json.load(f)


class CompareTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gold = load()
        with open(TEXT, encoding="utf-8") as f:
            cls.text = f.read()

    def test_self_comparison_is_perfect(self):
        rep = compare.compare(self.gold, copy.deepcopy(self.gold), self.text)
        for name in ("links", "definitions", "evidence", "limitations", "references", "relations"):
            self.assertEqual(rep[name]["recall"], 1.0, name)
            self.assertEqual(rep[name]["precision"], 1.0, name)
        self.assertEqual(rep["claims"]["all"]["recall"], 1.0)
        self.assertEqual(rep["claims"]["coding differences"], [])
        self.assertEqual(rep["evidence"]["table cells recovered"]["found"],
                         rep["evidence"]["table cells recovered"]["gold cells"])

    def test_renumbered_candidate_still_matches(self):
        cand = copy.deepcopy(self.gold)
        cand["claims"].reverse()
        new = {c["id"]: f"C{100 + i}" for i, c in enumerate(cand["claims"])}
        for c in cand["claims"]:
            c["id"] = new[c["id"]]
            for k in ("depends_on", "assumptions"):
                if k in c:
                    c[k] = [new[x] for x in c[k]]
        for lim in cand["limitations"]:
            lim["affects"] = [new[x] for x in lim["affects"]]
        rep = compare.compare(self.gold, cand, self.text)
        self.assertEqual(rep["claims"]["all"]["recall"], 1.0)
        self.assertEqual(rep["links"]["recall"], 1.0)

    def test_missing_claim_and_wrong_coding_are_reported(self):
        cand = copy.deepcopy(self.gold)
        dropped = cand["claims"].pop(0)
        cand["claims"][0]["type"] = "interpretive"
        rep = compare.compare(self.gold, cand, self.text)
        self.assertIn(dropped["id"], [m["id"] for m in rep["claims"]["missed"]])
        self.assertLess(rep["claims"]["all"]["recall"], 1.0)
        self.assertEqual(len(rep["claims"]["coding differences"]), 1)

    def test_bundled_claim_counts_as_present(self):
        cand = copy.deepcopy(self.gold)
        c1, c3 = cand["claims"][0], cand["claims"][2]
        c1["statement"] += " The pruning objective of SEP is monotone submodular."
        c1["source_spans"] = c1["source_spans"] + c3["source_spans"]
        c1["depends_on"] = []
        cand["claims"].remove(c3)
        rep = compare.compare(self.gold, cand, self.text)
        self.assertIn("C3", [m["id"] for m in rep["claims"]["missed"]])
        self.assertNotIn("C3", rep["claims"]["coverage"]["not covered"])
        self.assertEqual(rep["claims"]["coverage"]["bundles"], {"C1": ["C1", "C3"]})

    def test_hungarian_assignment(self):
        self.assertEqual(compare.hungarian([[0.9, 0.1], [0.2, 0.8]]), {0: 1, 1: 0})
        self.assertEqual(compare.hungarian([[0.5, 0.1, 0.9]]), {0: 1})



class TestSourceErrors(unittest.TestCase):
    def test_flags_and_corrections_count_as_finding_an_error(self):
        from compare import source_errors
        gold = {"paper": {"converted_from": {"corrections": [
            {"field": "D4.definition", "where": "p6.4", "printed": "W_3 = Phi", "recorded": "W_3 = I_n", "reason": "r"},
            {"field": "D4.definition", "where": "p6.12", "printed": "A = alpha 1_n'", "recorded": "A = alpha I_n",
             "reason": "r"},
            {"field": "C3.statement", "where": "p9.2", "printed": "x", "recorded": "y", "reason": "r"}]}}}
        cand = {"paper": {"converted_from": {"corrections": [{"where": "p9.2"}]}}}
        rep = source_errors(gold, cand, [{"where": "p6.4", "kind": "formula"}, {"where": "p6.9", "kind": "formula"}])
        self.assertEqual([r["found"] for r in rep["errors"]], ["paragraph", "page", "paragraph"])
        self.assertEqual(rep["recall"], 1.0)
        rep = source_errors(gold, {}, [])
        self.assertEqual(rep["recall"], 0.0)
        self.assertIsNone(source_errors({}, {}, [])["recall"])

if __name__ == "__main__":
    unittest.main()
