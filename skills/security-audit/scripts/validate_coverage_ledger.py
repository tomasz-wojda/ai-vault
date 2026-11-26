#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from types import MappingProxyType

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common import (
    WINDOWS_RESERVED_COMPONENT,
    ErrorList,
    JsonStructureError,
    SafeInputError,
    has_path_forbidden_character,
    has_visible_prose,
    is_js_integer,
    is_safe_relative_path,
    js_get,
    js_keys,
    js_trim,
    parse_json_text,
    read_file_within_limit as read_input_within_limit,
    safe_quote,
    type_of,
    utf16_key,
    utf16_length,
)

LIMITS = MappingProxyType({
    "inputBytes": 5 * 1024 * 1024,
    "units": 10000,
    "collectionItems": 1000,
    "objectFields": 1000,
    "nestingDepth": 64,
    "preflightValues": 500000,
    "validationErrors": 100,
})
MAX_INPUT_BYTES = LIMITS["inputBytes"]
MAX_UNITS = LIMITS["units"]
MAX_LIST_ITEMS = LIMITS["collectionItems"]
MAX_TEXT_LENGTH = 4096
REQUIRED_FIELDS = (
    "coverage_id",
    "canonical_refs",
    "surface",
    "boundary",
    "subsystem",
    "attack_class",
    "starting_paths",
    "ordinary_attack_class_block",
    "selected_companion_blocks",
    "excluded_blocks",
    "prior_status",
    "attempts",
    "wave",
    "status",
    "agent_id",
    "reviewed_paths",
    "local_checks",
    "result_fingerprints",
    "unresolved",
)
REF_FIELDS = ("surface", "boundary", "subsystem", "attack_class")
STATUSES = frozenset([
    "planned",
    "not_applicable",
    "out_of_scope",
    "in_progress",
    "covered",
    "candidate",
    "blocked",
    "deferred",
])
ATTEMPT_STATUSES = frozenset(["covered", "candidate", "blocked"])
ATTEMPT_FIELDS = (
    "wave",
    "status",
    "agent_id",
    "reviewed_paths",
    "local_checks",
    "result_fingerprints",
    "unresolved",
    "reassignment_reason",
)
PRIOR_STATUSES = frozenset([
    "new",
    "prior_confirmed_same_source",
    "prior_confirmed_changed_source",
    "prior_needs_validation",
    "prior_deferred",
    "prior_blocked",
    "prior_out_of_scope",
    "prior_covered_same_source",
    "prior_covered_changed_source",
    "prior_rejected_claim_changed",
    "none",
])
FINGERPRINT_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]*")
AGENT_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
WINDOWS_RESERVED_AGENT_ID = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])")
PREFLIGHT_WHITESPACE = frozenset(" \t\r\n")
STRING_SPECIAL = re.compile(r'["\\]')
TOKEN_TAIL = re.compile(r'[^ \t\r\n,:\[\]{}"]*')
UNRESERVED_BYTES = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def create_error_list() -> ErrorList:
    return ErrorList(LIMITS["validationErrors"])


def is_object(value) -> bool:
    return isinstance(value, dict)


def in_string_set(values, value) -> bool:
    return isinstance(value, str) and value in values


def primitive_key(value):
    if isinstance(value, (str, int, float)) or value is None:
        return type_of(value), value
    return None


def read_file_within_limit(file) -> str:
    return read_input_within_limit(file, MAX_INPUT_BYTES)


