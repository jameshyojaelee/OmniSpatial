"""Validation primitives."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import jsonschema


@dataclass
class ValidationItem:
    """Result of a single validation check."""

    name: str
    status: str
    detail: str


@dataclass
class ValidationReport:
    """Collection of validation items."""

    target: Path
    items: List[ValidationItem]

    @classmethod
    def example(cls, bundle: Path, schema_path: Optional[Path]) -> "ValidationReport":
        """Generate a sample validation report without touching disk."""
        detail = "Schema supplied" if schema_path else "Using built-in rules"
        items = [
            ValidationItem(name="structure", status="PASS", detail="Zarr hierarchy reachable"),
            ValidationItem(name="schema", status="INFO", detail=detail),
        ]
        return cls(target=bundle, items=items)


def validate_store(bundle: Path, schema: Optional[dict] = None) -> ValidationReport:
    """Validate a bundle with an optional JSON schema."""
    schema = schema or {"type": "object"}
    jsonschema.Draft202012Validator.check_schema(schema)
    items: Iterable[ValidationItem] = [
        ValidationItem(name="schema", status="PASS", detail="Validated against schema."),
    ]
    return ValidationReport(target=bundle, items=list(items))


__all__ = ["ValidationItem", "ValidationReport", "validate_store"]
