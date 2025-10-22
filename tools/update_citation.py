#!/usr/bin/env python3
"""Utility to bump version and release date in CITATION.cff."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import yaml


def update_citation(version: str, citation_path: Path) -> None:
    data = yaml.safe_load(citation_path.read_text())
    data["version"] = version
    data["date-released"] = dt.date.today().isoformat()
    citation_path.write_text(yaml.safe_dump(data, sort_keys=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Update version and release date in CITATION.cff")
    parser.add_argument("--version", required=True, help="Version string, e.g. 0.2.0")
    parser.add_argument(
        "--file",
        default="CITATION.cff",
        help="Path to the CITATION file (default: CITATION.cff)",
    )
    args = parser.parse_args()
    citation_path = Path(args.file).resolve()
    if not citation_path.exists():
        raise SystemExit(f"CITATION file not found: {citation_path}")
    update_citation(args.version, citation_path)
    print(f"Updated {citation_path} to version {args.version} on {dt.date.today():%Y-%m-%d}.")


if __name__ == "__main__":
    main()
