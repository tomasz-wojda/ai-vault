import html
import re

from .markup import card_markup, escape
from .miro_shapes import header, shape, text, zone_rect
from .palette import TINTS

FRAME_W = 2976
COLUMN_X = (64, 1520)
ZONE_W = 1392
CARD_W, CARD_H = 420, 160
STEP_X, STEP_Y = 452, 192
ZONE_TOP = 360
ZONE_HEAD = 90
ZONE_TAIL = 2
ZONE_GAP = 48
GRID_COLUMNS = 3


def place_cards(cards):
    slots, row, col = [], 0, 0
    for card in cards:
        span = card.span
        if col + span > GRID_COLUMNS:
            row, col = row + 1, 0
        slots.append((row, col, span))
        col += span
        if col >= GRID_COLUMNS:
            row, col = row + 1, 0
    rows = max(r for r, _, _ in slots) + 1 if slots else 0
    return slots, rows


def zone_height(rows):
    return ZONE_HEAD + rows * STEP_Y - (STEP_Y - CARD_H) + ZONE_TAIL + 32


def layout_areas(areas):
    bottoms = [ZONE_TOP, ZONE_TOP]
    placed = []
    for index, area in enumerate(areas):
        slots, rows = place_cards(area.cards)
        height = zone_height(rows)
        column = 0 if bottoms[0] <= bottoms[1] else 1
        placed.append((index, area, slots, COLUMN_X[column], bottoms[column], height))
        bottoms[column] += height + ZONE_GAP
    return placed, max(bottoms) - ZONE_GAP + 70


def render_detail(prefix, frame, palette):
    placed, height = layout_areas(frame.areas)
    zones, titles, cards = [], [], []
    for index, area, slots, x, y, h in placed:
        zones.append(zone_rect(f"{prefix}z{index}", x, y, ZONE_W, h, TINTS[index % len(TINTS)]))
        titles.append(text(f"{prefix}h{index}", x + 32, y + 24, 1300, 47, area.name, 33, bold=True))
        for number, (card, (row, col, span)) in enumerate(zip(area.cards, slots)):
            width = CARD_W * span + (STEP_X - CARD_W) * (span - 1)
            content = card_markup(card.title, card.body, card.foot, card.evidence)
            cards.append(
                shape(
                    f"{prefix}c{index}_{number}",
                    x + 32 + col * STEP_X,
                    y + ZONE_HEAD + row * STEP_Y,
                    width,
                    CARD_H,
                    content,
                    palette[card.category],
                )
            )
    return zones + titles + header(prefix, frame.title, frame.subtitle, frame.legend, palette) + cards, height


def render_from_svg(prefix, frame):
    source = frame.from_svg.read_text(encoding="utf-8")
    frame_rect = re.search(r'<rect data-type="frame"[^>]*/>', source)
    body = source[frame_rect.end():].rsplit("</g>", 1)[0]
    original_title = re.search(r'data-title="([^"]*)"', frame_rect.group(0))
    body = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{prefix}{m.group(1)}"', body)
    body = re.sub(r'\bdata-(start|end)="([^"]+)"', lambda m: f'data-{m.group(1)}="{prefix}{m.group(2)}"', body)
    if original_title and original_title.group(1):
        old = escape(html.unescape(original_title.group(1)))
        body = body.replace(f">{old}</textArea>", f">{escape(frame.title)}</textArea>")
    height = int(float(re.search(r'height="([\d.]+)"', frame_rect.group(0)).group(1)))
    return [item for item in body.strip().splitlines() if item.strip()], height
