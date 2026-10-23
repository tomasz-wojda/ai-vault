from .model import EVIDENCE


def _claims(spec):
    for f_index, frame in enumerate(spec.frames):
        for a_index, area in enumerate(frame.areas):
            for c_index, card in enumerate(area.cards):
                yield {
                    "kind": "card",
                    "path": f"frames[{f_index}].areas[{a_index}].cards[{c_index}]",
                    "frame": frame.key,
                    "title": card.title,
                    "evidence": card.evidence,
                    "sources": card.sources,
                }
    for index, node in enumerate(spec.overview.nodes):
        yield {
            "kind": "node",
            "path": f"overview.nodes[{index}]",
            "title": node.title,
            "evidence": node.evidence,
            "sources": node.sources,
        }
    for index, edge in enumerate(spec.overview.edges):
        yield {
            "kind": "edge",
            "path": f"overview.edges[{index}]",
            "title": f"{edge.from_id} {edge.relation} {edge.to_id}",
            "evidence": edge.evidence,
            "sources": edge.sources,
        }


def build_ledger(spec):
    claims = list(_claims(spec))
    counts = {label: sum(1 for claim in claims if claim["evidence"] == label) for label in EVIDENCE}
    return {
        "title": spec.title,
        "claims": claims,
        "counts": counts,
        "unknowns": [claim["path"] for claim in claims if claim["evidence"] == "unknown"],
        "inferred": [claim["path"] for claim in claims if claim["evidence"] == "inferred"],
    }
