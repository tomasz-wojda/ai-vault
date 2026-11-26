import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

import validate_coverage_ledger as ledger_module  # noqa: E402
import validate_findings as findings_module  # noqa: E402
from validate_findings import (  # noqa: E402
    LIMITS,
    collect,
    collect_schema_errors,
    validate_document,
)

VALIDATOR_PATH = SKILL_ROOT / "scripts" / "validate_findings.py"
SCHEMA = json.loads((SKILL_ROOT / "references" / "report-schema.json").read_text(encoding="utf-8"))
CLI_TIMEOUT_SECONDS = 10
HOSTILE_CLI_TIMEOUT_SECONDS = 60
HAS_SAFE_INPUT_OPEN = bool(getattr(os, "O_NOFOLLOW", 0)) and bool(getattr(os, "O_NONBLOCK", 0))
TERMINAL_CONTROL_PAYLOAD = "\u001b\u0007\u0085\u202e\u034f\ufe0f"
TERMINAL_CONTROL_BYTES = [
    b"\x1b",
    b"\x07",
    "\u0085".encode("utf-8"),
    "\u202e".encode("utf-8"),
    "\u034f".encode("utf-8"),
    "\ufe0f".encode("utf-8"),
]
ENGINE_FAILURE = re.compile(r"Traceback|RecursionError|MemoryError", re.IGNORECASE)


def to_json(value) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return "".join(f"\\u{ord(character):04x}" if 0xD800 <= ord(character) <= 0xDFFF else character for character in text)


def source(kind="entrypoint", file="src/handler.c", line=10):
    return {"kind": kind, "file": file, "line": line, "scope": "handle", "description": "Attacker data reaches the operation."}


def evidence(file="src/handler.c", line=10):
    return {"file": file, "line": line, "description": "The source performs the operation without the required check."}


def confirmed():
    return {
        "verdict": "confirmed",
        "fingerprint": "src-handler-missing-check",
        "title": "Missing ownership check",
        "description": "An attacker can reach an operation without the intended ownership check.",
        "root_cause": "handle omits the ownership check before changing the object.",
        "intended_behavior": "Only the object's owner can change it.",
        "trace": [source("entrypoint"), source("propagation", "src/model.c", 20), source("sink", "src/store.c", 30)],
        "evidence": [evidence()],
        "conditions": [],
        "execution": {
            "attacker_perspective": "An unprivileged remote user with their own account.",
            "payloads": ["An object identifier owned by another user."],
            "instructions": ["Submit the identifier through the public operation."],
            "observed_result": "The other user's object changes.",
        },
        "remediation": {"strategy": "Check ownership before the state change."},
        "severity": {
            "likelihood": {"score": "medium", "reason": "The operation is directly reachable."},
            "impact": {"score": "medium", "reason": "The attacker changes one protected object."},
            "overall_severity": "medium",
        },
        "confidence": {"score": "high", "reason": "The source path and result were reproduced."},
    }


def needs_validation():
    return {
        "verdict": "needs_validation",
        "fingerprint": "src-parser-size-hypothesis",
        "title": "Unchecked parsed size",
        "description": "A parsed size may reach an allocation without a limit.",
        "claimed_root_cause": "parse_size may pass an unbounded value to allocate.",
        "trace": [source()],
        "evidence": [evidence()],
        "blockers": ["The generated parser source is absent from this checkout."],
        "validation_plan": {
            "local": "Generate the parser and submit the smallest input that exceeds the documented limit.",
            "deployment": "In an approved test deployment, confirm the request reaches the generated parser and record the bounded observable result.",
        },
    }


def rejected():
    return {
        "verdict": "rejected",
        "fingerprint": "src-router-auth-bypass",
        "title": "Authorization bypass in router",
        "description": "The candidate claimed a route bypassed authorization.",
        "claimed_root_cause": "dispatch was claimed to skip the authorization wrapper.",
        "trace": [source("sink")],
        "evidence": [evidence()],
        "reason": "All routes pass through the authorization wrapper before dispatch.",
    }


def errors_for(value):
    return validate_document(value, SCHEMA)


