import argparse
import html
import importlib
import re
import sys
from pathlib import Path

from reportlab.platypus import Paragraph


DEFAULT_ROW_HEIGHT = 19.0
HORIZONTAL_PADDING = 16.0
VERTICAL_PADDING = 4.0
TAG = re.compile(r"<[^>]+>")
TEMP_NOTES_HEADING = re.compile(r"^## Slide (\d+) — (.+?)\s*$", re.MULTILINE)
LEVEL_TWO_HEADING = re.compile(r"^## .+$", re.MULTILINE)


def load_module(name, deck_directory):
    sys.path.insert(0, str(deck_directory))
    try:
        sys.modules.pop(name, None)
        return importlib.import_module(name)
    finally:
        sys.path.pop(0)


def expected_page_keys(page_count):
    return set(range(1, page_count + 1))


def validate_page_keys(slides, notes, timings):
    findings = []
    expected = expected_page_keys(len(slides))
    if set(notes) != expected:
        findings.append(
            f"notes keys must be {sorted(expected)}, got {sorted(notes)}"
        )
    if set(timings) != expected:
        findings.append(
            f"timing keys must be {sorted(expected)}, got {sorted(timings)}"
        )
    return findings


def validate_timings(timings, questions_minutes, slot_minutes):
    findings = []
    warnings = []
    for page, minutes in timings.items():
        if not isinstance(minutes, (int, float)) or minutes < 0:
            findings.append(f"timing for page {page} must be a non-negative number")
    if not isinstance(questions_minutes, (int, float)) or questions_minutes < 0:
        findings.append("QUESTIONS_MINUTES must be a non-negative number")
        return findings, warnings, None
    if findings:
        return findings, warnings, None
    total = sum(timings.values()) + questions_minutes
    if slot_minutes is not None and total > slot_minutes:
        warnings.append(
            f"total duration {total:g} minutes exceeds slot {slot_minutes:g}"
        )
    return findings, warnings, total


def validate_table_shape(spec, page_number, table_number):
    findings = []
    rows = spec.get("rows")
    widths = spec.get("colWidths")
    label = f"page {page_number} table {table_number}"
    if not isinstance(rows, list) or not rows:
        return [f"{label}: rows must be a non-empty list"]
    if not isinstance(widths, list) or not widths:
        return [f"{label}: colWidths must be a non-empty list"]
    column_count = len(widths)
    for row_number, row in enumerate(rows):
        if not isinstance(row, (list, tuple)) or len(row) != column_count:
            findings.append(
                f"{label}: row {row_number} must contain {column_count} cells"
            )
    row_heights = spec.get("row_heights")
    if row_heights is not None:
        if not isinstance(row_heights, list) or len(row_heights) != len(rows):
            findings.append(
                f"{label}: row_heights must contain one value per row"
            )
        elif any(
            not isinstance(height, (int, float)) or height <= 0
            for height in row_heights
        ):
            findings.append(f"{label}: row_heights values must be positive numbers")
    else:
        row_height = spec.get("row_height", DEFAULT_ROW_HEIGHT)
        if not isinstance(row_height, (int, float)) or row_height <= 0:
            findings.append(f"{label}: row_height must be a positive number")
    for column, width in enumerate(widths):
        if not isinstance(width, (int, float)) or width <= 0:
            findings.append(f"{label}: column {column} width must be positive")
    return findings


def row_heights_for(spec):
    if "row_heights" in spec:
        return list(spec["row_heights"])
    return [spec.get("row_height", DEFAULT_ROW_HEIGHT)] * len(spec["rows"])


