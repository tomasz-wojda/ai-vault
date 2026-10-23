import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from sysdiagram.cli import main

EXAMPLE = SKILL_ROOT / "templates" / "example-spec.json"
BOARD = "https://miro.com/app/board/x=/"


def run(argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


class CliEndToEndTest(unittest.TestCase):
    def test_full_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            code, stdout, _ = run(["validate", str(EXAMPLE), "--strict"])
            self.assertEqual(code, 0)
            self.assertIn("frames 2", stdout)
            code, _, _ = run(["mermaid", str(EXAMPLE), "--out", tmp])
            self.assertEqual(code, 0)
            self.assertEqual(sorted(p.name for p in (out / "mermaid").iterdir()), ["api.mmd", "data.mmd", "overview.mmd"])
            code, _, _ = run(["miro-details", str(EXAMPLE), "--out", tmp])
            self.assertEqual(code, 0)
            miro = out / "miro"
            self.assertTrue((miro / "batch-1.svg").is_file())
            self.assertTrue((miro / "frames" / "api.svg").is_file())
            layout = json.loads((miro / "layout.json").read_text(encoding="utf-8"))
            result_svg = "".join(f'<g id="{entry["local_id"]}" data-frame="x" data-miro-id="{900 + n}">' for n, entry in enumerate(layout))
            result = out / "result.json"
            result.write_text(json.dumps({"success": True, "result_svg": result_svg}), encoding="utf-8")
            ids_path = miro / "frame_ids.json"
            code, _, _ = run(["miro-ids", "--layout", str(miro / "layout.json"), "--results", str(result), "--out", str(ids_path)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(ids_path.read_text(encoding="utf-8")), {"api": "900", "data": "901"})
            code, _, _ = run(["miro-overview", str(EXAMPLE), "--out", tmp, "--board-url", BOARD, "--frame-ids", str(ids_path)])
            self.assertEqual(code, 0)
            overview = (miro / "frames" / "overview.svg").read_text(encoding="utf-8")
            self.assertIn("moveToWidget=900", overview)
            snapshot = (miro / "snapshot.svg").read_text(encoding="utf-8")
            self.assertEqual(len(re.findall(r"data-frame=", snapshot)), 3)
            code, _, _ = run(["ledger", str(EXAMPLE), "--out", tmp])
            self.assertEqual(code, 0)
            ledger = json.loads((out / "ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(len(ledger["claims"]), 12 + 6 + 5)
            self.assertEqual(ledger["counts"], {"observed": 18, "derived": 1, "inferred": 3, "unknown": 1})

    def test_validate_broken_spec_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.json"
            data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
            data["overview"]["edges"][0]["to"] = "missing"
            broken.write_text(json.dumps(data), encoding="utf-8")
            code, _, stderr = run(["validate", str(broken)])
            self.assertEqual(code, 1)
            self.assertIn("unknown node 'missing'", stderr)


if __name__ == "__main__":
    unittest.main()
