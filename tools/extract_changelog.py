"""Extract a changelog section for GitHub releases."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def extract_section(changelog: Path, version: str) -> str:
    text = changelog.read_text(encoding="utf-8")
    pattern = re.compile(r"^## \[(?P<version>[^\]]+)\].*$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        return text.strip()

    target = next((match for match in matches if match.group("version") == version), None)
    if target is None:
        # Fallback to unreleased section if the version is not present.
        target = next((match for match in matches if match.group("version").lower() == "unreleased"), matches[0])

    start = target.end()
    following = next((match.start() for match in matches if match.start() > target.start()), len(text))
    section = text[start:following].strip()
    heading = target.group(0)
    return f"{heading}\n\n{section}\n"


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: extract_changelog.py <version>", file=sys.stderr)
        sys.exit(1)
    version = sys.argv[1]
    changelog = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
    print(extract_section(changelog, version))


if __name__ == "__main__":
    main()
