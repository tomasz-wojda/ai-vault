import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from sysdiagram.mermaid_render import check_structure, render_frame_mermaid, render_overview_mermaid, safe_id
from sysdiagram.palette import resolve
from sysdiagram.spec_loader import load_spec

EXAMPLE = SKILL_ROOT / "templates" / "example-spec.json"


class MermaidRenderTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(EXAMPLE)
        self.palette = resolve(self.spec.categories)
        self.overview = render_overview_mermaid(self.spec, self.palette)

    def test_overview_header_and_subgraphs(self):
        lines = self.overview.splitlines()
        self.assertEqual(lines[0], "flowchart LR")
        subgraphs = [line for line in lines if line.strip().startswith("subgraph ")]
        ends = [line for line in lines if line.strip() == "end"]
        self.assertEqual(len(subgraphs), len(self.spec.overview.zones))
        self.assertEqual(len(subgraphs), len(ends))
        self.assertEqual(check_structure(self.overview), [])

    def test_dashed_only_for_data_relations(self):
        dashed = [line for line in self.overview.splitlines() if "-.->" in line]
        self.assertEqual(len(dashed), 2)
        self.assertTrue(any("n_orders_db" in line for line in dashed))
        self.assertTrue(all("-.->" not in line for line in self.overview.splitlines() if "order.created" in line))

    def test_quote_escaping_and_reserved_id(self):
        self.spec.overview.nodes[0].title = 'say "hi"'
        self.spec.overview.nodes[0].id = "end"
        self.spec.overview.edges[0].from_id = "end"
        text = render_overview_mermaid(self.spec, self.palette)
        self.assertIn("#quot;hi#quot;", text)
        self.assertIn("n_end[", text)
        self.assertEqual(safe_id("end", "n"), "n_end")
        self.assertEqual(check_structure(text), [])

    def test_inferred_class_applied(self):
        self.assertIn("classDef ev_inferred stroke-dasharray: 5 5", self.overview)
        self.assertIn("class n_worker ev_inferred", self.overview)

    def test_click_lines_only_with_ids_and_url(self):
        self.assertNotIn("click ", self.overview)
        linked = render_overview_mermaid(self.spec, self.palette, {"api": "111", "data": "222"}, "https://miro.com/app/board/x=/")
        self.assertIn('click n_gateway "https://miro.com/app/board/x=/?moveToWidget=111"', linked)
        self.assertIn('click n_orders_db "https://miro.com/app/board/x=/?moveToWidget=222"', linked)

    def test_detail_frame_has_subgraph_per_area(self):
        frame = self.spec.frames[0]
        text = render_frame_mermaid(frame, self.palette)
        self.assertEqual(text.splitlines()[0], "flowchart TB")
        subgraphs = [line for line in text.splitlines() if line.strip().startswith("subgraph ")]
        self.assertEqual(len(subgraphs), len(frame.areas))
        self.assertIn("class c_api_1_2 ev_inferred", text)
        self.assertEqual(check_structure(text), [])

    def test_structure_flags_undeclared_endpoint(self):
        text = 'flowchart LR\n    n_a["a"]\n    n_a --> n_b\n'
        self.assertIn("line 3: undeclared endpoint 'n_b'", check_structure(text))

    def test_structure_flags_unbalanced_subgraph(self):
        text = 'flowchart LR\n    subgraph z_a["a"]\n    n_a["a"]\n'
        self.assertIn("1 subgraph block(s) without 'end'", check_structure(text))


if __name__ == "__main__":
    unittest.main()
