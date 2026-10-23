import html

EVIDENCE_MARKERS = ("inferred", "unknown")


def attr(text):
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def escape(text):
    return html.escape(text, quote=False)


def evidence_foot(foot, evidence):
    if evidence not in EVIDENCE_MARKERS:
        return foot
    return f"{foot} · {evidence}" if foot else evidence


def card_markup(title, body, foot, evidence, title_markup=None):
    parts = [f"<b>{title_markup if title_markup is not None else escape(title)}</b>"]
    if body:
        parts.append(escape(body))
    footer = evidence_foot(foot, evidence)
    if footer:
        parts.append(f"<i>{escape(footer)}</i>")
    return "<br />".join(parts)


def anchor(url, inner):
    return f'<a href="{attr(url)}">{inner}</a>'