def preflight_json_text(contents: str) -> None:
    containers: list[dict] = []
    root_state = "value"
    total_values = 0

    def fail(message: str):
        raise JsonStructureError(f"input {message}")

    def count_value() -> None:
        nonlocal total_values
        total_values += 1
        if total_values > LIMITS["preflightValues"]:
            fail(f"exceeds {LIMITS['preflightValues']} total value limit")

    def begin_value() -> None:
        nonlocal root_state
        container = containers[-1] if containers else None
        if container is None:
            if root_state != "value":
                fail("has malformed JSON structure")
            root_state = "end"
        elif container["type"] == "array":
            if container["state"] not in ("firstValueOrEnd", "value"):
                fail("has malformed JSON array structure")
            container["items"] += 1
            limit = MAX_UNITS if container["topLevel"] else LIMITS["collectionItems"]
            if container["items"] > limit:
                fail(f"exceeds {limit} top-level unit limit" if container["topLevel"] else f"exceeds {limit} item array limit")
            container["state"] = "commaOrEnd"
        else:
            if container["state"] != "value":
                fail("has malformed JSON object structure")
            container["state"] = "commaOrEnd"
        count_value()

    def begin_string() -> None:
        container = containers[-1] if containers else None
        if container is not None and container["type"] == "object" and container["state"] in ("firstKeyOrEnd", "key"):
            container["fields"] += 1
            if container["fields"] > LIMITS["objectFields"]:
                fail(f"exceeds {LIMITS['objectFields']} field object limit")
            container["state"] = "colon"
        else:
            begin_value()

    def begin_container(container_type: str) -> None:
        begin_value()
        if len(containers) >= LIMITS["nestingDepth"]:
            fail(f"exceeds nesting depth limit {LIMITS['nestingDepth']}")
        if container_type == "array":
            containers.append({"type": "array", "state": "firstValueOrEnd", "items": 0, "topLevel": len(containers) == 0})
        else:
            containers.append({"type": "object", "state": "firstKeyOrEnd", "fields": 0})

    def close_container(container_type: str) -> None:
        container = containers[-1] if containers else None
        if container is None or container["type"] != container_type:
            fail("has mismatched JSON containers")
        closable = ("firstValueOrEnd", "commaOrEnd") if container_type == "array" else ("firstKeyOrEnd", "commaOrEnd")
        if container["state"] not in closable:
            fail(f"has malformed JSON {container_type} structure")
        containers.pop()

    length = len(contents)
    index = 0
    in_string = False
    while index < length:
        if in_string:
            match = STRING_SPECIAL.search(contents, index)
            if match is None:
                index = length
                break
            if match.group() == "\\":
                index = match.start() + 2
            else:
                in_string = False
                index = match.start() + 1
            continue

        character = contents[index]
        if character in PREFLIGHT_WHITESPACE:
            index += 1
            continue
        if character == '"':
            begin_string()
            in_string = True
        elif character == "[":
            begin_container("array")
        elif character == "{":
            begin_container("object")
        elif character == "]":
            close_container("array")
        elif character == "}":
            close_container("object")
        elif character == ":":
            container = containers[-1] if containers else None
            if container is None or container["type"] != "object" or container["state"] != "colon":
                fail("has malformed JSON object structure")
            container["state"] = "value"
        elif character == ",":
            container = containers[-1] if containers else None
            if container is None or container["state"] != "commaOrEnd":
                fail("has malformed JSON collection structure")
            container["state"] = "value" if container["type"] == "array" else "key"
        else:
            begin_value()
            index = TOKEN_TAIL.match(contents, index + 1).end() - 1
        index += 1

    if in_string:
        fail("has an unterminated JSON string")
    if containers:
        fail("has truncated JSON structure")
    if root_state != "end":
        fail("has no JSON value")


def preflight_document(root) -> ErrorList:
    errors = create_error_list()
    stack = [(root, 0, "$")]
    visited = 0

    while stack:
        value, depth, location = stack.pop()
        visited += 1
        if visited > LIMITS["preflightValues"]:
            errors.push(f"$: exceeds {LIMITS['preflightValues']} total values")
            return errors
        if not isinstance(value, (dict, list)):
            continue
        if depth >= LIMITS["nestingDepth"]:
            errors.push(f"{location}: exceeds nesting depth limit {LIMITS['nestingDepth']}")
            return errors

        if isinstance(value, list):
            limit = MAX_UNITS if location == "$" else MAX_LIST_ITEMS
            if len(value) > limit:
                errors.push(f"{location}: exceeds {limit} entries")
                return errors
            for index in range(len(value) - 1, -1, -1):
                stack.append((value[index], depth + 1, f"{location}[{index}]"))
            continue

        keys = js_keys(value)
        if len(keys) > LIMITS["objectFields"]:
            errors.push(f"{location}: exceeds {LIMITS['objectFields']} object fields")
            return errors
        for index in range(len(keys) - 1, -1, -1):
            stack.append((value[keys[index]], depth + 1, f"{location}{{{index}}}"))

    return errors


def is_visible_text(value, max_length: int = MAX_TEXT_LENGTH) -> bool:
    if not isinstance(value, str):
        return False
    length = utf16_length(value)
    return 0 < length <= max_length and js_trim(value) == value and has_visible_prose(value)


