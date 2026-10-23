import math
import re

from .markup import anchor, card_markup, escape
from .miro_shapes import header, line, panel, shape, text, zone_rect
from .palette import TINTS

NODE_W, NODE_H = 320, 120
NODE_GAP_X, NODE_GAP_Y = 32, 48
ZONE_PAD = 32
ZONE_HEAD = 96
LANE_GAP = 96
ZONE_GAP = 48
ZONE_TOP = 360
MARGIN = 64
NOTE_W, NOTE_H = 384, 280
NOTE_STRIDE = 416
INDEX_ROW = 28


def safe_id(value):
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def zone_width(columns):
    return 2 * ZONE_PAD + columns * NODE_W + (columns - 1) * NODE_GAP_X


def zone_height(node_count, columns):
    rows = max(1, math.ceil(node_count / columns))
    return ZONE_HEAD + rows * (NODE_H + NODE_GAP_Y) - NODE_GAP_Y + ZONE_PAD


def _lane_positions(zones):
    lanes = sorted({zone.lane for zone in zones})
    positions, x = {}, MARGIN
    for lane in lanes:
        width = max(zone_width(zone.columns) for zone in zones if zone.lane == lane)
        positions[lane] = (x, width)
        x += width + LANE_GAP
    return positions


def layout_overview(overview, frame_count):
    lanes = _lane_positions(overview.zones)
    members = {zone.id: [node for node in overview.nodes if node.zone == zone.id] for zone in overview.zones}
    lane_bottoms = {lane: ZONE_TOP for lane in lanes}
    zone_rects, node_rects = {}, {}
    for zone in overview.zones:
        x, _ = lanes[zone.lane]
        y = lane_bottoms[zone.lane]
        width = zone_width(zone.columns)
        height = zone_height(len(members[zone.id]), zone.columns)
        zone_rects[zone.id] = (x, y, width, height)
        lane_bottoms[zone.lane] = y + height + ZONE_GAP
        for index, node in enumerate(members[zone.id]):
            row, col = divmod(index, zone.columns)
            node_rects[node.id] = (
                x + ZONE_PAD + col * (NODE_W + NODE_GAP_X),
                y + ZONE_HEAD + row * (NODE_H + NODE_GAP_Y),
                NODE_W,
                NODE_H,
            )
    zones_bottom = max((y + h for _, y, _, h in zone_rects.values()), default=ZONE_TOP)
    panel_y = zones_bottom + MARGIN
    note_rects = [(MARGIN + index * NOTE_STRIDE, panel_y, NOTE_W, NOTE_H) for index in range(len(overview.notes))]
    index_rect = None
    if frame_count:
        index_rect = (MARGIN + len(note_rects) * NOTE_STRIDE, panel_y, NOTE_W, max(NOTE_H, 64 + INDEX_ROW * frame_count))
    panels = note_rects + ([index_rect] if index_rect else [])
    right = max([x + w for x, _, w, _ in zone_rects.values()] + [x + w for x, _, w, _ in panels] + [MARGIN])
    bottom = max([zones_bottom] + [y + h for _, y, _, h in panels])
    return {
        "zones": zone_rects,
        "nodes": node_rects,
        "notes": note_rects,
        "index": index_rect,
        "width": right + MARGIN,
        "height": bottom + MARGIN,
    }


def connector_sides(src_zone, dst_zone, src_rect, dst_rect):
    src_cy = src_rect[1] + src_rect[3] / 2
    dst_cy = dst_rect[1] + dst_rect[3] / 2
    straight = src_cy == dst_cy
    if dst_zone.lane > src_zone.lane:
        return "right", "left", straight
    if dst_zone.lane < src_zone.lane:
        return "left", "right", straight
    if dst_cy - src_cy > src_rect[3] / 2:
        return "bottom", "top", straight
    if src_cy - dst_cy > src_rect[3] / 2:
        return "top", "bottom", straight
    if dst_rect[0] > src_rect[0]:
        return "right", "left", straight
    return "left", "right", straight


def _frame_link(board_url, frame_ids, key):
    if board_url and frame_ids and key in frame_ids:
        return f"{board_url}?moveToWidget={frame_ids[key]}"
    return None


def _node_content(node, board_url, frame_ids):
    url = _frame_link(board_url, frame_ids, node.expands) if node.expands else None
    title_markup = anchor(url, escape(node.title)) if url else None
    return card_markup(node.title, node.body, "", node.evidence, title_markup=title_markup)


def _index_content(frames, board_url, frame_ids):
    lines = ["<b>Detail frames</b>"]
    for frame in frames:
        url = _frame_link(board_url, frame_ids, frame.key)
        lines.append(anchor(url, escape(frame.title)) if url else escape(frame.title))
    return "<br />".join(lines)


def render_overview(spec, palette, frame_ids=None, board_url=None):
    overview = spec.overview
    layout = layout_overview(overview, len(spec.frames))
    zones_by_id = {zone.id: zone for zone in overview.zones}
    nodes_by_id = {node.id: node for node in overview.nodes}
    backgrounds, lines, nodes, panels = [], [], [], []
    for index, zone in enumerate(overview.zones):
        x, y, w, h = layout["zones"][zone.id]
        backgrounds.append(zone_rect(f"ovz{index}", x, y, w, h, TINTS[index % len(TINTS)]))
        backgrounds.append(text(f"ovzh{index}", x + 32, y + 24, w - 64, 47, zone.name, 33, bold=True))
        if zone.subtitle:
            backgrounds.append(text(f"ovzs{index}", x + 32, y + 64, w - 64, 26, zone.subtitle, 18, color="#595959"))
    for index, edge in enumerate(overview.edges):
        source, target = nodes_by_id[edge.from_id], nodes_by_id[edge.to_id]
        start_side, end_side, straight = connector_sides(
            zones_by_id[source.zone], zones_by_id[target.zone], layout["nodes"][source.id], layout["nodes"][target.id]
        )
        lines.append(line(f"ove{index}", f"ovn_{safe_id(source.id)}", f"ovn_{safe_id(target.id)}", edge.relation, edge.label, start_side, end_side, straight))
    for node in overview.nodes:
        x, y, w, h = layout["nodes"][node.id]
        nodes.append(shape(f"ovn_{safe_id(node.id)}", x, y, w, h, _node_content(node, board_url, frame_ids), palette[node.category], kind=node.shape))
    for index, (note, (x, y, w, h)) in enumerate(zip(overview.notes, layout["notes"])):
        content = "<br />".join([f"<b>{escape(note.title)}</b>"] + [escape(item) for item in note.lines])
        panels.append(panel(f"ovp{index}", x, y, w, h, content))
    if layout["index"]:
        x, y, w, h = layout["index"]
        panels.append(panel("ovx", x, y, w, h, _index_content(spec.frames, board_url, frame_ids), size=14))
    items = backgrounds + header("ov", overview.title, overview.subtitle, overview.legend, palette) + lines + nodes + panels
    return items, layout["width"], layout["height"]
