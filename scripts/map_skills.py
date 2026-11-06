#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skill_frontmatter import FrontmatterError, parse_frontmatter

SCHEMA_VERSION = 1
SKILL_FILE = "SKILL.md"
PRUNED_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".pytest_cache"}
MIRROR_MANIFEST = Path("docs/resources/skills/manifest.json")
MIRROR_ROOT = "docs/resources/skills"
VAULT_MANIFEST = Path("repos/ai-vault/skills/manifest.json")
INSTALL_DIRS = {"cursor": ".cursor/skills", "claude": ".claude/skills", "agents": ".agents/skills"}
PLUGIN_DIRS = (".claude-plugin", ".cursor-plugin", ".codex-plugin", ".kimi-plugin", ".devin-plugin", ".agents/plugins")
AGENT_FILES = ("AGENTS.md", "CLAUDE.md", ".rules", "GEMINI.md")
SCRIPT = "repos/ai-vault/scripts/map_skills.py"
DEFAULT_OUTPUT = Path("skills/mapped-skills.json")
COMPARED_SECTIONS = ("skills", "installed_links")


def default_workspace():
    return Path(__file__).resolve().parents[3]


def rel(path, root):
    return Path(os.path.relpath(path, root)).as_posix()


def discover_skill_files(repo):
    found = []
    for current, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in PRUNED_DIRS)
        if SKILL_FILE in files:
            found.append(Path(current) / SKILL_FILE)
    return sorted(found)


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_mirror_manifests(workspace, repos):
    mirrors = {}
    for repo in repos:
        manifest = load_json(repo / MIRROR_MANIFEST)
        if not isinstance(manifest, dict):
            continue
        for entry in manifest.get("entries") or []:
            dest = entry.get("dest_path")
            if not dest:
                continue
            mirrors[rel(repo / dest, workspace)] = {
                "mirror_source": entry.get("source_path"),
                "mirror_modified": entry.get("modified"),
                "source_commit": entry.get("source_commit"),
                "manifest": rel(repo / MIRROR_MANIFEST, workspace),
            }
    return mirrors


def git_state(repo):
    def git(*args):
        out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=60)
        return out.stdout.strip() if out.returncode == 0 else None

    if not (repo / ".git").exists():
        return {"commit": None, "dirty": None}
    commit = git("rev-parse", "--short", "HEAD")
    status = git("status", "--porcelain", "--untracked-files=no")
    return {"commit": commit, "dirty": None if status is None else bool(status)}


def repo_metadata(repo, workspace):
    plugins = []
    for directory in PLUGIN_DIRS:
        folder = repo / directory
        if folder.is_dir():
            plugins += sorted(rel(p, workspace) for p in folder.glob("*.json"))
    agents = [rel(repo / f, workspace) for f in AGENT_FILES if (repo / f).exists()]
    return {"plugin_manifests": plugins, "agent_files": agents}


def classify_kind(skill_rel, frontmatter, mirrors):
    if skill_rel in mirrors or f"/{MIRROR_ROOT}/" in f"/{skill_rel}/":
        return "mirror"
    metadata = frontmatter.get("metadata")
    if isinstance(metadata, dict) and metadata.get("source"):
        return "installed-copy"
    return "canonical"


def normalise_text(value):
    return " ".join(str(value).split()) if value is not None else None


def skill_entry(skill_file, repo, workspace, mirrors):
    folder = skill_file.parent
    skill_rel = rel(folder, workspace)
    try:
        frontmatter = parse_frontmatter(skill_file.read_text(encoding="utf-8", errors="replace"))
        error = None
    except FrontmatterError as exc:
        frontmatter, error = {}, str(exc)
    metadata = frontmatter.get("metadata") if isinstance(frontmatter.get("metadata"), dict) else {}
    kind = classify_kind(skill_rel, frontmatter, mirrors)
    entry = {
        "id": f"{repo.name}:{rel(folder, repo)}",
        "name": frontmatter.get("name") or folder.name,
        "repo": repo.name,
        "path": skill_rel,
        "description": normalise_text(frontmatter.get("description")),
        "version": frontmatter.get("version") or metadata.get("version"),
        "kind": kind,
        "frontmatter_extra": {k: v for k, v in frontmatter.items() if k not in ("name", "description", "version")},
        "resources": sorted(p.name for p in folder.iterdir() if p.is_dir() and p.name not in PRUNED_DIRS),
        "installed": [],
    }
    if error:
        entry["frontmatter_error"] = error
    if kind == "mirror":
        entry.update({"mirror_of": None, **mirrors.get(skill_rel, {"mirror_source": None})})
    if kind == "installed-copy":
        entry.update({"generated_from": metadata.get("source"), "generator": metadata.get("author")})
    return entry