def is_canonical_ref(value) -> bool:
    return (
        is_visible_text(value, 1024)
        and not has_path_forbidden_character(value)
        and unicodedata.normalize("NFC", value) == value
    )


def encode_canonical_ref(value) -> str:
    if not is_canonical_ref(value):
        raise TypeError("invalid canonical reference")
    return "".join(
        chr(byte) if byte in UNRESERVED_BYTES else f"%{byte:02X}"
        for byte in value.encode("utf-8")
    )


def canonical_coverage_id(refs) -> str:
    if not is_object(refs):
        raise TypeError("canonical_refs must be an object")
    fields = (*REF_FIELDS, "lifecycle") if "lifecycle" in refs else REF_FIELDS
    if len(refs) != len(fields) or any(field not in refs for field in fields):
        raise TypeError("canonical_refs has missing or unexpected fields")
    return "::".join(encode_canonical_ref(refs[field]) for field in fields)


def is_safe_agent_id(value) -> bool:
    return (
        isinstance(value, str)
        and AGENT_ID_PATTERN.fullmatch(value) is not None
        and WINDOWS_RESERVED_AGENT_ID.fullmatch(value) is None
    )


def is_owned_artifact_path(value, agent_id) -> bool:
    if not is_safe_agent_id(agent_id) or not is_safe_relative_path(value):
        return False
    prefix = f"agents/{agent_id}/artifacts/"
    return value.startswith(prefix) and len(value) > len(prefix)


def validate_string_array(value, location: str, errors: ErrorList, allow_empty: bool = True,
                          fingerprint: bool = False, path_value: bool = False) -> None:
    if not isinstance(value, list):
        errors.push(f"{location}: expected array")
        return
    if not allow_empty and len(value) == 0:
        errors.push(f"{location}: must not be empty")
    if len(value) > MAX_LIST_ITEMS:
        errors.push(f"{location}: exceeds {MAX_LIST_ITEMS} entries")
    seen: set[str] = set()
    for index, entry in enumerate(value[:MAX_LIST_ITEMS]):
        entry_location = f"{location}[{index}]"
        valid = is_safe_relative_path(entry) if path_value else is_visible_text(entry)
        if not valid:
            errors.push(f"{entry_location}: invalid {'repository-relative path' if path_value else 'text'}")
        if fingerprint and isinstance(entry, str) and FINGERPRINT_PATTERN.fullmatch(entry) is None:
            errors.push(f"{entry_location}: invalid fingerprint")
        if isinstance(entry, str) and entry in seen:
            errors.push(f"{entry_location}: duplicate entry")
        if isinstance(entry, str):
            seen.add(entry)


def validate_checks(value, location: str, errors: ErrorList) -> None:
    if not isinstance(value, list):
        errors.push(f"{location}: expected array")
        return
    if len(value) > MAX_LIST_ITEMS:
        errors.push(f"{location}: exceeds {MAX_LIST_ITEMS} entries")
    for index, check in enumerate(value[:MAX_LIST_ITEMS]):
        base = f"{location}[{index}]"
        if not is_object(check):
            errors.push(f"{base}: expected object")
            continue
        for field in ("agent_id", "reviewed_paths", "invariant", "method", "result", "artifact"):
            if field not in check:
                errors.push(f"{base}: missing required field {safe_quote(field)}")
        agent_id = js_get(check, "agent_id")
        method = js_get(check, "method")
        artifact = js_get(check, "artifact")
        if not is_safe_agent_id(agent_id):
            errors.push(f"{base}.agent_id: expected a canonical lowercase agent ID")
        validate_string_array(js_get(check, "reviewed_paths"), f"{base}.reviewed_paths", errors,
                              allow_empty=False, path_value=True)
        if not is_visible_text(js_get(check, "invariant")):
            errors.push(f"{base}.invariant: invalid text")
        if method != "source" and method != "local":
            errors.push(f'{base}.method: expected "source" or "local"')
        if not is_visible_text(js_get(check, "result")):
            errors.push(f"{base}.result: invalid text")
        if method == "source" and artifact is not None:
            errors.push(f"{base}.artifact: source-only check must use null")
        elif method == "local":
            if not is_owned_artifact_path(artifact, agent_id):
                owner = agent_id if is_safe_agent_id(agent_id) else "<agent-id>"
                errors.push(f"{base}.artifact: local check requires an artifact owned by agent {safe_quote(owner)}")
        elif method != "source" and method != "local" and artifact is not None and not is_safe_relative_path(artifact):
            errors.push(f"{base}.artifact: expected null or a safe output-relative path")


