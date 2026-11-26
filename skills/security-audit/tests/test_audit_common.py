import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import audit_common  # noqa: E402


class DefaultIgnorableTableTests(unittest.TestCase):
    def test_range_edges_are_inclusive(self):
        for start, end in audit_common.DEFAULT_IGNORABLE_RANGES:
            self.assertTrue(audit_common.is_default_ignorable(chr(start)), hex(start))
            self.assertTrue(audit_common.is_default_ignorable(chr(end)), hex(end))

    def test_neighbours_outside_ranges_are_not_ignorable(self):
        for code in (0x00AC, 0x00AE, 0x034E, 0x0350, 0x200A, 0x2010, 0xFE10, 0xFFF9, 0xE1000, 0x41):
            self.assertFalse(audit_common.is_default_ignorable(chr(code)), hex(code))


class JavaScriptStringSemanticsTests(unittest.TestCase):
    def test_js_trim_matches_ecmascript_whitespace(self):
        self.assertEqual(audit_common.js_trim("\ufeff value \u3000"), "value")
        self.assertEqual(audit_common.js_trim("\u001cvalue"), "\u001cvalue")
        self.assertEqual(audit_common.js_trim("\u0085value"), "\u0085value")

    def test_utf16_key_orders_like_javascript_comparison(self):
        astral = "\U0001f600"
        bmp_high = "\uffff"
        self.assertLess(audit_common.utf16_key(astral), audit_common.utf16_key(bmp_high))
        self.assertGreater(astral, bmp_high)

    def test_utf16_length_counts_surrogate_pairs(self):
        self.assertEqual(audit_common.utf16_length("a\U0001f600"), 3)
        self.assertEqual(audit_common.code_point_length("a\U0001f600"), 2)
        self.assertEqual(audit_common.code_point_length("\ud83d\ude00"), 1)

    def test_js_number_text_matches_number_to_string(self):
        cases = {
            1: "1",
            -0.0: "0",
            123.0: "123",
            1.5: "1.5",
            1e21: "1e+21",
            1e20: "100000000000000000000",
            1.5e-7: "1.5e-7",
            0.000001: "0.000001",
            2**60: "1152921504606847000",
        }
        for value, expected in cases.items():
            self.assertEqual(audit_common.js_number_text(value), expected, repr(value))

    def test_js_keys_puts_array_indexes_first(self):
        value = {"b": 1, "10": 2, "a": 3, "2": 4, "01": 5, "4294967295": 6}
        self.assertEqual(audit_common.js_keys(value), ["2", "10", "b", "a", "01", "4294967295"])

    def test_safe_quote_clips_at_utf16_units_and_escapes_controls(self):
        clipped = audit_common.safe_quote("x" * 255 + "\U0001f600" + "tail")
        self.assertTrue(clipped.endswith('\\ud83d..."'))
        self.assertEqual(audit_common.safe_quote("\u001b\u202e"), '"\\u001b\\u202e"')
        self.assertEqual(audit_common.safe_quote(audit_common.UNDEFINED), '"<undefined>"')
        self.assertEqual(audit_common.safe_quote({}), '"<object>"')
        self.assertEqual(audit_common.safe_quote(float("inf")), '"<number>"')


class JsonParsingTests(unittest.TestCase):
    def test_rejects_non_standard_constants(self):
        for text in ("NaN", "[Infinity]", "[-Infinity]"):
            with self.assertRaises(ValueError):
                audit_common.parse_json_text(text)

    def test_keeps_a_leading_byte_order_mark_invalid(self):
        with self.assertRaises(ValueError):
            audit_common.parse_json_text("\ufeff[]")

    def test_is_js_integer_excludes_booleans(self):
        self.assertTrue(audit_common.is_js_integer(3))
        self.assertTrue(audit_common.is_js_integer(3.0))
        self.assertFalse(audit_common.is_js_integer(True))
        self.assertFalse(audit_common.is_js_integer(3.5))


if __name__ == "__main__":
    unittest.main()
