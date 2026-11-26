#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_common import (
    JS_WHITESPACE,
    UNDEFINED,
    WINDOWS_RESERVED_COMPONENT,
    ErrorList,
    JsonStructureError,
    SafeInputError,
    code_point_length,
    escape_unsafe_diagnostic_characters,
    has_valid_unicode_scalar_values,
    has_visible_content,
    has_visible_prose,
    is_finite_number,
    is_js_integer,
    is_number,
    is_safe_relative_path,
    js_get,
    js_json_string,
    js_keys,
    js_number_text,
    js_truthy,
    parse_json_text,
    read_file_within_limit,
    safe_quote,
    type_of,
    utf16_key,
    utf8_length,
)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "references" / "report-schema.json"
SUPPORTED_TYPES = frozenset(["object", "array", "string", "integer", "number", "boolean", "null"])
SUPPORTED_KEYWORDS = frozenset([
    "$comment",
    "additionalProperties",
    "const",
    "description",
    "enum",
    "items",
    "minimum",
    "minItems",
    "minLength",
    "oneOf",
    "pattern",
    "properties",
    "required",
    "type",
    "uniqueItems",
    "visibleContent",
])
SEVERITY_RANK = MappingProxyType({
    "informational": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
})
LIMITS = MappingProxyType({
    "inputBytes": 5 * 1024 * 1024,
    "nestingDepth": 64,
    "arrayItems": 1000,
    "canonicalKeyBytes": 1024 * 1024,
    "uniqueSetBytes": 5 * 1024 * 1024,
    "validationErrors": 100,
})
PROPERTY_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
is_safe_relative_source_path = is_safe_relative_path


class CanonicalKeyError(ValueError):
    pass


def create_error_list() -> ErrorList:
    return ErrorList(LIMITS["validationErrors"])


def property_path(base: str, key: str) -> str:
    return f"{base}.{key}" if PROPERTY_NAME.fullmatch(key) else f"{base}[{safe_quote(key)}]"


def is_container(value) -> bool:
    return isinstance(value, (dict, list))


def is_rank(value) -> bool:
    return isinstance(value, str) and value in SEVERITY_RANK


def to_python_pattern(pattern: str) -> str:
    if pattern.endswith("$"):
        prefix = pattern[:-1]
        if (len(prefix) - len(prefix.rstrip("\\"))) % 2 == 0:
            return prefix + r"\Z"
    return pattern


@lru_cache(maxsize=64)
def compile_pattern(pattern: str):
    return re.compile(to_python_pattern(pattern))


def deep_equal(left, right) -> bool:
    if left is right:
        return True
    left_type = type_of(left)
    if left_type != type_of(right):
        return False
    if left_type == "array":
        return len(left) == len(right) and all(deep_equal(value, right[index]) for index, value in enumerate(left))
    if left_type == "object":
        return len(left) == len(right) and all(key in right and deep_equal(left[key], right[key]) for key in left)
    return left == right


def canonical_key(value) -> tuple[str, int]:
    chunks: list[str] = []
    total = 0
    limit = LIMITS["canonicalKeyBytes"]

    def append(chunk: str) -> None:
        nonlocal total
        total += utf8_length(chunk)
        if total > limit:
            raise CanonicalKeyError(f"canonical key exceeds {limit} byte limit")
        chunks.append(chunk)

    def encode(item) -> None:
        item_type = type_of(item)
        if item_type == "null":
            append("null")
        elif item_type == "string":
            append(f"string:{js_json_string(item)}")
        elif item_type == "number":
            append(f"number:{js_number_text(item)}")
        elif item_type == "boolean":
            append(f"boolean:{'true' if item else 'false'}")
        elif item_type == "array":
            append("array:[")
            for index, entry in enumerate(item):
                if index > 0:
                    append(",")
                encode(entry)
            append("]")
        elif item_type == "object":
            append("object:{")
            for index, key in enumerate(sorted(item, key=utf16_key)):
                if index > 0:
                    append(",")
                append(js_json_string(key))
                append(":")
                encode(item[key])
            append("}")
        else:
            append(f"{item_type}:{item}")

    encode(value)
    return "".join(chunks), total