def validate_reviewed_path_ownership(unit: dict, base: str, errors: ErrorList) -> None:
    reviewed_paths = js_get(unit, "reviewed_paths")
    local_checks = js_get(unit, "local_checks")
    if not isinstance(reviewed_paths, list) or not isinstance(local_checks, list):
        return
    aggregate_paths = dict.fromkeys(value for value in reviewed_paths if isinstance(value, str))
    owned_paths: dict[str, None] = {}
    for check in local_checks:
        check_paths = js_get(check, "reviewed_paths")
        if not is_object(check) or not isinstance(check_paths, list):
            continue
        for reviewed_path in check_paths:
            if isinstance(reviewed_path, str):
                owned_paths[reviewed_path] = None
    for reviewed_path in aggregate_paths:
        if reviewed_path not in owned_paths:
            errors.push(f"{base}.reviewed_paths: {safe_quote(reviewed_path)} has no check owner")
    for reviewed_path in owned_paths:
        if reviewed_path not in aggregate_paths:
            errors.push(f"{base}.local_checks: owned path {safe_quote(reviewed_path)} is absent from aggregate reviewed_paths")


def validate_excluded_blocks(value, location: str, errors: ErrorList) -> None:
    if not isinstance(value, list):
        errors.push(f"{location}: expected array")
        return
    if len(value) > MAX_LIST_ITEMS:
        errors.push(f"{location}: exceeds {MAX_LIST_ITEMS} entries")
    seen: set[str] = set()
    for index, entry in enumerate(value[:MAX_LIST_ITEMS]):
        base = f"{location}[{index}]"
        if not is_object(entry):
            errors.push(f"{base}: expected object")
            continue
        block = js_get(entry, "block")
        if not is_visible_text(block):
            errors.push(f"{base}.block: invalid text")
        if not is_visible_text(js_get(entry, "reason")):
            errors.push(f"{base}.reason: invalid text")
        if isinstance(block, str) and block in seen:
            errors.push(f"{base}.block: duplicate entry")
        if isinstance(block, str):
            seen.add(block)


def semantic_key(unit: dict) -> str:
    return json.dumps([
        unit["surface"],
        unit["boundary"],
        unit["subsystem"],
        unit["attack_class"],
        unit["lifecycle"] if "lifecycle" in unit else None,
    ], ensure_ascii=False)


def has_valid_semantic_fields(unit: dict) -> bool:
    return all(is_visible_text(js_get(unit, field)) for field in REF_FIELDS) and (
        "lifecycle" not in unit or is_visible_text(unit["lifecycle"])
    )


def require_empty_array(unit: dict, field: str, base: str, errors: ErrorList) -> None:
    value = js_get(unit, field)
    if isinstance(value, list) and len(value) > 0:
        errors.push(f"{base}.{field}: unit with status {safe_quote(js_get(unit, 'status'))} must keep this array empty")


def require_nonempty_array(unit: dict, field: str, base: str, errors: ErrorList) -> None:
    value = js_get(unit, field)
    if not isinstance(value, list) or len(value) == 0:
        errors.push(f"{base}.{field}: unit with status {safe_quote(js_get(unit, 'status'))} requires entries")


def validate_state_invariants(unit: dict, base: str, errors: ErrorList) -> None:
    status = js_get(unit, "status")
    agent_id = js_get(unit, "agent_id")

    def empty_evidence() -> None:
        require_empty_array(unit, "reviewed_paths", base, errors)
        require_empty_array(unit, "local_checks", base, errors)

    def require_owner() -> None:
        if not is_safe_agent_id(agent_id):
            errors.push(f"{base}.agent_id: unit with status {safe_quote(status)} requires a canonical lowercase agent ID")

    if status != "candidate":
        require_empty_array(unit, "result_fingerprints", base, errors)

    if status == "planned":
        if agent_id is not None:
            errors.push(f"{base}.agent_id: planned unit must be unassigned")
        empty_evidence()
        require_empty_array(unit, "unresolved", base, errors)
    elif status in ("not_applicable", "out_of_scope", "deferred"):
        if agent_id is not None:
            errors.push(f"{base}.agent_id: unit with status {safe_quote(status)} must be unassigned")
        empty_evidence()
        require_nonempty_array(unit, "unresolved", base, errors)
    elif status == "in_progress":
        require_owner()
        empty_evidence()
        require_empty_array(unit, "unresolved", base, errors)
    elif status == "blocked":
        require_owner()
        require_nonempty_array(unit, "reviewed_paths", base, errors)
        require_nonempty_array(unit, "local_checks", base, errors)
        require_nonempty_array(unit, "unresolved", base, errors)
    elif status == "covered":
        require_owner()
        require_nonempty_array(unit, "reviewed_paths", base, errors)
        require_nonempty_array(unit, "local_checks", base, errors)
        require_empty_array(unit, "unresolved", base, errors)
    elif status == "candidate":
        require_owner()
        require_nonempty_array(unit, "reviewed_paths", base, errors)
        require_nonempty_array(unit, "local_checks", base, errors)
        require_nonempty_array(unit, "result_fingerprints", base, errors)


