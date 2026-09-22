#!/usr/bin/env python3

import argparse
import json
import os
import sys
from pathlib import Path


HOOK_LINKS = {
    "git-handoff-baseline.py": "capture-turn-baseline.py",
    "git-handoff-guard-git.py": "guard-git-mutations.py",
    "git-handoff-capture-response.py": "capture-agent-response.py",
    "git-handoff-require-handoff.py": "require-commit-handoff.py",
}
LEGACY_HOOK_LINKS = {
    "ai-vault-guard-git.py": "guard-git-mutations.py",
    "ai-vault-capture-response.py": "capture-agent-response.py",
    "ai-vault-require-handoff.py": "require-commit-handoff.py",
}
LEGACY_RULE_LINKS = {
    "ai-vault-governance.mdc": "ai-vault-governance.mdc",
}
LEGACY_HOOK_COMMANDS = {
    ".cursor/hooks/ai-vault-guard-git.py",
    ".cursor/hooks/ai-vault-capture-response.py",
    ".cursor/hooks/ai-vault-require-handoff.py",
}
RULE_LINKS = {
    "git-handoff-governance.mdc": "git-handoff-governance.mdc",
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


def managed_relative(source: Path, target: Path) -> bool:
    if not target.is_symlink():
        return False
    try:
        return target.resolve() == source.resolve()
    except OSError:
        return False


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


def remove_legacy_hook_entries(hooks: dict) -> dict:
    merged = json.loads(json.dumps(hooks))
    hook_map = merged.get("hooks")
    if not isinstance(hook_map, dict):
        return merged
    for event, definitions in hook_map.items():
        if not isinstance(definitions, list):
            continue
        hook_map[event] = [
            item
            for item in definitions
            if item.get("command") not in LEGACY_HOOK_COMMANDS
        ]
    return merged


def hook_fragment(vault: Path, scope: str) -> dict:
    fragment = load_json(
        vault / "harness" / "cursor" / "hooks.fragment.json",
        {},
    )
    if scope == "workspace":
        return fragment
    transformed = json.loads(json.dumps(fragment))
    for definitions in transformed.get("hooks", {}).values():
        for definition in definitions:
            command = definition.get("command")
            if isinstance(command, str) and command.startswith(".cursor/"):
                definition["command"] = command.removeprefix(".cursor/")
    return transformed


def link_action(source: Path, target: Path) -> dict:
    relative = os.path.relpath(source.resolve(), target.parent.resolve())
    if target.is_symlink() and os.readlink(target) == relative:
        status = "unchanged"
    elif target.exists() or target.is_symlink():
        if managed_relative(source, target):
            status = "unchanged"
        else:
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


def unlink_action(target: Path, source: Path) -> dict | None:
    if not target.is_symlink():
        return None
    if not managed_relative(source, target):
        return None
    return {
        "kind": "symlink-remove",
        "target": str(target),
        "status": "remove",
    }


def install_root(scope: str, workspace: Path | None) -> Path:
    if scope == "user":
        return Path.home() / ".cursor"
    if scope == "workspace":
        if workspace is None:
            raise InstallError("workspace scope requires --workspace")
        return workspace / ".cursor"
    raise InstallError(f"unsupported scope: {scope}")


def plan_install(
    scope: str,
    workspace: Path | None,
    vault: Path,
    migrate_legacy: bool,
) -> tuple[list[dict], dict, Path]:
    cursor = install_root(scope, workspace)
    hook_dir = cursor / "hooks"
    rule_dir = cursor / "rules"
    actions: list[dict] = []
    for target_name, source_name in HOOK_LINKS.items():
        source = vault / "harness" / "cursor" / "hooks" / source_name
        actions.append(link_action(source, hook_dir / target_name))
    if scope == "workspace" and migrate_legacy:
        for target_name, source_name in LEGACY_HOOK_LINKS.items():
            source = vault / "harness" / "cursor" / "hooks" / source_name
            removal = unlink_action(hook_dir / target_name, source)
            if removal is not None:
                actions.append(removal)
        for target_name, source_name in LEGACY_RULE_LINKS.items():
            source = vault / "harness" / "cursor" / "rules" / source_name
            removal = unlink_action(rule_dir / target_name, source)
            if removal is not None:
                actions.append(removal)
    if scope == "workspace":
        for target_name, source_name in RULE_LINKS.items():
            source = vault / "harness" / "cursor" / "rules" / source_name
            actions.append(link_action(source, rule_dir / target_name))
    hooks_path = cursor / "hooks.json"
    current = load_json(hooks_path, {"version": 1, "hooks": {}})
    fragment = hook_fragment(vault, scope)
    merged = merge_hooks(current, fragment)
    if migrate_legacy:
        merged = remove_legacy_hook_entries(merged)
    changed = any(action["status"] == "create" for action in actions)
    changed = changed or merged != current
    if scope == "user" and changed:
        actions.append(
            {
                "kind": "grace-marker",
                "target": str(
                    Path.home()
                    / ".cursor"
                    / "hook-state"
                    / "git-handoff"
                    / ".migration-grace"
                ),
                "status": "create",
            }
        )
    actions.append(
        {
            "kind": "json",
            "target": str(hooks_path),
            "status": "unchanged" if merged == current else "update",
        }
    )
    return actions, merged, hooks_path


def plan_legacy_removal(
    workspace: Path,
    vault: Path,
) -> tuple[list[dict], dict, Path]:
    cursor = workspace / ".cursor"
    hook_dir = cursor / "hooks"
    actions: list[dict] = []
    for target_name, source_name in LEGACY_HOOK_LINKS.items():
        source = vault / "harness" / "cursor" / "hooks" / source_name
        removal = unlink_action(hook_dir / target_name, source)
        if removal is not None:
            actions.append(removal)
    rule_dir = cursor / "rules"
    for target_name, source_name in LEGACY_RULE_LINKS.items():
        source = vault / "harness" / "cursor" / "rules" / source_name
        removal = unlink_action(rule_dir / target_name, source)
        if removal is not None:
            actions.append(removal)
    for target_name, source_name in RULE_LINKS.items():
        source = vault / "harness" / "cursor" / "rules" / source_name
        actions.append(link_action(source, rule_dir / target_name))
    hooks_path = cursor / "hooks.json"
    current = load_json(hooks_path, {"version": 1, "hooks": {}})
    merged = remove_legacy_hook_entries(current)
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
        if action["kind"] == "symlink-remove" and action["status"] == "remove":
            target.unlink(missing_ok=True)
        if action["kind"] == "grace-marker" and action["status"] == "create":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("pending\n", encoding="utf-8")
    if next(item for item in actions if item["kind"] == "json")["status"] == "update":
        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = hooks_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(hooks, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, hooks_path)


def verify_install(
    actions: list[dict],
    hooks_path: Path,
    vault: Path,
    scope: str,
) -> None:
    for action in actions:
        if action["kind"] == "grace-marker":
            if not Path(action["target"]).is_file():
                raise InstallError("migration grace marker was not created")
            continue
        if action["kind"] not in {"symlink", "symlink-remove"}:
            continue
        target = Path(action["target"])
        if action["kind"] == "symlink-remove":
            if target.exists():
                raise InstallError(f"legacy hook link was not removed: {target}")
            continue
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
        for definitions in hook_fragment(vault, scope)["hooks"].values()
        for definition in definitions
    }
    if not expected.issubset(commands):
        raise InstallError("installed hooks.json is missing git-handoff hooks")