def parse_spans(spec, page_number, table_number):
    findings = []
    starts = {}
    covered = set()
    rows = spec["rows"]
    widths = spec["colWidths"]
    label = f"page {page_number} table {table_number}"
    for index, span in enumerate(spec.get("spans", [])):
        valid_shape = (
            isinstance(span, (list, tuple))
            and len(span) == 2
            and all(
                isinstance(point, (list, tuple))
                and len(point) == 2
                and all(isinstance(value, int) for value in point)
                for point in span
            )
        )
        if not valid_shape:
            findings.append(f"{label}: span {index} has invalid coordinates")
            continue
        (start_column, start_row), (end_column, end_row) = span
        in_bounds = (
            0 <= start_column <= end_column < len(widths)
            and 0 <= start_row <= end_row < len(rows)
        )
        if not in_bounds:
            findings.append(f"{label}: span {index} is outside the table")
            continue
        start = (start_row, start_column)
        starts[start] = (end_row, end_column)
        for row in range(start_row, end_row + 1):
            for column in range(start_column, end_column + 1):
                coordinate = (row, column)
                if coordinate != start:
                    covered.add(coordinate)
    return findings, starts, covered


def measure_table_cells(spec, styles, markup, page_number, table_number):
    findings = []
    label = f"page {page_number} table {table_number}"
    span_findings, span_starts, covered = parse_spans(
        spec, page_number, table_number
    )
    findings.extend(span_findings)
    if span_findings:
        return findings
    rows = spec["rows"]
    widths = spec["colWidths"]
    heights = row_heights_for(spec)
    last_row = len(rows) - 1
    for row_number, row in enumerate(rows):
        for column_number, cell in enumerate(row):
            coordinate = (row_number, column_number)
            if coordinate in covered:
                continue
            end_row, end_column = span_starts.get(
                coordinate, (row_number, column_number)
            )
            width = sum(widths[column_number : end_column + 1])
            height = sum(heights[row_number : end_row + 1])
            style_name = (
                "cellb"
                if row_number == 0
                or (spec.get("total_row") and row_number == last_row)
                else "cell"
            )
            try:
                paragraph = Paragraph(markup(str(cell)), styles[style_name])
                _, required_height = paragraph.wrap(
                    width - HORIZONTAL_PADDING, 10000
                )
            except Exception as exc:
                findings.append(
                    f"{label}: cell {row_number},{column_number} cannot render: {exc}"
                )
                continue
            usable_height = height - VERTICAL_PADDING
            if required_height > usable_height:
                findings.append(
                    f"{label}: cell overflow at {row_number},{column_number}: "
                    f"needs {required_height:g}pt, has {usable_height:g}pt"
                )
    return findings


def iter_tables(slides):
    for page_number, slide in enumerate(slides, start=1):
        items = slide.get("items", []) if isinstance(slide, dict) else []
        table_number = 0
        for item in items:
            if (
                isinstance(item, (list, tuple))
                and len(item) == 2
                and item[0] == "table"
            ):
                table_number += 1
                yield page_number, table_number, item[1]


def collect_text(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result = []
        for nested in value.values():
            result.extend(collect_text(nested))
        return result
    if isinstance(value, (list, tuple)):
        result = []
        for nested in value:
            result.extend(collect_text(nested))
        return result
    return []


def validate_expected_text(slides, expected_texts):
    text = "\n".join(collect_text(slides))
    return [
        f"expected text is missing: {expected}"
        for expected in expected_texts
        if expected not in text
    ]


def plain_text(value):
    return html.unescape(TAG.sub("", str(value))).strip()


def slide_heading(slide):
    if not isinstance(slide, dict):
        return "(untitled)"
    for item in slide.get("items", []):
        if (
            isinstance(item, (list, tuple))
            and len(item) == 2
            and item[0] in ("h1", "h2")
        ):
            return plain_text(item[1])
    return "(untitled)"


def temporary_notes_sections(text):
    section_boundaries = list(LEVEL_TWO_HEADING.finditer(text))
    sections = []
    for index, boundary in enumerate(section_boundaries):
        match = TEMP_NOTES_HEADING.match(boundary.group(0))
        if match is None:
            continue
        body_end = (
            section_boundaries[index + 1].start()
            if index + 1 < len(section_boundaries)
            else len(text)
        )
        sections.append(
            (int(match.group(1)), match.group(2).strip(), text[boundary.end() : body_end])
        )
    return sections


def validate_temporary_notes(slides, path):
    if path is None:
        return []
    notes_path = Path(path)
    if not notes_path.is_file():
        return [f"temporary notes file does not exist: {notes_path}"]
    try:
        text = notes_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"temporary notes file cannot be read: {exc}"]
    sections = temporary_notes_sections(text)
    expected_numbers = list(range(1, len(slides) + 1))
    actual_numbers = [number for number, _, _ in sections]
    findings = []
    if actual_numbers != expected_numbers:
        findings.append(
            f"temporary notes sections must be {expected_numbers}, got {actual_numbers}"
        )
    for number, title, body in sections:
        if number > len(slides):
            continue
        expected_title = slide_heading(slides[number - 1])
        if title != expected_title:
            findings.append(
                f"temporary notes title mismatch for slide {number}: "
                f"expected '{expected_title}', got '{title}'"
            )
        if not body.strip():
            findings.append(f"temporary notes section {number} has no prose")
    return findings


