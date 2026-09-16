import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = SKILL_ROOT / "scripts" / "validate_reportlab_deck.py"


class ReportLabDeckValidatorTest(unittest.TestCase):
    def create_deck(
        self,
        directory,
        slides,
        notes=None,
        timings=None,
        questions=0,
    ):
        root = Path(directory)
        (root / "content.py").write_text(
            f"SLIDES = {slides!r}\n",
            encoding="utf-8",
        )
        (root / "notes.py").write_text(
            "\n".join(
                [
                    f"NOTES = {(notes if notes is not None else {1: 'note'})!r}",
                    f"TIMINGS = {(timings if timings is not None else {1: 1})!r}",
                    f"QUESTIONS_MINUTES = {questions!r}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (root / "renderer.py").write_text(
            textwrap.dedent(
                """
                from reportlab.lib.enums import TA_LEFT
                from reportlab.lib.styles import ParagraphStyle

                def register_fonts():
                    return "Helvetica", "Helvetica-Bold"

                def build_styles(regular, bold):
                    return {
                        "cell": ParagraphStyle(
                            "cell", fontName=regular, fontSize=11,
                            leading=14, alignment=TA_LEFT
                        ),
                        "cellb": ParagraphStyle(
                            "cellb", fontName=bold, fontSize=11,
                            leading=14, alignment=TA_LEFT
                        ),
                    }

                def markup(text):
                    return text
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    def run_validator(self, directory, *arguments):
        return subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--deck-dir",
                str(directory),
                "--content-module",
                "content",
                "--notes-module",
                "notes",
                "--renderer-module",
                "renderer",
                *arguments,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def write_temp_notes(self, directory, text):
        path = Path(directory) / "slide-notes-temp.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_valid_deck_passes(self):
        slides = [
            {
                "items": [
                    (
                        "table",
                        {
                            "colWidths": [100, 200],
                            "row_height": 35,
                            "rows": [
                                ["Term", "Meaning"],
                                ["state", "Machine-readable ticket state"],
                            ],
                        },
                    )
                ]
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            self.create_deck(directory, slides)
            result = self.run_validator(
                directory,
                "--slot-minutes",
                "5",
                "--expect-text",
                "Machine-readable ticket state",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS", result.stdout)
            self.assertIn("pages=1", result.stdout)

    def test_missing_note_key_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            self.create_deck(
                directory,
                [{"items": []}, {"items": []}],
                notes={1: "note"},
                timings={1: 1, 2: 1},
            )
            result = self.run_validator(directory)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("notes keys", result.stdout)

    def test_missing_timing_key_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            self.create_deck(
                directory,
                [{"items": []}, {"items": []}],
                notes={1: "note", 2: "note"},
                timings={1: 1},
            )
            result = self.run_validator(directory)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("timing keys", result.stdout)

    def test_row_height_count_mismatch_fails(self):
        slides = [
            {
                "items": [
                    (
                        "table",
                        {
                            "colWidths": [100, 200],
                            "row_heights": [35],
                            "rows": [["Term", "Meaning"], ["state", "value"]],
                        },
                    )
                ]
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            self.create_deck(directory, slides)
            result = self.run_validator(directory)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("row_heights", result.stdout)

    def test_invalid_span_fails(self):
        slides = [
            {
                "items": [
                    (
                        "table",
                        {
                            "colWidths": [100, 200],
                            "row_height": 35,
                            "rows": [["Term", "Meaning"], ["state", "value"]],
                            "spans": [((1, 1), (2, 1))],
                        },
                    )
                ]
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            self.create_deck(directory, slides)
            result = self.run_validator(directory)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("span", result.stdout)

    def test_wrapped_cell_overflow_fails(self):
        slides = [
            {
                "items": [
                    (
                        "table",
                        {
                            "colWidths": [80, 100],
                            "row_height": 19,
                            "rows": [
                                ["Term", "Meaning"],
                                [
                                    "state",
                                    "This description is intentionally long enough "
                                    "to wrap across several lines",
                                ],
                            ],
                        },
                    )
                ]
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            self.create_deck(directory, slides)
            result = self.run_validator(directory)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("cell overflow", result.stdout)

    def test_horizontal_span_uses_combined_width(self):
        slides = [
            {
                "items": [
                    (
                        "table",
                        {
                            "colWidths": [80, 100, 100],
                            "row_height": 35,
                            "rows": [
                                ["Term", "Meaning", "Extra"],
                                [
                                    "state",
                                    "This text fits only when both columns are used",
                                    "",
                                ],
                            ],
                            "spans": [((1, 1), (2, 1))],
                        },
                    )
                ]
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            self.create_deck(directory, slides)
            result = self.run_validator(directory)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_expected_text_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            self.create_deck(directory, [{"items": [("body", "Present text")]}])
            result = self.run_validator(
                directory,
                "--expect-text",
                "Approved exact text",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("expected text", result.stdout)

    def test_over_budget_is_reported_without_failing(self):
        with tempfile.TemporaryDirectory() as directory:
            self.create_deck(
                directory,
                [{"items": []}],
                timings={1: 8},
                questions=3,
            )
            result = self.run_validator(directory, "--slot-minutes", "10")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("WARNING", result.stdout)
            self.assertIn("11", result.stdout)

    def test_valid_temporary_notes_pass(self):
        slides = [
            {"items": [("h2", "First slide")]},
            {"items": [("h2", "Drugi slajd")]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            self.create_deck(
                directory,
                slides,
                notes={1: "note", 2: "note"},
                timings={1: 1, 2: 1},
            )
            notes = self.write_temp_notes(
                directory,
                "\n".join(
                    [
                        "# Slide notes",
                        "",
                        "## Slide 1 — First slide",
                        "",
                        "Narration one.",
                        "",
                        "## Slide 2 — Drugi slajd",
                        "",
                        "Narracja druga.",
                        "",
                        "## Archived notes",
                        "",
                        "### Slide 9 — Removed slide",
                        "",
                        "Preserved historical narration.",
                        "",
                    ]
                ),
            )
            result = self.run_validator(directory, "--temp-notes", notes)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_temporary_notes_file_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            self.create_deck(directory, [{"items": [("h2", "Only slide")]}])
            result = self.run_validator(
                directory,
                "--temp-notes",
                Path(directory) / "missing.md",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("temporary notes file", result.stdout)

    def test_missing_temporary_notes_section_fails(self):
        slides = [
            {"items": [("h2", "First slide")]},
            {"items": [("h2", "Second slide")]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            self.create_deck(
                directory,
                slides,
                notes={1: "note", 2: "note"},
                timings={1: 1, 2: 1},
            )
            notes = self.write_temp_notes(
                directory,
                "## Slide 1 — First slide\n\nNarration.\n",
            )
            result = self.run_validator(directory, "--temp-notes", notes)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("temporary notes sections", result.stdout)

    def test_duplicate_temporary_notes_section_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            self.create_deck(directory, [{"items": [("h2", "Only slide")]}])
            notes = self.write_temp_notes(
                directory,
                "\n".join(
                    [
                        "## Slide 1 — Only slide",
                        "",
                        "First version.",
                        "",
                        "## Slide 1 — Only slide",
                        "",
                        "Duplicate version.",
                        "",
                    ]
                ),
            )
            result = self.run_validator(directory, "--temp-notes", notes)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("temporary notes sections", result.stdout)

    def test_temporary_notes_title_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            self.create_deck(directory, [{"items": [("h2", "Canonical title")]}])
            notes = self.write_temp_notes(
                directory,
                "## Slide 1 — Different title\n\nNarration.\n",
            )
            result = self.run_validator(directory, "--temp-notes", notes)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("title mismatch", result.stdout)


if __name__ == "__main__":
    unittest.main()
