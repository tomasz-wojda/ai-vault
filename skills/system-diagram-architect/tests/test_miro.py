import json
import re
import sys
import tempfile
import unittest
import xml.dom.minidom
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from sysdiagram.miro_detail import CARD_W, FRAME_W, ZONE_W, layout_areas, place_cards, render_from_svg
from sysdiagram.miro_overview import connector_sides, layout_overview, render_overview
from sysdiagram.miro_publish import batch_groups, build_detail_groups, extract_frame_ids, grid_positions, svg_document
from sysdiagram.miro_shapes import frame_group
from sysdiagram.model import Area, Card, Frame, Zone
from sysdiagram.palette import resolve
from sysdiagram.spec_loader import load_spec

EXAMPLE = SKILL_ROOT / "templates" / "example-spec.json"
BOARD = "https://miro.com/app/board/x=/"


def card(span=1):
    return Card("blue", "t", "b", "f", span, "observed", ["a"])


def ids_in(document):
    return set(re.findall(r'\bid="([^"]+)"', document))


class MiroDetailTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(EXAMPLE)
        self.palette = resolve(self.spec.categories)

    def test_cards_inside_zone(self):
        placed, _ = layout_areas(self.spec.frames[0].areas)
        for _, area, slots, x, y, h in placed:
            for row, col, span in slots:
                left = x + 32 + col * 452
                width = CARD_W * span + 32 * (span - 1)
                self.assertLessEqual(left + width, x + ZONE_W)
                self.assertLessEqual(y + 90 + row * 192 + 160, y + h)

    def test_wide_card_wraps_from_column_two(self):
        slots, rows = place_cards([card(), card(), card(2)])
        self.assertEqual(slots[2], (1, 0, 2))
        self.assertEqual(rows, 2)

    def test_masonry_uses_shorter_column(self):
        areas = [Area("a", [card()] * 9), Area("b", [card()]), Area("c", [card()])]
        placed, _ = layout_areas(areas)
        self.assertEqual(placed[0][3], 64)
        self.assertEqual(placed[1][3], 1520)
        self.assertEqual(placed[2][3], 1520)

    def test_detail_frame_width_and_documents(self):
        groups = build_detail_groups(self.spec, self.palette)
        for _, _, group, entry in groups:
            self.assertEqual(entry["width"], FRAME_W)
            document = svg_document([group])
            xml.dom.minidom.parseString(document)
            self.assertNotIn("data-miro-id", document)

    def test_grid_places_fifth_frame_on_second_row(self):
        positions = grid_positions([100, 300, 200, 100, 50], 1000)
        self.assertEqual(positions[3], (1000 + 3 * 3232, 0))
        self.assertEqual(positions[4], (1000, 300 + 320))

    def test_batches_respect_limit(self):
        groups = [(str(n), "p", "x" * 40, {}) for n in range(5)]
        batches = batch_groups(groups, limit=100)
        self.assertEqual([len(batch) for batch in batches], [2, 2, 1])

    def test_from_svg_prefixes_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "frame.svg"
            inner = frame_group("x", "Old", 0, 0, 100, 200, ['<rect id="a" x="0" y="0" width="1" height="1" />', '<line id="l" data-start="a" data-end="a" />', '<textArea id="t">Old</textArea>'])
            source.write_text(svg_document([inner]), encoding="utf-8")
            frame = Frame("k", "New", "s", [], [], from_svg=source)
            items, height = render_from_svg("f03", frame)
            joined = "\n".join(items)
            self.assertEqual(height, 200)
            self.assertIn('id="f03a"', joined)
            self.assertIn('data-start="f03a"', joined)
            self.assertIn(">New</textArea>", joined)


class MiroOverviewTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(EXAMPLE)
        self.palette = resolve(self.spec.categories)

    def document(self, frame_ids=None, board_url=None):
        items, width, height = render_overview(self.spec, self.palette, frame_ids, board_url)
        return svg_document([frame_group("ov", self.spec.overview.title, 0, 0, width, height, items)])

    def test_overview_is_valid_and_endpoints_exist(self):
        document = self.document()
        xml.dom.minidom.parseString(document)
        self.assertNotIn("data-miro-id", document)
        ids = ids_in(document)
        for endpoint in re.findall(r'data-(?:start|end)="([^"]+)"', document):
            self.assertIn(endpoint, ids)
        self.assertEqual(document.count("<line "), len(self.spec.overview.edges))

    def test_connector_sides(self):
        left, right = Zone("a", "a", "", 0, 1), Zone("b", "b", "", 1, 1)
        top, below, beside = (0, 0, 320, 120), (0, 300, 320, 120), (400, 0, 320, 120)
        self.assertEqual(connector_sides(left, right, top, top), ("right", "left", True))
        self.assertEqual(connector_sides(right, left, top, below), ("left", "right", False))
        self.assertEqual(connector_sides(left, left, top, below), ("bottom", "top", False))
        self.assertEqual(connector_sides(left, left, below, top), ("top", "bottom", False))
        self.assertEqual(connector_sides(left, left, top, beside), ("right", "left", True))
        self.assertEqual(connector_sides(left, left, beside, top), ("left", "right", True))

    def test_anchors_only_with_frame_ids(self):
        self.assertNotIn("moveToWidget", self.document())
        linked = self.document({"api": "111", "data": "222"}, BOARD)
        self.assertIn("moveToWidget=111", linked)
        self.assertIn("moveToWidget=222", linked)

    def test_index_panel_lists_every_frame(self):
        document = self.document({"api": "111", "data": "222"}, BOARD)
        index = re.search(r'<rect id="ovx"[^>]*data-content="([^"]*)"', document).group(1)
        for frame in self.spec.frames:
            self.assertIn(frame.title, index)

    def test_layout_lanes_left_to_right(self):
        layout = layout_overview(self.spec.overview, len(self.spec.frames))
        xs = [layout["zones"][zone_id][0] for zone_id in ("client", "api", "data")]
        self.assertEqual(xs, sorted(xs))
        self.assertGreater(layout["width"], xs[-1])


class FrameIdTest(unittest.TestCase):
    def test_extract_and_missing(self):
        layout = [{"key": "api", "local_id": "f00f"}, {"key": "data", "local_id": "f01f"}]
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / "result.json"
            result.write_text(json.dumps({"result_svg": '<g id="f00f" transform="translate(0,0)" data-frame="a" data-miro-id="123">'}), encoding="utf-8")
            with self.assertRaises(ValueError) as raised:
                extract_frame_ids(layout, [result])
            self.assertIn("data", str(raised.exception))
            result.write_text(
                json.dumps({"result_svg": '<g id="f00f" data-frame="a" data-miro-id="123"><g id="f01f" data-frame="b" data-miro-id="456">'}),
                encoding="utf-8",
            )
            self.assertEqual(extract_frame_ids(layout, [result]), {"api": "123", "data": "456"})


if __name__ == "__main__":
    unittest.main()
