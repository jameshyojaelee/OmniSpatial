"""Regression tests for the high-level ConversionPipeline."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile

from omnispatial.adapters import AdapterRegistry
from omnispatial.core import ConversionPipeline, SampleMetadata
from omnispatial.validate import validate_ngff


def _create_xenium_dataset(root: Path) -> Path:
    """Populate a minimal Xenium-style dataset for testing."""
    images_dir = root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(images_dir / "synthetic.tif", np.ones((2, 2), dtype=np.uint16))

    cells = pd.DataFrame(
        {
            "cell_id": ["cell_a", "cell_b"],
            "x": [0.5, 1.5],
            "y": [0.5, 1.5],
            "area": [1.0, 1.0],
            "polygon_wkt": [
                "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
                "POLYGON ((1 1, 2 1, 2 2, 1 2, 1 1))",
            ],
        }
    )
    cells.to_csv(root / "cells.csv", index=False)

    matrix = pd.DataFrame(
        {
            "cell_id": ["cell_a", "cell_b"],
            "gene": ["Gene1", "Gene1"],
            "count": [5, 7],
        }
    )
    matrix.to_csv(root / "matrix.csv", index=False)
    return root


def test_pipeline_converts_xenium_dataset(tmp_path: Path) -> None:
    """ConversionPipeline should materialise NGFF output for matching adapters."""
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    _create_xenium_dataset(dataset_dir)

    output_dir = tmp_path / "outputs"
    pipeline = ConversionPipeline()
    metadata = SampleMetadata(sample_id="S-001", organism="human", assay="transcriptomics")

    results = pipeline.convert(dataset_dir, output_dir, metadata)
    assert len(results) == 1
    result = results[0]
    assert result.adapter == "xenium"
    assert result.output_path is not None
    assert result.output_path.exists()

    report = validate_ngff(Path(result.output_path))
    assert report.ok

    shutil.rmtree(result.output_path)


def test_registry_matching_requires_detection(tmp_path: Path) -> None:
    """Registry should only yield adapters whose detect() succeeds by default."""
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    _create_xenium_dataset(dataset_dir)

    metadata = SampleMetadata(sample_id="S-002", organism="human", assay="transcriptomics")
    registry = AdapterRegistry.default()

    matches = list(registry.matching(metadata=metadata, input_path=dataset_dir))
    assert matches == ["xenium"]

    fallback_matches = list(registry.matching(metadata=metadata, input_path=dataset_dir, require_detect=False))
    assert "xenium" in fallback_matches
    assert len(fallback_matches) >= len(matches)
