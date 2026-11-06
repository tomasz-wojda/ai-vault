import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


frontmatter = load("skill_frontmatter")
map_skills = load("map_skills")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class FrontmatterTest(unittest.TestCase):
    def test_plain_and_quoted_values(self):
        data = frontmatter.parse_frontmatter("---\nname: a\nversion: \"1.2.0\"\ndescription: 'It''s'\n---\nbody\n")
        self.assertEqual(data, {"name": "a", "version": "1.2.0", "description": "It's"})

    def test_folded_block(self):
        data = frontmatter.parse_frontmatter("---\nname: a\ndescription: >-\n  first line\n  second line\nversion: \"1.0.0\"\n---\n")
        self.assertEqual(data["description"], "first line second line")
        self.assertEqual(data["version"], "1.0.0")

    def test_literal_block(self):
        data = frontmatter.parse_frontmatter("---\nnotes: |-\n  a\n  b\n---\n")
        self.assertEqual(data["notes"], "a\nb")

    def test_wrapped_plain_value(self):
        data = frontmatter.parse_frontmatter("---\nname: speckit-plan\ndescription: Execute the planning workflow\n  to generate design artifacts.\n---\n")
        self.assertEqual(data["description"], "Execute the planning workflow to generate design artifacts.")

    def test_nested_maps_lists_and_booleans(self):
        text = ("---\nname: x\nmetadata:\n  author: someone\n  credits:\n    skill: show-me\n    url: \"https://e.x/a\"\n"
                "tags: [a, \"b c\"]\nitems:\n  - one\n  - two\nuser-invocable: true\n---\n")
        data = frontmatter.parse_frontmatter(text)
        self.assertEqual(data["metadata"], {"author": "someone", "credits": {"skill": "show-me", "url": "https://e.x/a"}})
        self.assertEqual(data["tags"], ["a", "b c"])
        self.assertEqual(data["items"], ["one", "two"])
        self.assertIs(data["user-invocable"], True)

    def test_double_quoted_escapes_and_unicode(self):
        data = frontmatter.parse_frontmatter('---\ndescription: "say \\"hi\\" 做成一页"\n---\n')
        self.assertEqual(data["description"], 'say "hi" 做成一页')

    def test_no_frontmatter(self):
        self.assertEqual(frontmatter.parse_frontmatter("# Title\n"), {})

    def test_unterminated(self):
        with self.assertRaises(frontmatter.FrontmatterError):
            frontmatter.parse_frontmatter("---\nname: a\n")


class MapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        repos = self.ws / "repos"
        write(repos / "ai-vault/skills/alpha/SKILL.md", "---\nname: alpha\nversion: \"1.0.0\"\ndescription: >-\n  Use when\n  alpha.\n---\n")
        (repos / "ai-vault/skills/alpha/references").mkdir()
        write(repos / "ai-vault/skills/manifest.json", json.dumps({"version": 1, "skills": [
            {"name": "alpha", "dir": "alpha", "required": True, "ides": ["cursor"]}]}))
        write(repos / "ai-vault/AGENTS.md", "rules\n")
        write(repos / "upstream/skills/beta/SKILL.md", "---\nname: beta\ndescription: Use when beta.\n---\n")
        write(repos / "upstream/.claude-plugin/plugin.json", "{}")
        write(repos / "upstream/node_modules/pkg/skills/ignored/SKILL.md", "---\nname: ignored\n---\n")
        write(repos / "scaleup/docs/resources/skills/upstream/skills/beta/SKILL.md", "---\nname: beta\ndescription: Use when beta.\n---\n")
        write(repos / "scaleup/docs/resources/skills/manifest.json", json.dumps({"entries": [{
            "repo": "upstream", "source_path": "repos/upstream/skills/beta",
            "dest_path": "docs/resources/skills/upstream/skills/beta", "source_commit": "abc123", "modified": False}]}))
        write(repos / "scaleup/.claude/skills/speckit-plan/SKILL.md",
              "---\nname: speckit-plan\ndescription: Plan.\nmetadata:\n  author: github-spec-kit\n  source: preset:docs-root\n---\n")
        links = self.ws / ".cursor/skills"
        links.mkdir(parents=True)
        os.symlink(repos / "ai-vault/skills/alpha", links / "alpha")
        os.symlink(self.ws / "missing", links / "broken")

    def tearDown(self):
        self.tmp.cleanup()

    def by_id(self, data):
        return {s["id"]: s for s in data["skills"]}

    def test_discovery_and_kinds(self):
        data = map_skills.build_map(self.ws)
        skills = self.by_id(data)
        self.assertEqual(set(skills), {
            "ai-vault:skills/alpha", "upstream:skills/beta",
            "scaleup:docs/resources/skills/upstream/skills/beta", "scaleup:.claude/skills/speckit-plan"})
        self.assertEqual(skills["ai-vault:skills/alpha"]["kind"], "canonical")
        self.assertEqual(skills["ai-vault:skills/alpha"]["description"], "Use when alpha.")
        self.assertEqual(skills["ai-vault:skills/alpha"]["resources"], ["references"])
        mirror = skills["scaleup:docs/resources/skills/upstream/skills/beta"]
        self.assertEqual(mirror["kind"], "mirror")
        self.assertEqual(mirror["mirror_of"], "upstream:skills/beta")
        self.assertEqual(mirror["source_commit"], "abc123")
        copy = skills["scaleup:.claude/skills/speckit-plan"]
        self.assertEqual(copy["kind"], "installed-copy")
        self.assertEqual(copy["generated_from"], "preset:docs-root")
        self.assertEqual(data["summary"], {"repos": 3, "skills": 4, "canonical": 2, "mirror": 1,
                                           "installed_copy": 1, "installed_links": 2})

    def test_installed_links_and_vault_manifest(self):
        data = map_skills.build_map(self.ws)
        skills = self.by_id(data)
        alpha = skills["ai-vault:skills/alpha"]
        self.assertEqual(alpha["installed"], [{"ide": "cursor", "link": ".cursor/skills/alpha"}])
        self.assertEqual(alpha["ai_vault_manifest"], {"required": True, "ides": ["cursor"]})
        links = {l["link"]: l for l in data["installed_links"]}
        self.assertEqual(links[".cursor/skills/alpha"]["resolves_to"], "ai-vault:skills/alpha")
        self.assertFalse(links[".cursor/skills/broken"]["exists"])
        self.assertIsNone(links[".cursor/skills/broken"]["resolves_to"])

    def test_repo_metadata_and_index(self):
        data = map_skills.build_map(self.ws)
        repos = {r["name"]: r for r in data["repos"]}
        self.assertEqual(repos["upstream"]["metadata"]["plugin_manifests"], ["repos/upstream/.claude-plugin/plugin.json"])
        self.assertEqual(repos["ai-vault"]["metadata"]["agent_files"], ["repos/ai-vault/AGENTS.md"])
        self.assertEqual(repos["ai-vault"]["git"], {"commit": None, "dirty": None})
        self.assertEqual(data["index"]["by_name"]["beta"],
                         ["scaleup:docs/resources/skills/upstream/skills/beta", "upstream:skills/beta"])

    def test_regenerate_command_and_check(self):
        output = self.ws / "skills/mapped-skills.json"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(map_skills.main(["--workspace", str(self.ws)]), 0)
        stored = json.loads(output.read_text())
        self.assertEqual(stored["generator"]["regenerate"], "python3 repos/ai-vault/scripts/map_skills.py --workspace .")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(map_skills.main(["--workspace", str(self.ws), "--check"]), 0)
        write(self.ws / "repos/upstream/skills/gamma/SKILL.md", "---\nname: gamma\ndescription: Use when gamma.\n---\n")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(map_skills.main(["--workspace", str(self.ws), "--check"]), 1)
        self.assertIn("skills + upstream:skills/gamma", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