def validate_deck(
    content_module,
    notes_module,
    renderer_module,
    slot_minutes=None,
    expected_texts=None,
    temp_notes_path=None,
):
    findings = []
    warnings = []
    slides = getattr(content_module, "SLIDES", None)
    notes = getattr(notes_module, "NOTES", None)
    timings = getattr(notes_module, "TIMINGS", None)
    questions = getattr(notes_module, "QUESTIONS_MINUTES", 0)
    if not isinstance(slides, list) or not slides:
        return ["SLIDES must be a non-empty list"], warnings, None, 0
    if not isinstance(notes, dict):
        return ["NOTES must be a dictionary"], warnings, None, len(slides)
    if not isinstance(timings, dict):
        return ["TIMINGS must be a dictionary"], warnings, None, len(slides)
    findings.extend(validate_page_keys(slides, notes, timings))
    timing_findings, timing_warnings, total = validate_timings(
        timings, questions, slot_minutes
    )
    findings.extend(timing_findings)
    warnings.extend(timing_warnings)
    try:
        regular, bold = renderer_module.register_fonts()
        styles = renderer_module.build_styles(regular, bold)
        markup = getattr(renderer_module, "markup", lambda value: value)
    except Exception as exc:
        findings.append(f"renderer styles could not be loaded: {exc}")
        return findings, warnings, total, len(slides)
    for page_number, table_number, spec in iter_tables(slides):
        shape_findings = validate_table_shape(spec, page_number, table_number)
        findings.extend(shape_findings)
        if not shape_findings:
            findings.extend(
                measure_table_cells(
                    spec,
                    styles,
                    markup,
                    page_number,
                    table_number,
                )
            )
    findings.extend(validate_expected_text(slides, expected_texts or []))
    findings.extend(validate_temporary_notes(slides, temp_notes_path))
    return findings, warnings, total, len(slides)


def parse_arguments(arguments):
    parser = argparse.ArgumentParser()
    parser.add_argument("--deck-dir", required=True)
    parser.add_argument("--content-module", required=True)
    parser.add_argument("--notes-module", required=True)
    parser.add_argument("--renderer-module", required=True)
    parser.add_argument("--slot-minutes", type=float)
    parser.add_argument("--expect-text", action="append", default=[])
    parser.add_argument("--temp-notes")
    return parser.parse_args(arguments)


def main(arguments=None):
    args = parse_arguments(arguments)
    deck_directory = Path(args.deck_dir).expanduser().resolve()
    try:
        content = load_module(args.content_module, deck_directory)
        notes = load_module(args.notes_module, deck_directory)
        renderer = load_module(args.renderer_module, deck_directory)
        temp_notes_path = None
        if args.temp_notes:
            temp_notes_path = Path(args.temp_notes).expanduser()
            if not temp_notes_path.is_absolute():
                temp_notes_path = deck_directory / temp_notes_path
        findings, warnings, total, page_count = validate_deck(
            content,
            notes,
            renderer,
            args.slot_minutes,
            args.expect_text,
            temp_notes_path,
        )
    except Exception as exc:
        print(f"FAIL\n- module loading failed: {exc}")
        return 1
    for warning in warnings:
        print(f"WARNING: {warning}")
    if findings:
        print("FAIL")
        for finding in findings:
            print(f"- {finding}")
        return 1
    total_text = "unknown" if total is None else f"{total:g}"
    print(f"PASS pages={page_count} total_minutes={total_text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