def run_validator(arguments, timeout=CLI_TIMEOUT_SECONDS):
    return subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), *arguments],
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def run_cli(contents, timeout=CLI_TIMEOUT_SECONDS):
    directory = tempfile.mkdtemp(prefix="validate-findings-")
    findings_path = os.path.join(directory, "findings.json")
    try:
        data = contents.encode("utf-8") if isinstance(contents, str) else contents
        with open(findings_path, "wb") as handle:
            handle.write(data)
        return run_validator([findings_path], timeout)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def stdout_of(result) -> str:
    return result.stdout.decode("utf-8", "replace")


def stderr_of(result) -> str:
    return result.stderr.decode("utf-8", "replace")


def cli_output(result) -> str:
    return stdout_of(result) + stderr_of(result)


def producer_shaped_findings():
    demonstrated = confirmed()
    demonstrated["conditions"] = [{
        "kind": "authentication_level",
        "description": "The attacker needs a normal account.",
    }]
    demonstrated["execution"]["payloads"] = ["", " \t\r\n", "\u0000\u001f\u007f", "\u034f", "\ufe0f", "\ud800", "\udc00", "[{,}]\\\""]
    demonstrated["remediation"]["code_changes"] = [{
        "file_name": "src/handler.c",
        "fixed_code": "",
    }]

    blocked = needs_validation()
    del blocked["validation_plan"]["deployment"]

    return [demonstrated, blocked, rejected()]


