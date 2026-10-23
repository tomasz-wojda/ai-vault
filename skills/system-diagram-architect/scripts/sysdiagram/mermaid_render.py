import re
import shutil
import subprocess

from .model import DATA_RELATIONS

RESERVED = frozenset({"end", "graph", "subgraph", "click", "style", "class", "flowchart"})
EVIDENCE_CLASSES = {
    "inferred": "classDef ev_inferred stroke-dasharray: 5 5",
    "unknown": "classDef ev_unknown stroke-dasharray: 2 4",
}
NODE_DECL = re.compile(r"^\s*([A-Za-z0-9_]+)(\[\(|\[|\()")
EDGE_DECL = re.compile(r"^\s*([A-Za-z0-9_]+)\s+(-->|-\.->)(\|[^|]*\|)?\s*([A-Za-z0-9_]+)\s*$")


def safe_id(value, prefix):
    return f"{prefix}_{re.sub(r'[^A-Za-z0-9_]', '_', value)}"


def _text(value):
    return value.replace('"', "#quot;").replace("<", "#lt;").replace(">", "#gt;").replace("|", "#124;")


def label(title, body, evidence):
    parts = [f"<b>{_text(title)}</b>"]
    if body:
        parts.append(_text(body))
    if evidence in EVIDENCE_CLASSES:
        parts.append(f"<i>{evidence}</i>")
    return "<br/>".join(parts)


def _node_line(node_id, text, kind="rect"):
    if kind == "can":
        return f'{node_id}[("{text}")]'
    if kind == "round":
        return f'{node_id}("{text}")'
    return f'{node_id}["{text}"]'


def _class_lines(palette, members, evidence_members):
    lines = []
    for category in sorted(members):
        fill, stroke, color = palette[category]
        lines.append(f"classDef cat_{category} fill:{fill},stroke:{stroke},color:{color}")
    for evidence in sorted(evidence_members):
        lines.append(EVIDENCE_CLASSES[evidence])
    for category in sorted(members):
        lines.append(f"class {','.join(members[category])} cat_{category}")
    for evidence in sorted(evidence_members):
        lines.append(f"class {','.join(evidence_members[evidence])} ev_{evidence}")
    return lines


def _collect(members, evidence_members, node_id, category, evidence):
    members.setdefault(category, []).append(node_id)
    if evidence in EVIDENCE_CLASSES:
        evidence_members.setdefault(evidence, []).append(node_id)


def render_overview_mermaid(spec, palette, frame_ids=None, board_url=None):
    overview = spec.overview
    lines = ["flowchart LR"]
    members, evidence_members = {}, {}
    for zone in overview.zones:
        lines.append(f'    subgraph {safe_id(zone.id, "z")}["{_text(zone.name)}"]')
        lines.append("        direction TB")
        for node in overview.nodes:
            if node.zone != zone.id:
                continue
            node_id = safe_id(node.id, "n")
            lines.append("        " + _node_line(node_id, label(node.title, node.body, node.evidence), node.shape))
            _collect(members, evidence_members, node_id, node.category, node.evidence)
        lines.append("    end")
    for edge in overview.edges:
        arrow = "-.->" if edge.relation in DATA_RELATIONS else "-->"
        text = f"|{_text(edge.label)}|" if edge.label else ""
        lines.append(f"    {safe_id(edge.from_id, 'n')} {arrow}{text} {safe_id(edge.to_id, 'n')}")
    lines.extend("    " + item for item in _class_lines(palette, members, evidence_members))
    if frame_ids and board_url:
        for node in overview.nodes:
            if node.expands and node.expands in frame_ids:
                lines.append(f'    click {safe_id(node.id, "n")} "{board_url}?moveToWidget={frame_ids[node.expands]}"')
    return "\n".join(lines) + "\n"


def render_frame_mermaid(frame, palette):
    lines = ["flowchart TB"]
    if frame.from_svg is not None:
        lines.append(f'    {safe_id(frame.key, "c")}["<b>{_text(frame.title)}</b><br/>see Miro frame"]')
        return "\n".join(lines) + "\n"
    members, evidence_members = {}, {}
    for a_index, area in enumerate(frame.areas):
        lines.append(f'    subgraph {safe_id(f"{frame.key}_{a_index}", "z")}["{_text(area.name)}"]')
        for c_index, card in enumerate(area.cards):
            node_id = safe_id(f"{frame.key}_{a_index}_{c_index}", "c")
            body = " · ".join(part for part in (card.body, card.foot) if part)
            lines.append("        " + _node_line(node_id, label(card.title, body, card.evidence)))
            _collect(members, evidence_members, node_id, card.category, card.evidence)
        lines.append("    end")
    lines.extend("    " + item for item in _class_lines(palette, members, evidence_members))
    return "\n".join(lines) + "\n"


def check_structure(text):
    errors, declared, edges, depth = [], set(), [], 0
    for number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if stripped.startswith("subgraph "):
            depth += 1
            declared.add(stripped.split()[1].split("[")[0])
            continue
        if stripped == "end":
            depth -= 1
            if depth < 0:
                errors.append(f"line {number}: 'end' without subgraph")
            continue
        edge = EDGE_DECL.match(raw)
        if edge:
            edges.append((number, edge.group(1), edge.group(4)))
            continue
        node = NODE_DECL.match(raw)
        if node and not stripped.startswith(("classDef ", "class ", "click ", "direction ", "flowchart ")):
            node_id = node.group(1)
            if node_id in RESERVED:
                errors.append(f"line {number}: reserved id '{node_id}'")
            if node_id in declared:
                errors.append(f"line {number}: duplicate id '{node_id}'")
            declared.add(node_id)
    if depth > 0:
        errors.append(f"{depth} subgraph block(s) without 'end'")
    for number, source, target in edges:
        for endpoint in (source, target):
            if endpoint not in declared:
                errors.append(f"line {number}: undeclared endpoint '{endpoint}'")
    return errors


def check_with_mmdc(path):
    executable = shutil.which("mmdc")
    if not executable:
        return None, "mmdc not found; structural checks only"
    result = subprocess.run([executable, "-i", str(path), "-o", f"{path}.svg"], capture_output=True, text=True)
    return result.returncode == 0, result.stderr.strip()
