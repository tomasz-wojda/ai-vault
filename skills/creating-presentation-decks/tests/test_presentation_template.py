import base64
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = SKILL_ROOT / "templates" / "presentation_template.py"
DEFAULT_CONFIG = SKILL_ROOT / "templates" / "template_config.json"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


class PresentationTemplateTest(unittest.TestCase):
    def run_generator(self, *arguments):
        return subprocess.run(
            [sys.executable, str(GENERATOR), *map(str, arguments)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_default_config_is_anonymized(self):
        config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["identity"]["title"], "Presentation Topic")
        self.assertEqual(config["identity"]["presenter"], "Name Surname")
        self.assertEqual(config["identity"]["team"], "@team")
        self.assertEqual(config["identity"]["pdf_author"], "Name Surname")
        serialized = json.dumps(config)
        self.assertNotIn("Tomasz Wojda", serialized)
        self.assertNotIn("@tvn-devops", serialized)
        self.assertNotIn("wbd", serialized.lower())

    def test_generator_creates_requested_page_count(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "template.pdf"
            result = self.run_generator(
                "--config", DEFAULT_CONFIG, "--output", output, "--pages", "2"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = output.read_bytes()
            self.assertTrue(data.startswith(b"%PDF"))
            self.assertEqual(len(re.findall(rb"/Type\s*/Page(?!s)", data)), 2)
            self.assertIn("2 pages", result.stdout)

    def test_configuration_overrides_visible_identity_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
            config["identity"] = {
                "title": "Custom Topic",
                "presenter": "Example Person",
                "team": "@example",
                "pdf_author": "Example Person",
            }
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            output = root / "template.pdf"
            result = self.run_generator(
                "--config", config_path, "--output", output, "--pages", "1"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = output.read_bytes()
            self.assertIn(b"Custom Topic", data)
            self.assertIn(b"Example Person", data)

    def test_default_font_fallback_generates_without_font_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "template.pdf"
            result = self.run_generator(
                "--config", DEFAULT_CONFIG, "--output", output
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b"Helvetica", output.read_bytes())

    def test_custom_logo_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logo = root / "logo.png"
            logo.write_bytes(PNG_1X1)
            output = root / "template.pdf"
            result = self.run_generator(
                "--config", DEFAULT_CONFIG, "--output", output, "--logo", logo
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.exists())

    def test_missing_custom_logo_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_generator(
                "--config",
                DEFAULT_CONFIG,
                "--output",
                root / "template.pdf",
                "--logo",
                root / "missing.png",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("logo", result.stderr.lower())

    def test_missing_requested_font_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
            config["fonts"]["regular_path"] = str(root / "missing.ttf")
            config_path = root / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            result = self.run_generator(
                "--config", config_path, "--output", root / "template.pdf"
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("font", result.stderr.lower())

    def test_invalid_page_count_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_generator(
                "--config",
                DEFAULT_CONFIG,
                "--output",
                Path(directory) / "template.pdf",
                "--pages",
                "0",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("pages", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