def collect_data_limit_errors(value, location: str = "$data") -> list:
    stack = [(value, location, 1 if is_container(value) else 0)]
    seen: set[int] = set()

    while stack:
        current, current_location, depth = stack.pop()
        if not is_container(current):
            continue
        if depth > LIMITS["nestingDepth"]:
            return [escape_unsafe_diagnostic_characters(
                f"{current_location}: exceeds {LIMITS['nestingDepth']} level nesting depth limit")]
        if id(current) in seen:
            return [escape_unsafe_diagnostic_characters(
                f"{current_location}: input must not contain repeated or cyclic object references")]
        seen.add(id(current))

        if isinstance(current, list):
            if len(current) > LIMITS["arrayItems"]:
                return [escape_unsafe_diagnostic_characters(
                    f"{current_location}: exceeds {LIMITS['arrayItems']} item array limit")]
            for index in range(len(current) - 1, -1, -1):
                child = current[index]
                if is_container(child):
                    stack.append((child, f"{current_location}[{index}]", depth + 1))
        else:
            for key in reversed(js_keys(current)):
                child = current[key]
                if is_container(child):
                    stack.append((child, property_path(current_location, key), depth + 1))

    return []


def collect_schema_errors(schema, location: str = "schema") -> ErrorList:
    errors = create_error_list()

    def check(node, p: str) -> None:
        if not isinstance(node, dict):
            errors.push(f"{p}: schema must be an object")
            return

        for key in js_keys(node):
            if key not in SUPPORTED_KEYWORDS:
                errors.push(f"{p}: unsupported schema keyword {safe_quote(key)}")

        if "$comment" in node and not isinstance(node["$comment"], str):
            errors.push(f"{p}.$comment: expected string")
        if "description" in node and not isinstance(node["description"], str):
            errors.push(f"{p}.description: expected string")
        if "type" in node and not (isinstance(node["type"], str) and node["type"] in SUPPORTED_TYPES):
            errors.push(f"{p}.type: unsupported type {safe_quote(node['type'])}")
        if "properties" in node:
            if not isinstance(node["properties"], dict):
                errors.push(f"{p}.properties: expected object")
            else:
                for key in js_keys(node["properties"]):
                    check(node["properties"][key], property_path(f"{p}.properties", key))
        if "required" in node:
            required = node["required"]
            if not isinstance(required, list) or any(not isinstance(key, str) for key in required):
                errors.push(f"{p}.required: expected an array of strings")
            elif len(set(required)) != len(required):
                errors.push(f"{p}.required: entries must be unique")
        if "additionalProperties" in node and not isinstance(node["additionalProperties"], bool):
            errors.push(f"{p}.additionalProperties: only boolean values are supported")
        if "enum" in node:
            if not isinstance(node["enum"], list) or len(node["enum"]) == 0:
                errors.push(f"{p}.enum: expected a non-empty array")
            else:
                seen: set[str] = set()
                for value in node["enum"]:
                    try:
                        key = canonical_key(value)[0]
                    except CanonicalKeyError as error:
                        errors.push(f"{p}.enum: {error}")
                        break
                    if key in seen:
                        errors.push(f"{p}.enum: entries must be unique")
                        break
                    seen.add(key)
        if "items" in node:
            check(node["items"], f"{p}.items")
        for keyword in ("minItems", "minLength"):
            if keyword in node and (not is_js_integer(node[keyword]) or node[keyword] < 0):
                errors.push(f"{p}.{keyword}: expected a non-negative integer")
        if "minimum" in node and not is_finite_number(node["minimum"]):
            errors.push(f"{p}.minimum: expected a finite number")
        if "pattern" in node:
            if not isinstance(node["pattern"], str):
                errors.push(f"{p}.pattern: expected string")
            else:
                try:
                    compile_pattern(node["pattern"])
                except re.error:
                    errors.push(f"{p}.pattern: invalid regular expression")
        if "uniqueItems" in node and not isinstance(node["uniqueItems"], bool):
            errors.push(f"{p}.uniqueItems: expected boolean")
        if "visibleContent" in node:
            if not isinstance(node["visibleContent"], bool):
                errors.push(f"{p}.visibleContent: expected boolean")
            elif node["visibleContent"] is True and js_get(node, "type") != "string":
                errors.push(f'{p}.visibleContent: requires type "string"')
        if "oneOf" in node:
            if not isinstance(node["oneOf"], list) or len(node["oneOf"]) == 0:
                errors.push(f"{p}.oneOf: expected a non-empty array")
            else:
                for index, branch in enumerate(node["oneOf"]):
                    check(branch, f"{p}.oneOf[{index}]")

    check(schema, location)
    return errors


def find_discriminator(schema):
    properties = js_get(schema, "properties")
    if not isinstance(properties, dict):
        return None
    for key in js_keys(properties):
        sub_schema = properties[key]
        if isinstance(sub_schema, dict) and "const" in sub_schema:
            return key, sub_schema["const"]
    return None


