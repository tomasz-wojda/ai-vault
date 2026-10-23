import math

LINE_HEIGHT = 22
CARD_SIZES = {1: (420, 160), 2: (872, 160)}
NODE_SIZE = (320, 120)


def estimate_lines(segments, width, font_size=16):
    per_line = max(1, math.floor((width - 24) / (font_size * 0.53)))
    return sum(max(1, math.ceil(len(segment) / per_line)) for segment in segments if segment)


def _overflows(segments, width, height):
    lines = estimate_lines(segments, width)
    return lines if lines * LINE_HEIGHT > height - 16 else 0


def lint_spec(spec):
    warnings = []
    for f_index, frame in enumerate(spec.frames):
        for a_index, area in enumerate(frame.areas):
            for c_index, card in enumerate(area.cards):
                width, height = CARD_SIZES.get(card.span, CARD_SIZES[1])
                lines = _overflows([card.title, card.body, card.foot], width, height)
                if lines:
                    warnings.append(f"frames[{f_index}].areas[{a_index}].cards[{c_index}]: about {lines} lines exceed {width}x{height}")
    for n_index, node in enumerate(spec.overview.nodes):
        lines = _overflows([node.title, node.body], *NODE_SIZE)
        if lines:
            warnings.append(f"overview.nodes[{n_index}]: about {lines} lines exceed {NODE_SIZE[0]}x{NODE_SIZE[1]}")
    return warnings
