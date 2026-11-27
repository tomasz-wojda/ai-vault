import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import prom_range

RESULT = {
    "data": {
        "result": [
            {
                "metric": {"__name__": "up", "job": "node", "pod": "a", "instance": "10.0.0.1"},
                "values": [[1764158400, "1"], [1764158460, "0.5"]],
            },
            {"metric": {"__name__": "up"}, "values": [[1764158400, "12345.678"]]},
        ]
    }
}


class PromRangeTests(unittest.TestCase):
    def test_render_drops_labels_sorts_and_formats_utc(self):
        self.assertEqual(
            prom_range.render(RESULT),
            "instance=10.0.0.1,pod=a: 11-26T12:00=1 11-26T12:01=0.5\ntotal: 11-26T12:00=1.235e+04",
        )

    def test_query_range_builds_kubectl_call(self):
        completed = mock.Mock(stdout=json.dumps(RESULT))
        with mock.patch.object(prom_range.subprocess, "run", return_value=completed) as run:
            self.assertEqual(
                prom_range.query_range("ctx", "/proxy", "up", "1", "2", "60"), RESULT
            )
        run.assert_called_once_with(
            [
                "kubectl",
                "--context",
                "ctx",
                "get",
                "--raw",
                "/proxy?query=up&start=1&end=2&step=60",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_main_writes_evidence_with_query_header(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "evidence" / "prom"
            stdout = io.StringIO()
            with mock.patch.object(prom_range, "query_range", return_value=RESULT), contextlib.redirect_stdout(stdout):
                code = prom_range.main(
                    [
                        "--context", "ctx", "--out", str(out), "--name", "up",
                        "--expr", "up", "--start", "1", "--end", "2", "--step", "60",
                    ]
                )
            self.assertEqual(code, 0)
            written = (out / "up.txt").read_text(encoding="utf-8")
            self.assertTrue(written.startswith("QUERY: up\nRANGE: 1 2 step=60\n"))
            self.assertIn("== up\n", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