def validate(value, schema: dict, p: str, errors: ErrorList) -> None:
    if len(errors) >= LIMITS["validationErrors"]:
        return
    if "oneOf" in schema:
        results = [collect_unchecked(value, branch, p) for branch in schema["oneOf"]]
        passing = [index for index, branch_errors in enumerate(results) if len(branch_errors) == 0]
        if len(passing) != 1:
            errors.push(f"{p}: must match exactly one schema in oneOf; matched {len(passing)}")
            if len(passing) == 0 and isinstance(value, dict):
                matching = []
                for index, branch in enumerate(schema["oneOf"]):
                    discriminator = find_discriminator(branch)
                    if discriminator and discriminator[0] in value and deep_equal(value[discriminator[0]], discriminator[1]):
                        matching.append(index)
                if len(matching) == 1:
                    errors.push(*results[matching[0]])

    if "const" in schema and not deep_equal(value, schema["const"]):
        errors.push(f"{p}: must equal {safe_quote(schema['const'])}, got {safe_quote(value)}")
    if "enum" in schema and not any(deep_equal(value, allowed) for allowed in schema["enum"]):
        allowed_text = ", ".join(safe_quote(allowed) for allowed in schema["enum"])
        errors.push(f"{p}: invalid value {safe_quote(value)} (expected one of {allowed_text})")

    value_type = type_of(value)
    if "type" in schema and value_type != schema["type"] and not (
        schema["type"] == "integer" and value_type == "number" and is_js_integer(value)
    ):
        errors.push(f"{p}: expected {schema['type']}, got {value_type}")
        return

    if value_type == "object":
        for required in schema.get("required", []):
            if required not in value:
                errors.push(f"{p}: missing required field {safe_quote(required)}")
        properties = schema.get("properties")
        for key in js_keys(value):
            if properties is not None and key in properties:
                validate(value[key], properties[key], property_path(p, key), errors)
            elif schema.get("additionalProperties", UNDEFINED) is False:
                errors.push(f"{p}: unexpected field {safe_quote(key)}")

    if value_type == "array":
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.push(f"{p}: must have at least {js_number_text(schema['minItems'])} item(s), got {len(value)}")
        if schema.get("uniqueItems") is True:
            seen: set[str] = set()
            set_bytes = 0
            for index, item in enumerate(value):
                try:
                    key, key_bytes = canonical_key(item)
                except CanonicalKeyError as error:
                    errors.push(f"{p}[{index}]: {error}")
                    break
                if key in seen:
                    errors.push(f"{p}: items must be unique; duplicate at index {index}")
                    continue
                set_bytes += key_bytes
                if set_bytes > LIMITS["uniqueSetBytes"]:
                    errors.push(f"{p}: canonical uniqueness set exceeds {LIMITS['uniqueSetBytes']} byte limit")
                    break
                seen.add(key)
        if "items" in schema:
            for index, item in enumerate(value):
                validate(item, schema["items"], f"{p}[{index}]", errors)

    if value_type == "string":
        if "minLength" in schema and code_point_length(value) < schema["minLength"]:
            errors.push(f"{p}: must have at least {js_number_text(schema['minLength'])} character(s)")
        if schema.get("visibleContent") is True:
            if not has_valid_unicode_scalar_values(value):
                errors.push(f"{p}: must contain only valid Unicode scalar values")
            elif not has_visible_content(value):
                errors.push(f"{p}: must contain a visible character")
        if "pattern" in schema and not compile_pattern(schema["pattern"]).search(value):
            errors.push(f"{p}: must match pattern {js_json_string(schema['pattern'])}")

    if is_number(value) and "minimum" in schema and value < schema["minimum"]:
        errors.push(f"{p}: must be at least {js_number_text(schema['minimum'])}, got {js_number_text(value)}")


def collect_unchecked(value, schema: dict, p: str) -> ErrorList:
    errors = create_error_list()
    validate(value, schema, p, errors)
    return errors


def collect(value, schema: dict, p: str = "$data") -> list:
    limit_errors = collect_data_limit_errors(value, p)
    if limit_errors:
        return limit_errors
    return collect_unchecked(value, schema, p)


def kind_of(entry):
    return js_get(entry, "kind") if js_truthy(entry) else entry