def installed_links(workspace, by_path):
    links = []
    for ide, directory in INSTALL_DIRS.items():
        folder = workspace / directory
        if not folder.is_dir():
            continue
        for link in sorted(folder.iterdir()):
            target = os.readlink(link) if link.is_symlink() else None
            resolved = link.resolve()
            try:
                resolved_rel = rel(resolved, workspace)
            except ValueError:
                resolved_rel = str(resolved)
            links.append({
                "ide": ide,
                "link": rel(link, workspace),
                "symlink": link.is_symlink(),
                "target": target,
                "resolves_to": by_path.get(resolved_rel),
                "exists": resolved.exists(),
            })
    return links


def attach_vault_manifest(skills, workspace):
    manifest = load_json(workspace / VAULT_MANIFEST) or {}
    declared = {f"repos/ai-vault/skills/{e.get('dir')}": e for e in manifest.get("skills") or []}
    for skill in skills:
        entry = declared.get(skill["path"])
        if entry and skill["kind"] == "canonical":
            skill["ai_vault_manifest"] = {"required": entry.get("required"), "ides": entry.get("ides")}


def build_map(workspace):
    workspace = Path(workspace).resolve()
    repos = sorted(p for p in (workspace / "repos").iterdir() if p.is_dir() and not p.name.startswith("."))
    mirrors = load_mirror_manifests(workspace, repos)
    skills, repo_rows = [], []
    for repo in repos:
        entries = [skill_entry(f, repo, workspace, mirrors) for f in discover_skill_files(repo)]
        skills += entries
        repo_rows.append({
            "name": repo.name,
            "path": rel(repo, workspace),
            "git": git_state(repo),
            "skill_count": len(entries),
            "canonical_count": sum(1 for e in entries if e["kind"] == "canonical"),
            "mirror_count": sum(1 for e in entries if e["kind"] == "mirror"),
            "installed_copy_count": sum(1 for e in entries if e["kind"] == "installed-copy"),
            "metadata": repo_metadata(repo, workspace),
        })
    by_path = {s["path"]: s["id"] for s in skills}
    for skill in skills:
        if skill["kind"] == "mirror" and skill.get("mirror_source"):
            skill["mirror_of"] = by_path.get(skill["mirror_source"])
    attach_vault_manifest(skills, workspace)
    links = installed_links(workspace, by_path)
    by_id = {s["id"]: s for s in skills}
    for link in links:
        if link["resolves_to"]:
            by_id[link["resolves_to"]]["installed"].append({"ide": link["ide"], "link": link["link"]})
    index = {}
    for skill in skills:
        index.setdefault(skill["name"], []).append(skill["id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "generator": {
            "script": SCRIPT,
            "regenerate": f"python3 {SCRIPT} --workspace .",
            "check": f"python3 {SCRIPT} --workspace . --check",
            "run_from": "workspace root",
        },
        "summary": {
            "repos": len(repo_rows),
            "skills": len(skills),
            "canonical": sum(1 for s in skills if s["kind"] == "canonical"),
            "mirror": sum(1 for s in skills if s["kind"] == "mirror"),
            "installed_copy": sum(1 for s in skills if s["kind"] == "installed-copy"),
            "installed_links": len(links),
        },
        "repos": repo_rows,
        "skills": skills,
        "installed_links": links,
        "index": {"by_name": dict(sorted(index.items()))},
    }


def write_map(data, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def drift(current, stored):
    report = []
    for section in COMPARED_SECTIONS:
        new = {json.dumps(i, sort_keys=True) for i in current.get(section, [])}
        old = {json.dumps(i, sort_keys=True) for i in (stored or {}).get(section, [])}
        report += [f"{section} + {json.loads(i).get('id') or json.loads(i).get('link')}" for i in sorted(new - old)]
        report += [f"{section} - {json.loads(i).get('id') or json.loads(i).get('link')}" for i in sorted(old - new)]
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Map every SKILL.md under <workspace>/repos into mapped-skills.json")
    parser.add_argument("--workspace", default=str(default_workspace()))
    parser.add_argument("--output")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    output = Path(args.output) if args.output else workspace / DEFAULT_OUTPUT
    data = build_map(workspace)
    if args.check:
        changes = drift(data, load_json(output))
        for line in changes:
            print(line)
        print(f"{'DRIFT' if changes else 'CURRENT'} {output}")
        return 1 if changes else 0
    write_map(data, output)
    s = data["summary"]
    print(f"WROTE {output} repos={s['repos']} skills={s['skills']} canonical={s['canonical']} "
          f"mirror={s['mirror']} installed_copy={s['installed_copy']} links={s['installed_links']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
