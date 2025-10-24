"""Integration tests for the high-level omnispatial.api helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
import zarr

from omnispatial import api


def _create_xenium_fixture(root: Path) -> None:
    """Create a minimal Xenium-style dataset for conversions."""
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
        {"cell_id": ["cell_a", "cell_b"], "gene": ["Gene1", "Gene1"], "count": [5, 7]}
    )
    matrix.to_csv(root / "matrix.csv", index=False)


def _expected_sources(dataset_dir: Path) -> set[str]:
    return {
        str((dataset_dir / "cells.csv").resolve()),
        str((dataset_dir / "matrix.csv").resolve()),
        str((dataset_dir / "images" / "synthetic.tif").resolve()),
        str((dataset_dir / "matrix.h5ad").resolve()),
    }


def test_api_convert_and_validate(tmp_path: Path) -> None:
    """High-level API should emit NGFF and SpatialData bundles with provenance."""
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    _create_xenium_fixture(dataset_dir)

    ngff_output = tmp_path / "xenium_ngff.zarr"
    spatial_output = tmp_path / "xenium_spatial.zarr"

    ngff_result = api.convert(
        dataset_dir,
        ngff_output,
        vendor="xenium",
        output_format="ngff",
    )
    assert ngff_result.adapter == "xenium"
    assert ngff_result.output_path is not None
    assert ngff_result.output_path.exists()

    ngff_report = api.validate(ngff_result.output_path, output_format="ngff")
    assert ngff_report.ok

    root = zarr.open_group(str(ngff_result.output_path), mode="r")
    provenance = root.attrs.get("omnispatial_provenance")
    assert provenance is not None
    assert set(provenance.get("source_files", [])) == _expected_sources(dataset_dir)

    spatial_result = api.convert(
        dataset_dir,
        spatial_output,
        vendor="xenium",
        output_format="spatialdata",
    )
    assert spatial_result.adapter == "xenium"
    assert spatial_result.output_path is not None
    assert spatial_result.output_path.exists()

    spatial_report = api.validate(spatial_result.output_path, output_format="spatialdata")
    assert spatial_report.ok