class ValidateFindingsTests(unittest.TestCase):
    def assert_no_injected_control_bytes(self, output):
        data = output if isinstance(output, bytes) else output.encode("utf-8", "surrogatepass")
        for marker in TERMINAL_CONTROL_BYTES:
            self.assertEqual(data.find(marker), -1, f"found raw control bytes {marker.hex()}")

    def reject_mutation(self, factory, mutate):
        value = factory()
        mutate(value)
        self.assertNotEqual(len(errors_for([value])), 0)

    def test_schema_is_an_actual_top_level_array_with_exactly_three_branches(self):
        self.assertEqual(SCHEMA["type"], "array")
        self.assertEqual(len(SCHEMA["items"]["oneOf"]), 3)
        self.assertEqual(
            [branch["properties"]["verdict"]["const"] for branch in SCHEMA["items"]["oneOf"]],
            ["confirmed", "needs_validation", "rejected"],
        )
        confirmed_schema = SCHEMA["items"]["oneOf"][0]["properties"]
        self.assertIs(confirmed_schema["title"]["visibleContent"], True)
        payload_items = confirmed_schema["execution"]["properties"]["payloads"]["items"]
        self.assertNotIn("minLength", payload_items)
        self.assertNotIn("visibleContent", payload_items)
        fixed_code = confirmed_schema["remediation"]["properties"]["code_changes"]["items"]["properties"]["fixed_code"]
        self.assertNotIn("minLength", fixed_code)

    def test_accepts_a_producer_shaped_findings_document_through_the_cli(self):
        result = run_cli(to_json(producer_shaped_findings()))
        self.assertEqual(result.returncode, 0, cli_output(result))
        self.assertRegex(stdout_of(result), r"PASS: 3 findings valid")

    def test_accepts_empty_output_and_each_complete_branch(self):
        self.assertEqual(errors_for([]), [])
        self.assertEqual(errors_for([confirmed(), needs_validation(), rejected()]), [])
        local_only = needs_validation()
        del local_only["validation_plan"]["deployment"]
        self.assertEqual(errors_for([local_only]), [])
        deployment_only = needs_validation()
        del deployment_only["validation_plan"]["local"]
        self.assertEqual(errors_for([deployment_only]), [])

    def test_allows_a_one_line_finding_trace(self):
        finding = confirmed()
        finding["trace"] = [source("entrypoint")]
        self.assertEqual(errors_for([finding]), [])

    def test_rejects_empty_required_content(self):
        cases = [
            (confirmed, lambda finding: finding.update(title="")),
            (confirmed, lambda finding: finding.update(title="   ")),
            (confirmed, lambda finding: finding.update(evidence=[])),
            (confirmed, lambda finding: finding["execution"].update(payloads=[])),
            (confirmed, lambda finding: finding["execution"].update(instructions=[])),
            (confirmed, lambda finding: finding["execution"].update(observed_result="")),
            (confirmed, lambda finding: finding["remediation"].update(strategy="")),
            (needs_validation, lambda finding: finding.update(blockers=[])),
            (needs_validation, lambda finding: finding.update(validation_plan={})),
            (needs_validation, lambda finding: finding.update(validation_plan={"local": " "})),
            (rejected, lambda finding: finding.update(claimed_root_cause="")),
        ]
        for factory, mutate in cases:
            self.reject_mutation(factory, mutate)

    def test_preserves_exact_payload_and_replacement_code_strings(self):
        finding = confirmed()
        payloads = ["", " \t\r\n", "\u0000\u001f\u007f", "\u034f", "\ufe0f", "\ud800", "\udc00"]
        fixed_code = "\u0000 \t\r\n\u001f\u007f\u034f\ufe0f\ud800x\udc00"
        finding["execution"]["payloads"] = list(payloads)
        finding["remediation"]["code_changes"] = [{"file_name": "src/handler.c", "fixed_code": fixed_code}]

        self.assertEqual(errors_for([finding]), [])
        self.assertEqual(finding["execution"]["payloads"], payloads)
        self.assertEqual(finding["remediation"]["code_changes"][0]["fixed_code"], fixed_code)

    def test_rejects_invalid_scalars_and_whitespace_control_format_or_default_ignorable_prose(self):
        for invisible in ["\u0000\t\r\n\u001f\u007f\u200b", "\u034f", "\ufe0f", "\ud800", "\udc00", "visible\ud800"]:
            cases = [
                (confirmed, lambda finding: finding.update(title=invisible)),
                (confirmed, lambda finding: finding["trace"][0].update(scope=invisible)),
                (confirmed, lambda finding: finding["evidence"][0].update(description=invisible)),
                (confirmed, lambda finding: finding["execution"].update(instructions=[invisible])),
                (confirmed, lambda finding: finding["remediation"].update(strategy=invisible)),
                (confirmed, lambda finding: finding["severity"]["impact"].update(reason=invisible)),
                (confirmed, lambda finding: finding["confidence"].update(reason=invisible)),
                (needs_validation, lambda finding: finding.update(blockers=[invisible])),
                (needs_validation, lambda finding: finding.update(validation_plan={"local": invisible})),
                (rejected, lambda finding: finding.update(reason=invisible)),
            ]
            for factory, mutate in cases:
                self.reject_mutation(factory, mutate)

    def test_quotes_input_derived_controls_in_direct_validation_values_and_paths(self):
        finding = confirmed()
        finding["trace"][0]["kind"] = f"invalid-{TERMINAL_CONTROL_PAYLOAD}"
        finding["execution"][f"extra-{TERMINAL_CONTROL_PAYLOAD}"] = "value"

        cyclic = {}
        cyclic[f"path-{TERMINAL_CONTROL_PAYLOAD}"] = cyclic
        output = "\n".join([
            *errors_for([finding]),
            *collect(cyclic, {"type": "object"}, "$input"),
        ])

        for escaped in ["\\u001b", "\\u0007", "\\u0085", "\\u202e", "\\u034f", "\\ufe0f"]:
            self.assertIn(escaped, output, f"missing escaped diagnostic {escaped}")
        self.assert_no_injected_control_bytes(output)

    def test_rejects_line_zero(self):
        self.reject_mutation(confirmed, lambda finding: finding["trace"][0].update(line=0))
        self.reject_mutation(rejected, lambda finding: finding["evidence"][0].update(line=0))

    def test_does_not_treat_inherited_or_object_prototype_properties_as_schema_properties(self):
        self.reject_mutation(confirmed, lambda finding: finding.update(constructor="not allowed"))
        inherited = {}
        self.assertTrue(any("exactly one" in error for error in errors_for([inherited])))
        self.assertTrue(any("missing required" in error for error in collect({}, {
            "type": "object",
            "properties": {"constructor": {"type": "string"}},
            "required": ["constructor"],
            "additionalProperties": False,
        })))

    def test_one_of_requires_exactly_one_passing_branch(self):
        self.assertTrue(any(
            "matched 2" in error
            for error in collect("value", {"oneOf": [{"type": "string"}, {"minLength": 1}]}, "$test")))
        self.assertTrue(any(
            "matched 0" in error
            for error in collect(7, {"oneOf": [{"type": "string"}, {"minimum": 10}]}, "$test")))

    def test_rejects_duplicate_fingerprints_and_unique_array_entries(self):
        first = confirmed()
        second = rejected()
        second["fingerprint"] = first["fingerprint"]
        self.assertTrue(any("duplicate of" in error for error in errors_for([first, second])))
        self.reject_mutation(
            needs_validation,
            lambda finding: finding.update(blockers=[finding["blockers"][0], finding["blockers"][0]]))

    def test_uses_canonical_set_uniqueness_for_structured_entries_at_the_array_limit(self):
        entries = [{"id": index, "label": str(index)} for index in range(LIMITS["arrayItems"])]
        self.assertEqual(collect(entries, {"type": "array", "uniqueItems": True}), [])

        duplicate = entries[:-1]
        duplicate.append({"label": "0", "id": 0})
        self.assertTrue(any(
            f"duplicate at index {LIMITS['arrayItems'] - 1}" in error
            for error in collect(duplicate, {"type": "array", "uniqueItems": True})))

    def test_bounds_canonical_uniqueness_keys_and_set_storage(self):
        oversized_key = "x" * (LIMITS["canonicalKeyBytes"] + 1)
        self.assertTrue(any(
            "canonical key exceeds" in error
            for error in collect([oversized_key], {"type": "array", "uniqueItems": True})))

        item_length = LIMITS["uniqueSetBytes"] // 6
        large_unique_items = [f"{index}{'x' * item_length}" for index in range(6)]
        self.assertTrue(any(
            "canonical uniqueness set exceeds" in error
            for error in collect(large_unique_items, {"type": "array", "uniqueItems": True})))

    def test_requires_findings_to_be_sorted_by_fingerprint(self):
        first = confirmed()
        second = rejected()
        self.assertTrue(any("sorted lexicographically" in error for error in errors_for([second, first])))

    def test_rejects_severity_above_demonstrated_impact(self):
        def mutate(finding):
            finding["severity"]["overall_severity"] = "high"
            finding["severity"]["impact"]["score"] = "medium"

        self.reject_mutation(confirmed, mutate)

    def test_rejects_unsafe_source_paths(self):
        bad_paths = [
            "/etc/passwd",
            "../src/file.c",
            "src/../file.c",
            "src//file.c",
            "C:\\src\\file.c",
            "src/file:name.c",
            "src/file\nname.c",
            "src/file\u0001name.c",
            "src/file\u0085name.c",
            "src/file\u2028name.c",
            "src/file\u202ename.c",
            "src/file\u2066name.c",
            "src/file\u200dname.c",
            "src/file\u034fname.c",
            "src/file\ufe0fname.c",
            "src/file\ud800name.c",
            "src/file\udc00name.c",
            "CON",
            "src/con.txt",
            "src/PRN",
            "src/AUX.c",
            "src/NUL",
            "src/COM1.log",
            "src/lpt9",
            "src/CONIN$",
            "src/CONOUT$.txt",
            "src/CLOCK$.txt",
            "src/COM\u00b9.log",
            "src/LPT\u00b2.log",
            "src /file.c",
            "src./file.c",
            "src/file.c ",
            "src/file.c.",
        ]
        for bad_path in bad_paths:
            self.reject_mutation(confirmed, lambda finding: finding["trace"][0].update(file=bad_path))
        self.reject_mutation(rejected, lambda finding: finding["evidence"][0].update(file="NUL.txt"))
        self.reject_mutation(confirmed, lambda finding: finding["remediation"].update(
            code_changes=[{"file_name": "src/file:name.c", "fixed_code": "replacement"}]))

    def test_accepts_legitimate_unicode_source_paths_and_prose(self):
        finding = confirmed()
        finding["title"] = "Finding \U0001f600 cafe\u0301"
        finding["trace"][0]["file"] = "src/日本語/cafe\u0301-\U0001f600.ts"
        finding["evidence"][0]["file"] = "src/mañana/файл.ts"
        finding["remediation"]["code_changes"] = [{
            "file_name": "src/修正/éxito.ts",
            "fixed_code": "replacement",
        }]
        self.assertEqual(errors_for([finding]), [])

    def test_cli_rejects_input_above_the_byte_limit_without_an_exception_trace(self):
        result = run_cli(b" " * (LIMITS["inputBytes"] + 1))
        output = cli_output(result)
        self.assertEqual(result.returncode, 1, output)
        self.assertRegex(output, f"input exceeds {LIMITS['inputBytes']} byte limit")
        self.assertNotRegex(output, ENGINE_FAILURE)

    def test_cli_rejects_invalid_utf_8_without_replacement_or_an_exception_trace(self):
        findings = producer_shaped_findings()
        findings[0]["execution"]["payloads"] = ["INVALID_UTF8"]
        encoded = to_json(findings).encode("utf-8")
        marker = b"INVALID_UTF8"
        marker_offset = encoded.find(marker)
        self.assertNotEqual(marker_offset, -1)
        malformed = encoded[:marker_offset] + b"\x80" + encoded[marker_offset + len(marker):]

        result = run_cli(malformed)
        output = cli_output(result)
        self.assertEqual(result.returncode, 1, output)
        self.assertRegex(output, r"input is not valid UTF-8")
        self.assertNotRegex(output, ENGINE_FAILURE)

    @unittest.skipUnless(HAS_SAFE_INPUT_OPEN, "no-follow and nonblocking open unavailable")
    def test_quotes_input_derived_controls_in_cli_validation_errors(self):
        finding = confirmed()
        finding["trace"][0]["kind"] = f"invalid-{TERMINAL_CONTROL_PAYLOAD}"
        finding["execution"][f"extra-{TERMINAL_CONTROL_PAYLOAD}"] = "value"
        result = run_cli(to_json([finding]))

        self.assertEqual(result.returncode, 1, cli_output(result))
        self.assertRegex(stderr_of(result), r"\$\[0\]\.trace\[0\]\.kind")
        self.assertRegex(stderr_of(result), r"\\u001b")
        self.assertRegex(stderr_of(result), r"\\u202e")
        self.assert_no_injected_control_bytes(result.stderr)

    @unittest.skipUnless(HAS_SAFE_INPUT_OPEN, "no-follow and nonblocking open unavailable")
    def test_returns_a_generic_syntax_error_without_parser_supplied_controls(self):
        malformed = b"[" + TERMINAL_CONTROL_PAYLOAD.encode("utf-8") + b"]"
        result = run_cli(malformed)

        self.assertEqual(result.returncode, 1, cli_output(result))
        self.assertEqual(stderr_of(result), "Failed to parse findings JSON: invalid JSON syntax\n")
        self.assert_no_injected_control_bytes(result.stderr)

    def test_does_not_reflect_controls_from_a_failed_cli_input_path(self):
        directory = tempfile.mkdtemp(prefix="validate-findings-path-")
        missing_path = os.path.join(directory, f"missing-{TERMINAL_CONTROL_PAYLOAD}.json")
        try:
            result = run_validator([missing_path])
            self.assertEqual(result.returncode, 1, cli_output(result))
            self.assertRegex(stderr_of(result), r"Failed to read findings JSON:")
            self.assert_no_injected_control_bytes(result.stderr)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_cli_rejects_lone_surrogate_prose_without_changing_payload_semantics(self):
        findings = producer_shaped_findings()
        findings[0]["title"] = "\ud800"
        result = run_cli(to_json(findings))
        output = cli_output(result)
        self.assertEqual(result.returncode, 1, output)
        self.assertRegex(output, r"must contain only valid Unicode scalar values")
        self.assertNotRegex(output, ENGINE_FAILURE)

    def test_cli_rejects_unicode_format_controls_in_source_paths(self):
        findings = producer_shaped_findings()
        findings[0]["trace"][0]["file"] = "src/file\u202ename.c"
        result = run_cli(to_json(findings))
        output = cli_output(result)
        self.assertEqual(result.returncode, 1, output)
        self.assertRegex(output, r"must be a safe repository-relative source path")
        self.assertNotRegex(output, ENGINE_FAILURE)

    @unittest.skipIf(sys.platform == "win32", "FIFO semantics differ on Windows")
    @unittest.skipUnless(HAS_SAFE_INPUT_OPEN, "no-follow and nonblocking open unavailable")
    def test_cli_rejects_a_fifo_without_blocking(self):
        directory = tempfile.mkdtemp(prefix="validate-findings-fifo-")
        fifo_path = os.path.join(directory, "findings.json")
        try:
            os.mkfifo(fifo_path)
            result = run_validator([fifo_path])
            output = cli_output(result)
            self.assertEqual(result.returncode, 1, output)
            self.assertRegex(output, r"input must be a regular file")
            self.assertNotRegex(output, ENGINE_FAILURE)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    @unittest.skipIf(sys.platform == "win32", "symlink semantics differ on Windows")
    @unittest.skipUnless(HAS_SAFE_INPUT_OPEN, "no-follow and nonblocking open unavailable")
    def test_cli_rejects_a_symlink_without_following_it(self):
        directory = tempfile.mkdtemp(prefix="validate-findings-symlink-")
        target_path = os.path.join(directory, "target.json")
        symlink_path = os.path.join(directory, "findings.json")
        try:
            with open(target_path, "w", encoding="utf-8") as handle:
                handle.write(to_json(producer_shaped_findings()))
            os.symlink(target_path, symlink_path)
            result = run_validator([symlink_path])
            output = cli_output(result)
            self.assertEqual(result.returncode, 1, output)
            self.assertRegex(output, r"input must not be a symlink")
            self.assertNotRegex(output, ENGINE_FAILURE)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_cli_rejects_input_above_the_nesting_depth_limit_without_an_exception_trace(self):
        levels = LIMITS["nestingDepth"] + 1
        result = run_cli("[" * levels + "0" + "]" * levels)
        output = cli_output(result)
        self.assertEqual(result.returncode, 1, output)
        self.assertRegex(output, f"{LIMITS['nestingDepth']} level nesting depth limit")
        self.assertNotRegex(output, ENGINE_FAILURE)

    def test_cli_rejects_an_oversized_array_without_an_exception_trace(self):
        result = run_cli(to_json([None] * (LIMITS["arrayItems"] + 1)))
        output = cli_output(result)
        self.assertEqual(result.returncode, 1, output)
        self.assertRegex(output, f"{LIMITS['arrayItems']} item array limit")
        self.assertNotRegex(output, ENGINE_FAILURE)

    def test_checks_pattern_and_branch_invariants(self):
        self.reject_mutation(rejected, lambda finding: finding.update(fingerprint="not stable"))
        self.reject_mutation(needs_validation, lambda finding: finding.update(
            severity={"impact": {"score": "low"}, "overall_severity": "low"}))

    def test_rejects_unsupported_and_malformed_schema_keywords(self):
        self.assertTrue(any("format" in error for error in collect_schema_errors({"type": "string", "format": "uuid"})))
        self.assertTrue(any("regular expression" in error for error in collect_schema_errors({"type": "string", "pattern": "["})))
        self.assertTrue(any("expected boolean" in error for error in collect_schema_errors({"type": "string", "visibleContent": "yes"})))
        self.assertTrue(any("requires type" in error for error in collect_schema_errors({"type": "array", "visibleContent": True})))
        self.assertNotEqual(len(validate_document([], {"type": "array", "maxItems": 1})), 0)

    def test_caps_malformed_1000_finding_validation_output(self):
        self.assertEqual(len(errors_for([None] * LIMITS["arrayItems"])), LIMITS["validationErrors"])
        if not HAS_SAFE_INPUT_OPEN:
            return

        result = run_cli(to_json([None] * LIMITS["arrayItems"]))
        output = cli_output(result)
        self.assertEqual(result.returncode, 1, output)
        self.assertRegex(output, r"output capped at 100")
        self.assertLess(len(output), 20000, f"unexpected output length {len(output)}")
        self.assertNotRegex(output, ENGINE_FAILURE)

    @unittest.skipUnless(HAS_SAFE_INPUT_OPEN, "no-follow and nonblocking open unavailable")
    def test_caps_amplified_in_limit_findings_output(self):
        findings = [{
            "verdict": "confirmed",
            "trace": [0] * LIMITS["arrayItems"],
            "evidence": [0] * LIMITS["arrayItems"],
        } for _ in range(750)]
        contents = to_json(findings)
        self.assertGreater(len(contents), 3 * 1000 * 1000, f"hostile input too small: {len(contents)}")
        self.assertLessEqual(len(contents), LIMITS["inputBytes"], f"hostile input over limit: {len(contents)}")

        result = run_cli(contents, timeout=HOSTILE_CLI_TIMEOUT_SECONDS)
        output = cli_output(result)
        self.assertEqual(result.returncode, 1, output)
        self.assertRegex(output, r"output capped at 100")
        self.assertLess(len(output), 20000, f"unexpected output length {len(output)}")
        self.assertNotRegex(output, ENGINE_FAILURE)

    def test_keeps_shared_helpers_aligned_with_the_coverage_ledger_validator(self):
        for name in ("WINDOWS_RESERVED_COMPONENT", "has_visible_prose", "safe_quote", "ErrorList"):
            self.assertIs(getattr(findings_module, name), getattr(ledger_module, name), name)
        self.assertIs(findings_module.is_safe_relative_source_path, ledger_module.is_safe_relative_path)

        shared_limit_keys = sorted(key for key in findings_module.LIMITS if key in ledger_module.LIMITS)
        self.assertEqual(shared_limit_keys, ["inputBytes", "nestingDepth", "validationErrors"])
        for key in shared_limit_keys:
            self.assertEqual(findings_module.LIMITS[key], ledger_module.LIMITS[key], f"LIMITS.{key}")

        path_corpus = [
            "src/handler.js",
            "src/caf\u00e9/handler.js",
            "src/\u65e5\u672c\u8a9e/\u0444\u0430\u0439\u043b.ts",
            "src/cloc\u212a$.txt",
            "src/CLOCK$.txt",
            "src/con.txt",
            "CON",
            "src/COM\u00b9.log",
            "src/lpt\u00b3",
            "/etc/passwd",
            "../src/file.c",
            "src/../file.c",
            "src//file.c",
            "src\\file.c",
            "src/file:name.c",
            "~home/file.c",
            "C:/file.c",
            "src/file.c ",
            "src/file.c.",
            "src/file\u202ename.c",
            "src/file\u200b.js",
            "src/file\u034f.js",
            "src/file\ufe0f.js",
            "src/file\ud800name.c",
            "src/file\udc00name.c",
        ]
        for value in path_corpus:
            self.assertEqual(
                findings_module.is_safe_relative_source_path(value),
                ledger_module.is_safe_relative_path(value),
                f"path verdict diverges for {value!r}",
            )
        self.assertFalse(findings_module.is_safe_relative_source_path("src/cloc\u212a$.txt"))
        self.assertFalse(ledger_module.is_safe_relative_path("src/cloc\u212a$.txt"))

        prose_corpus = [
            "Valid prose.",
            "caf\u00e9",
            "",
            " \t\r\n",
            "\u200b",
            "\u034f",
            "\ufe0f",
            "\ud800",
            "\udc00",
            "visible\ud800",
        ]
        for value in prose_corpus:
            self.assertEqual(
                findings_module.has_visible_prose(value),
                ledger_module.has_visible_prose(value),
                f"prose verdict diverges for {value!r}",
            )


if __name__ == "__main__":
    unittest.main()
