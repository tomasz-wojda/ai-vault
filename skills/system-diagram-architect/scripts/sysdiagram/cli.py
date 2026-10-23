import argparse
import json
import sys
from pathlib import Path

from .ledger import build_ledger
from .mermaid_render import check_structure, check_with_mmdc, render_frame_mermaid, render_overview_mermaid
from .miro_overview import render_overview
from .miro_publish import CALL_LIMIT, build_detail_groups, extract_frame_ids, svg_document, write_detail_outputs, write_snapshot
from .miro_shapes import frame_group
from .model import EVIDENCE
from .palette import resolve
from .spec_loader import SpecError, load_spec
from .text_fit import lint_spec


def _load(path):
    try:
        return load_spec(path)
    except SpecError as exc:
        for error in exc.errors:
            print(f"error: {error}", file=sys.stderr)
        return None


def _frame_ids(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def cmd_validate(args):
    spec = _load(args.spec)
    if spec is None:
        return 1
    cards = [card for frame in spec.frames for area in frame.areas for card in area.cards]
    claims = cards + spec.overview.nodes + spec.overview.edges
    counts = ", ".join(f"{label} {sum(1 for claim in claims if claim.evidence == label)}" for label in EVIDENCE)
    print(
        f"frames {len(spec.frames)}, areas {sum(len(frame.areas) for frame in spec.frames)}, cards {len(cards)}, "
        f"zones {len(spec.overview.zones)}, nodes {len(spec.overview.nodes)}, edges {len(spec.overview.edges)}"
    )
    print(f"evidence: {counts}")
    warnings = lint_spec(spec)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 1 if warnings and args.strict else 0


def cmd_mermaid(args):
    spec = _load(args.spec)
    if spec is None:
        return 1
    palette = resolve(spec.categories)
    out_dir = Path(args.out) / "mermaid"
    out_dir.mkdir(parents=True, exist_ok=True)
    documents = [("overview", render_overview_mermaid(spec, palette, _frame_ids(args.frame_ids), args.board_url))]
    documents += [(frame.key, render_frame_mermaid(frame, palette)) for frame in spec.frames]
    status = 0
    for key, text in documents:
        path = out_dir / f"{key}.mmd"
        path.write_text(text, encoding="utf-8")
        errors = check_structure(text)
        for error in errors:
            print(f"error: {path.name}: {error}", file=sys.stderr)
        status = 1 if errors else status
        message = "ok"
        if args.check:
            ok, detail = check_with_mmdc(path)
            message = detail if ok is None else ("mmdc ok" if ok else f"mmdc failed: {detail}")
            status = 1 if ok is False else status
        print(f"{path} {message}")
    return status


def cmd_miro_details(args):
    spec = _load(args.spec)
    if spec is None:
        return 1
    groups = build_detail_groups(spec, resolve(spec.categories))
    for name, size, keys in write_detail_outputs(args.out, groups):
        print(f"{name} {size} chars: {', '.join(keys)}")
    return 0


def cmd_miro_ids(args):
    layout = json.loads(Path(args.layout).read_text(encoding="utf-8"))
    try:
        ids = extract_frame_ids(layout, args.results)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    Path(args.out).write_text(json.dumps(ids, indent=2) + "\n", encoding="utf-8")
    print(f"{args.out}: {len(ids)} frame ids")
    return 0


def cmd_miro_overview(args):
    spec = _load(args.spec)
    if spec is None:
        return 1
    items, width, height = render_overview(spec, resolve(spec.categories), _frame_ids(args.frame_ids), args.board_url)
    document = svg_document([frame_group("ov", spec.overview.title, 0, 0, width, height, items)])
    frames_dir = Path(args.out) / "miro" / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    (frames_dir / "overview.svg").write_text(document, encoding="utf-8")
    print(f"{frames_dir / 'overview.svg'} {len(document)} chars, {width}x{height}")
    if len(document) > CALL_LIMIT:
        print(f"error: overview is over {CALL_LIMIT} chars", file=sys.stderr)
        return 1
    target, size = write_snapshot(args.out)
    print(f"{target} {size} chars")
    return 0


def cmd_ledger(args):
    spec = _load(args.spec)
    if spec is None:
        return 1
    ledger = build_ledger(spec)
    target = Path(args.out) / "ledger.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(f"{target}: {', '.join(f'{k} {v}' for k, v in ledger['counts'].items())}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="build_diagram.py")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("spec")
    validate.add_argument("--strict", action="store_true")
    validate.set_defaults(handler=cmd_validate)
    mermaid = commands.add_parser("mermaid")
    mermaid.add_argument("spec")
    mermaid.add_argument("--out", required=True)
    mermaid.add_argument("--board-url")
    mermaid.add_argument("--frame-ids")
    mermaid.add_argument("--check", action="store_true")
    mermaid.set_defaults(handler=cmd_mermaid)
    details = commands.add_parser("miro-details")
    details.add_argument("spec")
    details.add_argument("--out", required=True)
    details.set_defaults(handler=cmd_miro_details)
    ids = commands.add_parser("miro-ids")
    ids.add_argument("--layout", required=True)
    ids.add_argument("--results", nargs="+", required=True)
    ids.add_argument("--out", required=True)
    ids.set_defaults(handler=cmd_miro_ids)
    overview = commands.add_parser("miro-overview")
    overview.add_argument("spec")
    overview.add_argument("--out", required=True)
    overview.add_argument("--board-url", required=True)
    overview.add_argument("--frame-ids", required=True)
    overview.set_defaults(handler=cmd_miro_overview)
    ledger = commands.add_parser("ledger")
    ledger.add_argument("spec")
    ledger.add_argument("--out", required=True)
    ledger.set_defaults(handler=cmd_ledger)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.handler(args)
