#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PROXY = (
    "/api/v1/namespaces/monitoring/services/prometheus-server:80/proxy/api/v1/query_range"
)
DROPPED_LABELS = ("__name__", "job")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a Prometheus range query through the kubectl service proxy "
        "and save it as incident evidence."
    )
    parser.add_argument("--context", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--expr", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--proxy", default=DEFAULT_PROXY)
    return parser.parse_args(argv)


def query_range(context: str, proxy: str, expr: str, start: str, end: str, step: str) -> dict:
    params = urllib.parse.urlencode({"query": expr, "start": start, "end": end, "step": step})
    out = subprocess.run(
        ["kubectl", "--context", context, "get", "--raw", f"{proxy}?{params}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(out)


def render(result: dict) -> str:
    lines = []
    for series in result["data"]["result"]:
        label = ",".join(
            f"{key}={value}"
            for key, value in sorted(series["metric"].items())
            if key not in DROPPED_LABELS
        )
        points = " ".join(
            f"{datetime.fromtimestamp(float(stamp), timezone.utc).strftime('%m-%dT%H:%M')}"
            f"={float(value):.4g}"
            for stamp, value in series["values"]
        )
        lines.append(f"{label or 'total'}: {points}")
    return "\n".join(lines)


def write_evidence(
    out: Path, name: str, expr: str, start: str, end: str, step: str, text: str
) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.txt"
    path.write_text(f"QUERY: {expr}\nRANGE: {start} {end} step={step}\n{text}\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = query_range(args.context, args.proxy, args.expr, args.start, args.end, args.step)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"query failed: {error}", file=sys.stderr)
        return 2
    text = render(result)
    write_evidence(args.out, args.name, args.expr, args.start, args.end, args.step, text)
    print(f"== {args.name}\n{text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
