from .markup import attr, escape
from .model import DATA_RELATIONS


def shape(sid, x, y, w, h, content, colours, size=16, bold=False, kind="rect"):
    fill, stroke, color = colours
    weight = ' data-font-weight="bold"' if bold else ""
    extra = ' data-shape="can"' if kind == "can" else ' rx="12"' if kind == "round" else ""
    return (
        f'<rect id="{sid}" x="{x}" y="{y}" width="{w}" height="{h}" data-content="{attr(content)}"{extra} '
        f'fill="{fill}" stroke="{stroke}" stroke-width="2" data-text-color="{color}" data-font-size="{size}"{weight} />'
    )


def panel(sid, x, y, w, h, content, size=16):
    return (
        f'<rect id="{sid}" x="{x}" y="{y}" width="{w}" height="{h}" data-content="{attr(content)}" rx="12" '
        f'fill="#f7f7f7" data-text-color="#313131" data-font-size="{size}" data-text-align="left" '
        f'data-text-align-vertical="top" stroke="none" />'
    )


def zone_rect(sid, x, y, w, h, tint):
    return f'<rect id="{sid}" x="{x}" y="{y}" width="{w}" height="{h}" fill="{tint}" stroke="none" />'


def text(sid, x, y, w, h, value, size, color="#1a1a1a", bold=False):
    weight = ' font-weight="bold"' if bold else ""
    return (
        f'<textArea id="{sid}" x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}" '
        f'font-size="{size}" text-align="left"{weight}>{escape(value)}</textArea>'
    )


def line(sid, start, end, relation, label, start_side, end_side, straight):
    dash = ' stroke-dasharray="5,5"' if relation in DATA_RELATIONS else ""
    content = f' data-content="{attr(label)}"' if label else ""
    return (
        f'<line id="{sid}" x1="0" y1="0" x2="1" y2="1" data-start="{start}" data-end="{end}" stroke="#313131" '
        f'stroke-width="2" data-arrow="end"{dash} data-shape="{"straight" if straight else "elbowed"}" '
        f'data-start-side="{start_side}" data-end-side="{end_side}"{content} />'
    )


def frame_group(prefix, title, x, y, width, height, items):
    head = [
        f'<g id="{prefix}f" transform="translate({x},{y})" data-frame="{attr(title)}">',
        f'<rect data-type="frame" x="0" y="0" width="{width}" height="{height}" fill="#ffffff" data-title="{attr(title)}" />',
    ]
    return "\n".join(head + list(items) + ["</g>"])


def header(prefix, title, subtitle, legend, palette):
    items = [
        text(f"{prefix}t", 64, 56, 2800, 96, title, 67, bold=True),
        text(f"{prefix}s", 64, 168, 2800, 31, subtitle, 22, color="#595959"),
    ]
    for index, entry in enumerate(legend):
        items.append(shape(f"{prefix}l{index}", 64 + index * 332, 236, 300, 64, entry.label, palette[entry.category], bold=True))
    return items