def collect_finding_semantic_errors(findings) -> ErrorList:
    errors = create_error_list()
    if not isinstance(findings, list):
        return errors

    fingerprints: dict[str, int] = {}
    previous_fingerprint = None
    for index, finding in enumerate(findings):
        if len(errors) >= LIMITS["validationErrors"]:
            continue
        if not isinstance(finding, dict):
            continue
        base = f"$[{index}]"

        fingerprint = finding.get("fingerprint")
        if isinstance(fingerprint, str):
            if fingerprint in fingerprints:
                errors.push(f"{base}.fingerprint: duplicate of $[{fingerprints[fingerprint]}].fingerprint")
            else:
                fingerprints[fingerprint] = index
            if previous_fingerprint is not None and utf16_key(previous_fingerprint) > utf16_key(fingerprint):
                errors.push(f"{base}.fingerprint: findings must be sorted lexicographically")
            previous_fingerprint = fingerprint

        for field in ("trace", "evidence"):
            entries = finding.get(field)
            if not isinstance(entries, list):
                continue
            for entry_index, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    continue
                if "line" in entry and (not is_js_integer(entry["line"]) or entry["line"] < 1):
                    errors.push(f"{base}.{field}[{entry_index}].line: must be a positive integer")
                if "file" in entry and not is_safe_relative_source_path(entry["file"]):
                    errors.push(f"{base}.{field}[{entry_index}].file: must be a safe repository-relative source path")

        remediation = finding.get("remediation")
        code_changes = js_get(remediation, "code_changes") if js_truthy(remediation) else UNDEFINED
        if isinstance(code_changes, list):
            for change_index, change in enumerate(code_changes):
                if isinstance(change, dict) and "file_name" in change and not is_safe_relative_source_path(change["file_name"]):
                    errors.push(
                        f"{base}.remediation.code_changes[{change_index}].file_name: "
                        "must be a safe repository-relative source path")

        trace = finding.get("trace")
        if isinstance(trace, list) and len(trace) == 1:
            kind = kind_of(trace[0])
            if kind != "entrypoint" and kind != "sink":
                errors.push(f'{base}.trace[0].kind: a one-line trace must be "entrypoint" or "sink"')
        elif isinstance(trace, list) and len(trace) > 1:
            last = len(trace) - 1
            if js_truthy(trace[0]) and js_get(trace[0], "kind") != "entrypoint":
                errors.push(f'{base}.trace[0].kind: must be "entrypoint", got {safe_quote(js_get(trace[0], "kind"))}')
            if js_truthy(trace[last]) and js_get(trace[last], "kind") != "sink":
                errors.push(f'{base}.trace[{last}].kind: must be "sink", got {safe_quote(js_get(trace[last], "kind"))}')
            for trace_index in range(1, last):
                entry = trace[trace_index]
                if js_truthy(entry) and js_get(entry, "kind") != "propagation":
                    errors.push(
                        f'{base}.trace[{trace_index}].kind: must be "propagation", '
                        f'got {safe_quote(js_get(entry, "kind"))}')

        verdict = finding.get("verdict")
        if verdict == "confirmed":
            for forbidden in ("claimed_root_cause", "blockers", "validation_plan", "reason"):
                if forbidden in finding:
                    errors.push(f"{base}: confirmed finding must not contain {safe_quote(forbidden)}")
            execution = finding.get("execution")
            observed = js_get(execution, "observed_result")
            if not js_truthy(execution) or not is_container(execution) or not isinstance(observed, str) or not has_visible_prose(observed):
                errors.push(f"{base}: confirmed finding requires a visible execution observed_result")
            strategy = js_get(remediation, "strategy")
            if not js_truthy(remediation) or not is_container(remediation) or not isinstance(strategy, str) or not has_visible_prose(strategy):
                errors.push(f"{base}: confirmed finding requires visible remediation")
            severity = finding.get("severity", UNDEFINED)
            overall = js_get(severity, "overall_severity") if js_truthy(severity) else severity
            impact_block = js_get(severity, "impact") if js_truthy(severity) else severity
            impact = js_get(impact_block, "score") if js_truthy(impact_block) else impact_block
            if is_rank(overall) and is_rank(impact) and SEVERITY_RANK[overall] > SEVERITY_RANK[impact]:
                errors.push(f"{base}.severity.overall_severity: cannot exceed demonstrated impact {safe_quote(impact)}")
        elif verdict == "needs_validation":
            if "severity" in finding:
                errors.push(f'{base}: needs_validation finding must not contain "severity"')
            for forbidden in ("execution", "remediation", "reason", "root_cause"):
                if forbidden in finding:
                    errors.push(f"{base}: needs_validation finding must not contain {safe_quote(forbidden)}")
            plan = finding.get("validation_plan", UNDEFINED)
            local = js_get(plan, "local") if js_truthy(plan) else UNDEFINED
            deployment = js_get(plan, "deployment") if js_truthy(plan) else UNDEFINED
            has_local_plan = isinstance(local, str) and has_visible_prose(local)
            has_deployment_plan = isinstance(deployment, str) and has_visible_prose(deployment)
            if not has_local_plan and not has_deployment_plan:
                errors.push(f"{base}.validation_plan: requires at least one visible local or deployment plan")
        elif verdict == "rejected":
            for forbidden in ("severity", "execution", "remediation", "blockers", "validation_plan", "root_cause"):
                if forbidden in finding:
                    errors.push(f"{base}: rejected finding must not contain {safe_quote(forbidden)}")

    return errors


