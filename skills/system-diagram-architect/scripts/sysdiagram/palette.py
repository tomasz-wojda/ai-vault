PALETTE = {
    "blue": ("#9ce6ff", "#2c97bb", "#1c4657"),
    "green": ("#adf0c7", "#1f9e5a", "#0f4d2b"),
    "grey": ("#ddddd8", "#8a8a7e", "#434339"),
    "stone": ("#e9e4d4", "#9a8f6e", "#4a4330"),
    "purple": ("#b8acfb", "#8a7be0", "#231266"),
    "lilac": ("#e4defe", "#8a7be0", "#231266"),
    "yellow": ("#ffe86d", "#a28e26", "#574900"),
    "white": ("#ffffff", "#757575", "#313131"),
    "orange": ("#ffd9a8", "#c98a2e", "#5a3a0a"),
    "red": ("#ffc9c9", "#d64545", "#6b1515"),
    "muted": ("#f5f5f5", "#b5b5b5", "#6b6b6b"),
}
TINTS = ("#f0f5fd", "#f4f2fd", "#fffbed", "#eefaf3", "#fdf1f1", "#f7f7f7")


def resolve(overrides=None):
    merged = dict(PALETTE)
    for name, colours in (overrides or {}).items():
        merged[name] = tuple(colours)
    return merged
