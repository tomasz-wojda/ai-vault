#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_OUT = Path("~/.cache/ai-vault/ca-bundle.pem")
KEYCHAINS = (
    "/Library/Keychains/System.keychain",
    "/System/Library/Keychains/SystemRootCertificates.keychain",
    "~/Library/Keychains/login.keychain-db",
)
CERTIFICATE_MARKER = "-----BEGIN CERTIFICATE-----"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export macOS keychain certificates into one PEM bundle for SSL_CERT_FILE."
    )
    parser.add_argument("--out", default=DEFAULT_OUT, type=Path)
    return parser.parse_args(argv)


def export_certificates(keychains: tuple[str, ...]) -> str:
    paths = [str(Path(keychain).expanduser()) for keychain in keychains]
    return subprocess.run(
        ["security", "find-certificate", "-a", "-p", *paths],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def write_bundle(path: Path, pem: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pem, encoding="utf-8")
    return pem.count(CERTIFICATE_MARKER)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        pem = export_certificates(KEYCHAINS)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"security find-certificate failed: {error}", file=sys.stderr)
        return 2
    if CERTIFICATE_MARKER not in pem:
        print("no certificates exported", file=sys.stderr)
        return 2
    out = args.out.expanduser()
    count = write_bundle(out, pem)
    print(f"wrote {count} certificates to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