def validate_attempts(value, unit: dict, base: str, errors: ErrorList) -> None:
    if not isinstance(value, list):
        errors.push(f"{base}.attempts: expected array")
        return
    if len(value) > MAX_LIST_ITEMS:
        errors.push(f"{base}.attempts: exceeds {MAX_LIST_ITEMS} entries")

    prior_owners: set[str] = set()
    prior_artifacts: set[str] = set()
    previous_wave = 0
    unit_wave = js_get(unit, "wave")
    for index, attempt in enumerate(value[:MAX_LIST_ITEMS]):
        attempt_base = f"{base}.attempts[{index}]"
        if not is_object(attempt):
            errors.push(f"{attempt_base}: expected object")
            continue
        for field in ATTEMPT_FIELDS:
            if field not in attempt:
                errors.push(f"{attempt_base}: missing required field {safe_quote(field)}")
        wave = js_get(attempt, "wave")
        if not is_js_integer(wave) or wave < 1:
            errors.push(f"{attempt_base}.wave: expected a positive integer")
        else:
            if wave <= previous_wave:
                errors.push(f"{attempt_base}.wave: archived attempt waves must be strictly increasing")
            if is_js_integer(unit_wave) and wave >= unit_wave:
                errors.push(f"{attempt_base}.wave: archived attempt wave must precede current wave {safe_quote(unit_wave)}")
            previous_wave = wave
        if not in_string_set(ATTEMPT_STATUSES, js_get(attempt, "status")):
            errors.push(f'{attempt_base}.status: expected "covered", "candidate", or "blocked"')
        agent_id = js_get(attempt, "agent_id")
        has_fresh_owner = False
        if not is_safe_agent_id(agent_id):
            errors.push(f"{attempt_base}.agent_id: archived attempt requires a canonical lowercase agent ID")
        elif agent_id in prior_owners:
            errors.push(f"{attempt_base}.agent_id: assignment owner must be fresh for each attempt")
        else:
            has_fresh_owner = True
        validate_string_array(js_get(attempt, "reviewed_paths"), f"{attempt_base}.reviewed_paths", errors, path_value=True)
        validate_checks(js_get(attempt, "local_checks"), f"{attempt_base}.local_checks", errors)
        validate_reviewed_path_ownership(attempt, attempt_base, errors)
        validate_string_array(js_get(attempt, "result_fingerprints"), f"{attempt_base}.result_fingerprints", errors,
                              fingerprint=True)
        validate_string_array(js_get(attempt, "unresolved"), f"{attempt_base}.unresolved", errors)
        if not is_visible_text(js_get(attempt, "reassignment_reason")):
            errors.push(f"{attempt_base}.reassignment_reason: invalid text")
        validate_state_invariants(attempt, attempt_base, errors)

        local_checks = js_get(attempt, "local_checks")
        if isinstance(local_checks, list):
            for check_index, check in enumerate(local_checks):
                if not is_object(check):
                    continue
                artifact = js_get(check, "artifact")
                if in_string_set(prior_owners, js_get(check, "agent_id")):
                    errors.push(
                        f"{attempt_base}.local_checks[{check_index}].agent_id: "
                        "prior assignment owner evidence must remain in its earlier attempt")
                if isinstance(artifact, str) and artifact in prior_artifacts:
                    errors.push(
                        f"{attempt_base}.local_checks[{check_index}].artifact: "
                        "artifact from an earlier attempt cannot be reused")
                if js_get(check, "method") == "local" and isinstance(artifact, str):
                    prior_artifacts.add(artifact)
        if has_fresh_owner:
            prior_owners.add(agent_id)

    unit_agent_id = js_get(unit, "agent_id")
    if is_safe_agent_id(unit_agent_id) and unit_agent_id in prior_owners:
        errors.push(f"{base}.agent_id: current assignment owner must be fresh after reassignment")
    unit_checks = js_get(unit, "local_checks")
    if isinstance(unit_checks, list):
        for index, check in enumerate(unit_checks):
            if not is_object(check):
                continue
            artifact = js_get(check, "artifact")
            if in_string_set(prior_owners, js_get(check, "agent_id")):
                errors.push(
                    f"{base}.local_checks[{index}].agent_id: "
                    "prior assignment owner evidence must remain in its archived attempt")
            if isinstance(artifact, str) and artifact in prior_artifacts:
                errors.push(f"{base}.local_checks[{index}].artifact: artifact from an archived attempt cannot be reused")


