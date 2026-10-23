import json
import re
from pathlib import Path

from .model import (
    EVIDENCE,
    RELATIONS,
    SCHEMA,
    SHAPES,
    Area,
    Card,
    Edge,
    Frame,
    LegendEntry,
    Node,
    Note,
    Overview,
    Spec,
    Zone,
)
from .palette import resolve

FRAME_KEY = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class SpecError(Exception):
    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = list(errors)


def _legend(items):
    return [LegendEntry(item.get("category", ""), item.get("label", "")) for item in items or []]


def _card(item):
    return Card(
        category=item.get("category", ""),
        title=item.get("title", ""),
        body=item.get("body", ""),
        foot=item.get("foot", ""),
        span=item.get("span", 1),
        evidence=item.get("evidence", ""),
        sources=list(item.get("sources", [])),
    )


def _frame(item, base_dir):
    from_svg = item.get("from_svg")
    return Frame(
        key=item.get("key", ""),
        title=item.get("title", ""),
        subtitle=item.get("subtitle", ""),
        legend=_legend(item.get("legend")),
        areas=[Area(area.get("name", ""), [_card(card) for card in area.get("cards", [])]) for area in item.get("areas", [])],
        from_svg=(base_dir / from_svg) if from_svg else None,
    )


def _overview(item):
    return Overview(
        title=item.get("title", ""),
        subtitle=item.get("subtitle", ""),
        legend=_legend(item.get("legend")),
        zones=[
            Zone(zone.get("id", ""), zone.get("name", ""), zone.get("subtitle", ""), zone.get("lane", 0), zone.get("columns", 2))
            for zone in item.get("zones", [])
        ],
        nodes=[
            Node(
                id=node.get("id", ""),
                zone=node.get("zone", ""),
                title=node.get("title", ""),
                body=node.get("body", ""),
                category=node.get("category", ""),
                shape=node.get("shape", "rect"),
                evidence=node.get("evidence", ""),
                sources=list(node.get("sources", [])),
                expands=node.get("expands"),
            )
            for node in item.get("nodes", [])
        ],
        edges=[
            Edge(
                from_id=edge.get("from", ""),
                to_id=edge.get("to", ""),
                relation=edge.get("relation", ""),
                label=edge.get("label") or edge.get("relation", "").replace("_", " "),
                evidence=edge.get("evidence", ""),
                sources=list(edge.get("sources", [])),
            )
            for edge in item.get("edges", [])
        ],
        notes=[Note(note.get("title", ""), list(note.get("lines", []))) for note in item.get("notes", [])],
    )


def parse_spec(data, base_dir):
    return Spec(
        title=data.get("title", ""),
        overview=_overview(data.get("overview", {})),
        frames=[_frame(item, base_dir) for item in data.get("frames", [])],
        categories=data.get("categories", {}),
        base_dir=base_dir,
        schema=data.get("schema", ""),
    )


def _check_claim(errors, path, evidence, sources):
    if evidence not in EVIDENCE:
        errors.append(f"{path}.evidence: '{evidence}' not in {', '.join(EVIDENCE)}")
    elif evidence != "unknown" and not sources:
        errors.append(f"{path}.sources: required unless evidence is unknown")


def _check_legend(errors, path, legend, palette):
    for index, entry in enumerate(legend):
        if entry.category not in palette:
            errors.append(f"{path}.legend[{index}].category: unknown category '{entry.category}'")