def verify_legacy_removal(actions: list[dict], hooks_path: Path) -> None:
    for action in actions:
        target = Path(action["target"])
        if action["kind"] == "symlink-remove" and target.exists():
            raise InstallError(f"legacy managed link was not removed: {target}")
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
    remaining = sorted(LEGACY_HOOK_COMMANDS & commands)
    if remaining:
        raise InstallError(
            "legacy hook entries remain: " + ", ".join(remaining)
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scope",
        choices=("user", "workspace"),
    )
    parser.add_argument("--workspace")
    parser.add_argument(
        "--migrate-workspace",
        help="Remove managed legacy ai-vault hooks from this workspace.",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--migrate-legacy",
        action="store_true",
        help="Remove managed ai-vault workspace hook entries and symlinks.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = Path(args.workspace).resolve() if args.workspace else None
    scope = args.scope or ("workspace" if workspace else "user")
    vault = Path(__file__).resolve().parents[1]
    migrate_legacy = args.migrate_legacy or scope == "workspace"
    try:
        actions, hooks, hooks_path = plan_install(
            scope,
            workspace,
            vault,
            migrate_legacy,
        )
        migration = None
        if args.migrate_workspace:
            migration_workspace = Path(args.migrate_workspace).resolve()
            migration = plan_legacy_removal(migration_workspace, vault)
        print(
            json.dumps(
                {
                    "apply": args.apply,
                    "scope": scope,
                    "workspace": str(workspace) if workspace else None,
                    "actions": actions,
                    "migration_actions": (
                        migration[0] if migration is not None else []
                    ),
                },
                indent=2,
            )
        )
        if args.apply:
            apply_install(actions, hooks, hooks_path)
            verify_install(actions, hooks_path, vault, scope)
            if migration is not None:
                migration_actions, migration_hooks, migration_path = migration
                apply_install(
                    migration_actions,
                    migration_hooks,
                    migration_path,
                )
                verify_legacy_removal(
                    migration_actions,
                    migration_path,
                )
        return 0
    except InstallError as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