def collect_unit_errors(unit, index: int) -> list:
    errors = create_error_list()
    base = f"$[{index}]"
    if not is_object(unit):
        return [f"{base}: expected object"]

    for field in REQUIRED_FIELDS:
        if field not in unit:
            errors.push(f"{base}: missing required field {safe_quote(field)}")
    for field in REF_FIELDS:
        if not is_visible_text(js_get(unit, field)):
            errors.push(f"{base}.{field}: invalid text")
    if "lifecycle" in unit and not is_visible_text(unit["lifecycle"]):
        errors.push(f"{base}.lifecycle: invalid text")

    expected_id = None
    refs = js_get(unit, "canonical_refs")
    if not is_object(refs):
        errors.push(f"{base}.canonical_refs: expected object")
    else:
        expected_fields = (*REF_FIELDS, "lifecycle") if "lifecycle" in refs else REF_FIELDS
        for field in expected_fields:
            if field not in refs:
                errors.push(f"{base}.canonical_refs: missing required field {safe_quote(field)}")
            elif not is_canonical_ref(refs[field]):
                errors.push(f"{base}.canonical_refs.{field}: invalid canonical reference")
        if any(field not in expected_fields for field in refs):
            errors.push(f"{base}.canonical_refs: contains unexpected fields")
        if ("lifecycle" in unit) != ("lifecycle" in refs):
            errors.push(f"{base}: lifecycle and canonical_refs.lifecycle must appear together")
        try:
            expected_id = canonical_coverage_id(refs)
        except TypeError:
            pass
    coverage_id = js_get(unit, "coverage_id")
    if not is_visible_text(coverage_id, 65536):
        errors.push(f"{base}.coverage_id: invalid text")
    elif expected_id is not None and coverage_id != expected_id:
        errors.push(f"{base}.coverage_id: expected canonical ID {safe_quote(expected_id)}")

    validate_string_array(js_get(unit, "starting_paths"), f"{base}.starting_paths", errors,
                          allow_empty=False, path_value=True)
    ordinary_block = js_get(unit, "ordinary_attack_class_block")
    if ordinary_block is not None and not is_visible_text(ordinary_block):
        errors.push(f"{base}.ordinary_attack_class_block: expected null or non-empty text")
    selected_blocks = js_get(unit, "selected_companion_blocks")
    excluded_blocks = js_get(unit, "excluded_blocks")
    validate_string_array(selected_blocks, f"{base}.selected_companion_blocks", errors)
    validate_excluded_blocks(excluded_blocks, f"{base}.excluded_blocks", errors)
    if isinstance(selected_blocks, list) and isinstance(excluded_blocks, list):
        selected = {key for key in map(primitive_key, selected_blocks) if key is not None}
        for block_index, entry in enumerate(excluded_blocks):
            if is_object(entry):
                key = primitive_key(js_get(entry, "block"))
                if key is not None and key in selected:
                    errors.push(f"{base}.excluded_blocks[{block_index}].block: block is also selected")

    prior_status = js_get(unit, "prior_status")
    status = js_get(unit, "status")
    wave = js_get(unit, "wave")
    agent_id = js_get(unit, "agent_id")
    if not in_string_set(PRIOR_STATUSES, prior_status):
        errors.push(f"{base}.prior_status: invalid value {safe_quote(prior_status)}")
    if not in_string_set(STATUSES, status):
        errors.push(f"{base}.status: invalid value {safe_quote(status)}")
    if not is_js_integer(wave) or wave < 1:
        errors.push(f"{base}.wave: expected a positive integer")
    if agent_id is not None and not is_safe_agent_id(agent_id):
        errors.push(f"{base}.agent_id: expected null or a safe agent ID")

    validate_attempts(js_get(unit, "attempts"), unit, base, errors)
    validate_string_array(js_get(unit, "reviewed_paths"), f"{base}.reviewed_paths", errors, path_value=True)
    validate_checks(js_get(unit, "local_checks"), f"{base}.local_checks", errors)
    validate_reviewed_path_ownership(unit, base, errors)
    validate_string_array(js_get(unit, "result_fingerprints"), f"{base}.result_fingerprints", errors, fingerprint=True)
    validate_string_array(js_get(unit, "unresolved"), f"{base}.unresolved", errors)

    validate_state_invariants(unit, base, errors)

    return errors


