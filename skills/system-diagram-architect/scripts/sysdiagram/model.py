from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

SCHEMA = "system-diagram/1"
EVIDENCE = ("observed", "derived", "inferred", "unknown")
RELATIONS = (
    "calls",
    "runs",
    "loads",
    "imports",
    "reads",
    "writes",
    "persists_to",
    "sends",
    "invokes",
    "handles",
    "exposes",
    "contains",
    "configures",
    "observed_as",
)
DATA_RELATIONS = frozenset({"reads", "writes", "persists_to", "configures"})
SHAPES = ("rect", "can", "round")


@dataclass
class LegendEntry:
    category: str
    label: str


@dataclass
class Card:
    category: str
    title: str
    body: str
    foot: str
    span: int
    evidence: str
    sources: list


@dataclass
class Area:
    name: str
    cards: list


@dataclass
class Frame:
    key: str
    title: str
    subtitle: str
    legend: list
    areas: list
    from_svg: Optional[Path] = None


@dataclass
class Zone:
    id: str
    name: str
    subtitle: str
    lane: int
    columns: int


@dataclass
class Node:
    id: str
    zone: str
    title: str
    body: str
    category: str
    shape: str
    evidence: str
    sources: list
    expands: Optional[str] = None


@dataclass
class Edge:
    from_id: str
    to_id: str
    relation: str
    label: str
    evidence: str
    sources: list


@dataclass
class Note:
    title: str
    lines: list


@dataclass
class Overview:
    title: str
    subtitle: str
    legend: list
    zones: list
    nodes: list
    edges: list
    notes: list


@dataclass
class Spec:
    title: str
    overview: Overview
    frames: list
    categories: dict = field(default_factory=dict)
    base_dir: Path = Path(".")
    schema: str = SCHEMA
