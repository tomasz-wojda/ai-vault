import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from sysdiagram.spec_loader import SpecError, load_spec

EXAMPLE = SKILL_ROOT / "templates" / "example-spec.json"


class SpecValidationTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def errors_for(self, data):
        path = Path(self.tmp.name) / "spec.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(SpecError) as raised:
            load_spec(path)
        return raised.exception.errors

    def mutated(self):
        return copy.deepcopy(self.data)

    def assert_error(self, data, fragment):
        errors = self.errors_for(data)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_example_loads(self):
        spec = load_spec(EXAMPLE)
        self.assertEqual(len(spec.frames), 2)
        self.assertEqual(len(spec.overview.nodes), 6)

    def test_duplicate_frame_key(self):
        data = self.mutated()
        data["frames"][1]["key"] = "api"
        self.assert_error(data, "frames[1].key: duplicate frame key 'api'")

    def test_unknown_category(self):
        data = self.mutated()
        data["frames"][0]["areas"][0]["cards"][0]["category"] = "magenta"
        self.assert_error(data, "frames[0].areas[0].cards[0].category: unknown category 'magenta'")

    def test_observed_card_without_sources(self):
        data = self.mutated()
        data["frames"][0]["areas"][0]["cards"][0]["sources"] = []
        self.assert_error(data, "frames[0].areas[0].cards[0].sources: required unless evidence is unknown")

    def test_dangling_edge(self):
        data = self.mutated()
        data["overview"]["edges"][0]["to"] = "missing"
        self.assert_error(data, "overview.edges[0].to: unknown node 'missing'")

    def test_self_edge(self):
        data = self.mutated()
        data["overview"]["edges"][0]["to"] = data["overview"]["edges"][0]["from"]
        self.assert_error(data, "overview.edges[0]: self-edge on 'browser'")

    def test_bad_relation(self):
        data = self.mutated()
        data["overview"]["edges"][0]["relation"] = "talks_to"
        self.assert_error(data, "overview.edges[0].relation: 'talks_to' not in vocabulary")

    def test_unknown_expands(self):
        data = self.mutated()
        data["overview"]["nodes"][2]["expands"] = "nowhere"
        self.assert_error(data, "overview.nodes[2].expands: unknown frame 'nowhere'")

    def test_span_three(self):
        data = self.mutated()
        data["frames"][0]["areas"][0]["cards"][0]["span"] = 3
        self.assert_error(data, "frames[0].areas[0].cards[0].span: 3 must be 1 or 2")

    def test_columns_five(self):
        data = self.mutated()
        data["overview"]["zones"][0]["columns"] = 5
        self.assert_error(data, "overview.zones[0].columns: 5 must be 1 to 4")

    def test_missing_from_svg(self):
        data = self.mutated()
        data["frames"][1] = {"key": "data", "title": "t", "subtitle": "s", "legend": [], "from_svg": "absent.svg"}
        self.assert_error(data, "frames[1].from_svg: file not found")

    def test_wrong_schema(self):
        data = self.mutated()
        data["schema"] = "system-diagram/0"
        self.assert_error(data, "schema: 'system-diagram/0' must be 'system-diagram/1'")

    def test_multiple_errors_reported_together(self):
        data = self.mutated()
        data["schema"] = "other"
        data["overview"]["edges"][0]["relation"] = "talks_to"
        data["frames"][0]["areas"][0]["cards"][0]["span"] = 3
        self.assertGreaterEqual(len(self.errors_for(data)), 3)


if __name__ == "__main__":
    unittest.main()