def validate_document(findings, schema) -> list:
    schema_errors = collect_schema_errors(schema)
    if schema_errors:
        return schema_errors
    limit_errors = collect_data_limit_errors(findings, "$")
    if limit_errors:
        return limit_errors
    errors = collect_unchecked(findings, schema, "$")
    if len(errors) < LIMITS["validationErrors"]:
        errors.push(*collect_finding_semantic_errors(findings))
    return errors


def load_schema(schema_path: Path = SCHEMA_PATH):
    schema = parse_json_text(Path(schema_path).read_text(encoding="utf-8"))
    errors = collect_schema_errors(schema)
    if errors:
        raise ValueError("unsupported or invalid report schema:\n" + "\n".join(errors))
    return schema


def enforce_json_text_limits(contents: str) -> None:
    containers: list[list] = []
    in_string = False
    escaped = False

    def mark_array_item() -> None:
        if not containers:
            return
        container = containers[-1]
        if container[0] != "array" or not container[1]:
            return
        container[1] = False
        container[2] += 1
        if container[2] > LIMITS["arrayItems"]:
            raise JsonStructureError(f"input exceeds {LIMITS['arrayItems']} item array limit")

    for character in contents:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue

        if character == '"':
            mark_array_item()
            in_string = True
        elif character in "[{":
            mark_array_item()
            if len(containers) >= LIMITS["nestingDepth"]:
                raise JsonStructureError(f"input exceeds {LIMITS['nestingDepth']} level nesting depth limit")
            containers.append(["array" if character == "[" else "object", character == "[", 0])
        elif character in "]}":
            if containers:
                containers.pop()
        elif character == ",":
            if containers and containers[-1][0] == "array":
                containers[-1][1] = True
        elif character not in JS_WHITESPACE:
            mark_array_item()


def run(file) -> int:
    if not file:
        print("Usage: python3 validate_findings.py <path-to-findings.json>", file=sys.stderr)
        return 1

    try:
        schema = load_schema()
    except Exception as error:
        print("Failed to load report-schema.json:", error, file=sys.stderr)
        return 1

    try:
        contents = read_file_within_limit(file, LIMITS["inputBytes"])
    except Exception as error:
        reason = str(error) if isinstance(error, SafeInputError) else "input could not be opened or read safely"
        print(f"Failed to read findings JSON: {reason}", file=sys.stderr)
        return 1

    try:
        enforce_json_text_limits(contents)
    except Exception as error:
        reason = str(error) if isinstance(error, JsonStructureError) else "invalid JSON structure"
        print(f"Failed to parse findings JSON: {reason}", file=sys.stderr)
        return 1

    try:
        findings = parse_json_text(contents)
    except Exception:
        print("Failed to parse findings JSON: invalid JSON syntax", file=sys.stderr)
        return 1

    try:
        errors = validate_document(findings, schema)
    except Exception:
        print("Failed to validate findings JSON: unexpected validation error", file=sys.stderr)
        return 1
    for message in errors:
        print("ERROR:", escape_unsafe_diagnostic_characters(message), file=sys.stderr)
    if errors:
        cap = (
            f"; output capped at {LIMITS['validationErrors']}"
            if len(errors) == LIMITS["validationErrors"]
            else ""
        )
        print(f"FAIL: {len(errors)} validation error(s){cap}", file=sys.stderr)
        return 1
    print(f"PASS: {len(findings)} findings valid")
    return 0


def main(argv=None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    try:
        return run(arguments[0] if arguments else None)
    except Exception:
        print("Failed to validate findings JSON: unexpected validation error", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