def validate_document(ledger) -> ErrorList:
    errors = create_error_list()
    if not isinstance(ledger, list):
        errors.push("$: expected a top-level array")
        return errors
    if len(ledger) > MAX_UNITS:
        errors.push(f"$: exceeds {MAX_UNITS} coverage units")
        return errors

    errors.push(*preflight_document(ledger))
    if errors:
        return errors

    ids: dict[str, tuple[int, str | None]] = {}
    semantics: dict[str, tuple[str, int]] = {}
    previous_id = None
    for index, unit in enumerate(ledger):
        if len(errors) >= LIMITS["validationErrors"]:
            break
        errors.push(*collect_unit_errors(unit, index))
        if len(errors) >= LIMITS["validationErrors"]:
            break
        coverage_id = js_get(unit, "coverage_id")
        if not is_object(unit) or not isinstance(coverage_id, str):
            continue

        key = semantic_key(unit) if has_valid_semantic_fields(unit) else None
        if coverage_id in ids:
            previous_index, previous_key = ids[coverage_id]
            qualifier = (
                "canonical identity collision with different semantic fields"
                if key is not None and previous_key is not None and previous_key != key
                else "duplicate coverage ID"
            )
            errors.push(f"$[{index}].coverage_id: {qualifier} at $[{previous_index}]")
        else:
            ids[coverage_id] = (index, key)
        if key is not None and key in semantics and semantics[key][0] != coverage_id:
            previous_coverage_id, previous_index = semantics[key]
            errors.push(
                f"$[{index}].canonical_refs: semantic tuple already uses coverage ID "
                f"{safe_quote(previous_coverage_id)} at $[{previous_index}]")
        elif key is not None:
            semantics[key] = (coverage_id, index)
        if previous_id is not None and utf16_key(previous_id) > utf16_key(coverage_id):
            errors.push(f"$[{index}].coverage_id: units must be sorted lexicographically")
        previous_id = coverage_id
    return errors


def run(file) -> int:
    if not file:
        print("Usage: python3 validate_coverage_ledger.py <path-to-coverage-ledger.json>", file=sys.stderr)
        return 1

    try:
        contents = read_file_within_limit(file)
    except Exception as error:
        reason = str(error) if isinstance(error, SafeInputError) else "input could not be opened or read safely"
        print(f"Failed to read coverage ledger: {reason}", file=sys.stderr)
        return 1

    try:
        preflight_json_text(contents)
    except Exception as error:
        reason = str(error) if isinstance(error, JsonStructureError) else "invalid JSON structure"
        print(f"Failed to parse coverage ledger: {reason}", file=sys.stderr)
        return 1
    try:
        ledger = parse_json_text(contents)
    except Exception:
        print("Failed to parse coverage ledger: invalid JSON syntax", file=sys.stderr)
        return 1

    try:
        errors = validate_document(ledger)
    except Exception:
        print("Failed to validate coverage ledger: unexpected validation error", file=sys.stderr)
        return 1
    for message in errors:
        print("ERROR:", message, file=sys.stderr)
    if errors:
        cap = (
            f"; output capped at {LIMITS['validationErrors']}"
            if len(errors) == LIMITS["validationErrors"]
            else ""
        )
        print(f"FAIL: {len(errors)} validation error(s){cap}", file=sys.stderr)
        return 1
    print(f"PASS: {len(ledger)} coverage units valid")
    return 0


def main(argv=None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    try:
        return run(arguments[0] if arguments else None)
    except Exception:
        print("Failed to validate coverage ledger: unexpected validation error", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
