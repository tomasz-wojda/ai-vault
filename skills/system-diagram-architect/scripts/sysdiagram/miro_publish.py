import json
import re
from pathlib import Path

from .miro_detail import FRAME_W, render_detail, render_from_svg
from .miro_overview import layout_overview
from .miro_shapes import frame_group

GRID_COLUMNS = 4
GRID_STRIDE_X = 3232
GRID_GAP_Y = 320
GRID_OFFSET = 256
BATCH_LIMIT = 90000
CALL_LIMIT = 200000
SVG_OPEN = '<svg xmlns="http://www.w3.org/2000/svg">'
FRAME_ID = re.compile(r'<g id="(f\d+f)"[^>]*data-miro-id="(\d+)"')


def svg_document(groups):
    return SVG_OPEN + "\n" + "\n".join(groups) + "\n</svg>\n"


def grid_positions(heights, x0):
    positions, row_y, row_h = [], 0, 0
    for number, height in enumerate(heights):
        col = number % GRID_COLUMNS
        if col == 0 and number:
            row_y += row_h + GRID_GAP_Y
            row_h = 0
        positions.append((x0 + col * GRID_STRIDE_X, row_y))
        row_h = max(row_h, height)
    return positions


def build_detail_groups(spec, palette):
    rendered = []
    for number, frame in enumerate(spec.frames):
        prefix = f"f{number:02d}"
        if frame.from_svg is not None:
            items, height = render_from_svg(prefix, frame)
        else:
            items, height = render_detail(prefix, frame, palette)
        rendered.append((frame, prefix, items, height))
    x0 = layout_overview(spec.overview, len(spec.frames))["width"] + GRID_OFFSET
    positions = grid_positions([height for _, _, _, height in rendered], x0)
    groups = []
    for (frame, prefix, items, height), (x, y) in zip(rendered, positions):
        group = frame_group(prefix, frame.title, x, y, FRAME_W, height, items)
        entry = {
            "key": frame.key,
            "title": frame.title,
            "local_id": f"{prefix}f",
            "x": x,
            "y": y,
            "width": FRAME_W,
            "height": height,
            "items": len(items),
        }
        groups.append((frame.key, prefix, group, entry))
    return groups


def batch_groups(groups, limit=BATCH_LIMIT):
    batches, current, size = [], [], 0
    for item in groups:
        group = item[2]
        if current and size + len(group) > limit:
            batches.append(current)
            current, size = [], 0
        current.append(item)
        size += len(group)
    if current:
        batches.append(current)
    return batches


def write_detail_outputs(out_dir, groups, limit=BATCH_LIMIT):
    miro_dir = Path(out_dir) / "miro"
    frames_dir = miro_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for key, _, group, _ in groups:
        (frames_dir / f"{key}.svg").write_text(svg_document([group]), encoding="utf-8")
    summary = []
    for number, batch in enumerate(batch_groups(groups, limit), 1):
        document = svg_document([item[2] for item in batch])
        if len(document) > CALL_LIMIT:
            raise ValueError(f"batch-{number}.svg is {len(document)} chars, over {CALL_LIMIT}")
        path = miro_dir / f"batch-{number}.svg"
        path.write_text(document, encoding="utf-8")
        summary.append((path.name, len(document), [item[0] for item in batch]))
    (miro_dir / "layout.json").write_text(json.dumps([item[3] for item in groups], indent=2) + "\n", encoding="utf-8")
    return summary


def extract_frame_ids(layout, result_paths):
    local_to_key = {entry["local_id"]: entry["key"] for entry in layout}
    ids = {}
    for path in result_paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for local, miro_id in FRAME_ID.findall(data.get("result_svg", "")):
            if local in local_to_key:
                ids[local_to_key[local]] = miro_id
    missing = [entry["key"] for entry in layout if entry["key"] not in ids]
    if missing:
        raise ValueError(f"missing frame ids: {', '.join(missing)}")
    return ids


def _frame_body(path):
    source = Path(path).read_text(encoding="utf-8")
    return source.split(SVG_OPEN, 1)[1].rsplit("</svg>", 1)[0].strip()


def write_snapshot(out_dir):
    miro_dir = Path(out_dir) / "miro"
    layout = json.loads((miro_dir / "layout.json").read_text(encoding="utf-8"))
    paths = [miro_dir / "frames" / "overview.svg"] + [miro_dir / "frames" / f"{entry['key']}.svg" for entry in layout]
    document = svg_document([_frame_body(path) for path in paths])
    target = miro_dir / "snapshot.svg"
    target.write_text(document, encoding="utf-8")
    return target, len(document)
