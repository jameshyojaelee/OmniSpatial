"""Sanity checks for key imports."""

from pathlib import Path

from omnispatial import __version__
from omnispatial.adapters import AdapterRegistry
from omnispatial.core import SampleMetadata
from omnispatial.validate import ValidationReport


def test_version_constant() -> None:
    """Package exposes the expected version."""
    assert __version__ == "0.1.0"


def test_registry_matches() -> None:
    """Default registry returns adapters that match the assay."""
    metadata = SampleMetadata(sample_id="1", organism="human", assay="transcriptomics")
    registry = AdapterRegistry.default()
    matches = list(registry.matching(metadata=metadata, input_path=Path("data"), require_detect=False))
    assert matches, "Expected at least one adapter for transcriptomics assays"


def test_validation_report_example() -> None:
    """Validation report factory returns populated items."""
    report = ValidationReport.example(bundle=Path("bundle"))
    assert report.ok
    assert report.issues
