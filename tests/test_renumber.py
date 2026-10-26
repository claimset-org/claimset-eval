import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from renumber import renumber  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "invented.claimset.json"


class TestRenumber(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_ids_are_gapless_and_in_reading_order(self):
        doc = copy.deepcopy(self.doc)
        doc["claims"][0]["id"] = "C40"
        old = {c["id"]: c for c in doc["claims"]}
        out, mapping = renumber(doc)
        ids = [c["id"] for c in out["claims"]]
        self.assertEqual(ids, [f"C{n}" for n in range(1, len(ids) + 1)])
        roles = [c["role"] for c in out["claims"] if not any(s.get("kind") == "assumption" for s in c["support"])]
        rank = {"principal": 0, "supporting": 1, "secondary": 2}
        self.assertEqual(roles, sorted(roles, key=rank.get))
        self.assertEqual(set(mapping) & set(old), set(old))
        contributions = out["paper"]["contributions"]
        self.assertEqual(contributions, sorted(contributions, key=lambda x: int(x[1:])))

    def test_references_follow(self):
        doc = copy.deepcopy(self.doc)
        doc["claims"][0]["id"] = "C40"
        for c in doc["claims"]:
            c["depends_on"] = ["C40" if x == "C1" else x for x in c.get("depends_on") or []] or c.get("depends_on")
        doc["definitions"][0]["id"] = "D9"
        for c in doc["claims"]:
            c["statement"] = c["statement"].replace("[[D1:", "[[D9:")
        out, mapping = renumber(doc)
        text = json.dumps(out)
        self.assertNotIn('"C40"', text)
        self.assertNotIn("[[D9:", text)
        all_ids = {o["id"] for k in ("claims", "definitions", "evidence", "limitations") for o in out.get(k) or []}
        for c in out["claims"]:
            for x in c.get("depends_on") or []:
                self.assertIn(x, all_ids)


if __name__ == "__main__":
    unittest.main()
