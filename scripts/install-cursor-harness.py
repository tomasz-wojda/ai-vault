#!/usr/bin/env python3

import argparse
import json
import os
import sys
from pathlib import Path


HOOK_LINKS = {
    "ai-vault-guard-git.py": "guard-git-mutations.py",
    "ai-vault-capture-response.py": "capture-agent-response.py",
    "ai-vault-require-handoff.py": "require-commit-handoff.py",
}
RULE_LINKS = {
    "ai-vault-governance.mdc": "ai-vault-governance.mdc",
}


class InstallError(RuntimeError):
    pass


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InstallError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise InstallError(f"{path} must contain a JSON object")
    return value


def merge_hooks(current: dict, fragment: dict) -> dict:
    if current.get("version", 1) != 1:
        raise InstallError("existing hooks.json version is not 1")
    merged = json.loads(json.dumps(current))
    merged["version"] = 1
    hooks = merged.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise InstallError("existing hooks field must be an object")
    for event, definitions in fragment["hooks"].items():
        existing = hooks.setdefault(event, [])
        if not isinstance(existing, list):
            raise InstallError(f"existing {event} hooks must be an array")
        commands = {item.get("command"): index for index, item in enumerate(existing)}
        for definition in definitions:
            command = definition["command"]
            if command in commands:
                existing[commands[command]] = definition
            else:
                existing.append(definition)
    return merged


def link_action(source: Path, target: Path) -> dict:
    relative = os.path.relpath(source.resolve(), target.parent.resolve())
    if target.is_symlink() and os.readlink(target) == relative:
        status = "unchanged"
    elif target.exists() or target.is_symlink():
        raise InstallError(f"refusing to replace {target}")
    else:
        status = "create"
    return {
        "kind": "symlink",
        "source": str(source),
        "target": str(target),
        "relative": relative,
        "status": status,
    }


def plan_install(workspace: Path, vault: Path) -> tuple[list[dict], dict, Path]:
    cursor = workspace / ".cursor"
    hook_dir = cursor / "hooks"
    rule_dir = cursor / "rules"
    actions: list[dict] = []
    for target_name, source_name in HOOK_LINKS.items():
        source = vault / "harness" / "cursor" / "hooks" / source_name
        actions.append(link_action(source, hook_dir / target_name))
    for target_name, source_name in RULE_LINKS.items():
        source = vault / "harness" / "cursor" / "rules" / source_name
        actions.append(link_action(source, rule_dir / target_name))
    hooks_path = cursor / "hooks.json"
    current = load_json(hooks_path, {"version": 1, "hooks": {}})
    fragment = load_json(
        vault / "harness" / "cursor" / "hooks.fragment.json",
        {},
    )
    merged = merge_hooks(current, fragment)
    actions.append(
        {
            "kind": "json",
            "target": str(hooks_path),
            "status": "unchanged" if merged == current else "update",
        }
    )
    return actions, merged, hooks_path


def apply_install(actions: list[dict], hooks: dict, hooks_path: Path) -> None:
    for action in actions:
        target = Path(action["target"])
        if action["kind"] == "symlink" and action["status"] == "create":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(action["relative"])
    if next(item for item in actions if item["kind"] == "json")["status"] == "update":
        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = hooks_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(hooks, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, hooks_path)


def verify_install(actions: list[dict], hooks_path: Path) -> None:
    for action in actions:
        target = Path(action["target"])
        if action["kind"] == "symlink":
            if not target.is_symlink() or not target.resolve().is_file():
                raise InstallError(f"installed link is invalid: {target}")
    hooks = load_json(hooks_path, {})
    commands = {
        item.get("command")
        for definitions in hooks.get("hooks", {}).values()
        for item in definitions
        if isinstance(item, dict)
    }
    expected = {
        definition["command"]
        for definitions in load_json(
            Path(__file__).resolve().parents[1]
            / "harness"
            / "cursor"
            / "hooks.fragment.json",
            {},
        )["hooks"].values()
        for definition in definitions
    }
    if not expected.issubset(commands):
        raise InstallError("installed hooks.json is missing ai-vault hooks")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--apply", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = Path(args.workspace).resolve()
    vault = Path(__file__).resolve().parents[1]
    try:
        actions, hooks, hooks_path = plan_install(workspace, vault)
        print(json.dumps({"apply": args.apply, "actions": actions}, indent=2))
        if args.apply:
            apply_install(actions, hooks, hooks_path)
            verify_install(actions, hooks_path)
        return 0
    except InstallError as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
