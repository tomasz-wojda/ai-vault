import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import build_ca_bundle

PEM = (
    "-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n"
    "-----BEGIN CERTIFICATE-----\nBBBB\n-----END CERTIFICATE-----\n"
)


class BuildCaBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name) / "cache" / "ca-bundle.pem"

    def tearDown(self):
        self.temp.cleanup()

    def run_main(self, **patch):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(build_ca_bundle, "export_certificates", **patch), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = build_ca_bundle.main(["--out", str(self.out)])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_bundle_written_and_count_printed(self):
        code, stdout, stderr = self.run_main(return_value=PEM)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(self.out.read_text(encoding="utf-8"), PEM)
        self.assertEqual(stdout, f"wrote 2 certificates to {self.out}\n")

    def test_zero_certificates_rejected(self):
        code, _, stderr = self.run_main(return_value="")
        self.assertEqual(code, 2)
        self.assertIn("no certificates exported", stderr)
        self.assertFalse(self.out.exists())

    def test_failing_security_call_rejected(self):
        error = subprocess.CalledProcessError(44, ["security"])
        code, _, stderr = self.run_main(side_effect=error)
        self.assertEqual(code, 2)
        self.assertIn("security find-certificate failed", stderr)
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