def _validate_frames(spec, palette, errors):
    seen = set()
    for index, frame in enumerate(spec.frames):
        path = f"frames[{index}]"
        if not FRAME_KEY.match(frame.key):
            errors.append(f"{path}.key: '{frame.key}' must match {FRAME_KEY.pattern}")
        if frame.key in seen:
            errors.append(f"{path}.key: duplicate frame key '{frame.key}'")
        seen.add(frame.key)
        if not frame.title:
            errors.append(f"{path}.title: required")
        if not frame.subtitle:
            errors.append(f"{path}.subtitle: required")
        _check_legend(errors, path, frame.legend, palette)
        if frame.from_svg is not None:
            if not frame.from_svg.is_file():
                errors.append(f"{path}.from_svg: file not found '{frame.from_svg}'")
            continue
        if not frame.areas:
            errors.append(f"{path}.areas: required unless from_svg is set")
        names = set()
        for a_index, area in enumerate(frame.areas):
            a_path = f"{path}.areas[{a_index}]"
            if area.name in names:
                errors.append(f"{a_path}.name: duplicate area name '{area.name}'")
            names.add(area.name)
            if not area.cards:
                errors.append(f"{a_path}.cards: required")
            for c_index, card in enumerate(area.cards):
                c_path = f"{a_path}.cards[{c_index}]"
                if card.category not in palette:
                    errors.append(f"{c_path}.category: unknown category '{card.category}'")
                if not card.title:
                    errors.append(f"{c_path}.title: required")
                if card.span not in (1, 2):
                    errors.append(f"{c_path}.span: {card.span} must be 1 or 2")
                _check_claim(errors, c_path, card.evidence, card.sources)
    return seen


def _validate_overview(spec, palette, frame_keys, errors):
    overview = spec.overview
    if not overview.title:
        errors.append("overview.title: required")
    _check_legend(errors, "overview", overview.legend, palette)
    zone_ids = set()
    for index, zone in enumerate(overview.zones):
        path = f"overview.zones[{index}]"
        if not zone.id:
            errors.append(f"{path}.id: required")
        if zone.id in zone_ids:
            errors.append(f"{path}.id: duplicate zone id '{zone.id}'")
        zone_ids.add(zone.id)
        if not isinstance(zone.lane, int) or zone.lane < 0:
            errors.append(f"{path}.lane: {zone.lane} must be an integer >= 0")
        if not isinstance(zone.columns, int) or not 1 <= zone.columns <= 4:
            errors.append(f"{path}.columns: {zone.columns} must be 1 to 4")
    node_ids = set()
    for index, node in enumerate(overview.nodes):
        path = f"overview.nodes[{index}]"
        if not node.id:
            errors.append(f"{path}.id: required")
        if node.id in node_ids:
            errors.append(f"{path}.id: duplicate node id '{node.id}'")
        node_ids.add(node.id)
        if node.zone not in zone_ids:
            errors.append(f"{path}.zone: unknown zone '{node.zone}'")
        if not node.title:
            errors.append(f"{path}.title: required")
        if node.category not in palette:
            errors.append(f"{path}.category: unknown category '{node.category}'")
        if node.shape not in SHAPES:
            errors.append(f"{path}.shape: '{node.shape}' not in {', '.join(SHAPES)}")
        if node.expands is not None and node.expands not in frame_keys:
            errors.append(f"{path}.expands: unknown frame '{node.expands}'")
        _check_claim(errors, path, node.evidence, node.sources)
    for index, edge in enumerate(overview.edges):
        path = f"overview.edges[{index}]"
        for end, value in (("from", edge.from_id), ("to", edge.to_id)):
            if value not in node_ids:
                errors.append(f"{path}.{end}: unknown node '{value}'")
        if edge.from_id == edge.to_id:
            errors.append(f"{path}: self-edge on '{edge.from_id}'")
        if edge.relation not in RELATIONS:
            errors.append(f"{path}.relation: '{edge.relation}' not in vocabulary")
        _check_claim(errors, path, edge.evidence, edge.sources)
    for index, note in enumerate(overview.notes):
        if not note.title:
            errors.append(f"overview.notes[{index}].title: required")


def validate(spec):
    errors = []
    if spec.schema != SCHEMA:
        errors.append(f"schema: '{spec.schema}' must be '{SCHEMA}'")
    if not spec.title:
        errors.append("title: required")
    palette = resolve(spec.categories)
    frame_keys = _validate_frames(spec, palette, errors)
    _validate_overview(spec, palette, frame_keys, errors)
    return errors


def load_spec(path):
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpecError([f"{path}: {exc}"]) from exc
    spec = parse_spec(data, path.resolve().parent)
    errors = validate(spec)
    if errors:
        raise SpecError(errors)
    return spec
