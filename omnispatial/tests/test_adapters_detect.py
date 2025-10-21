"""Detection tests for vendor adapters."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import tifffile
import zarr

from omnispatial.adapters import get_adapter
from omnispatial.adapters.cosmx import CosMxAdapter
from omnispatial.adapters.merfish import MerfishAdapter
from omnispatial.adapters.xenium import XeniumAdapter


def _write_table(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({"cell_id": ["a", "b"], "x": [0.0, 1.0], "y": [0.0, 1.0], "gene_a": [10, 20]})
    df.to_csv(path, index=False)


@pytest.mark.parametrize(
    ("adapter_cls", "filename"),
    [
        (XeniumAdapter, "cells.csv"),
        (CosMxAdapter, "cells.parquet"),
        (MerfishAdapter, "merfish_transcripts.csv"),
    ],
)
def test_adapter_detects_expected_structure(tmp_path, adapter_cls, filename) -> None:
    """Each adapter should recognise its canonical file layout."""
    file_path = tmp_path / filename
    if adapter_cls is XeniumAdapter:
        images_dir = tmp_path / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        tifffile.imwrite(images_dir / "synthetic.tif", np.ones((2, 2), dtype=np.uint16))
        cells = pd.DataFrame(
            {
                "cell_id": ["a", "b"],
                "x": [0.5, 1.5],
                "y": [0.5, 1.5],
                "area": [1.0, 1.0],
                "polygon_wkt": [
                    "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
                    "POLYGON ((1 1, 2 1, 2 2, 1 2, 1 1))",
                ],
            }
        )
        cells.to_csv(file_path, index=False)
        matrix = pd.DataFrame(
            {
                "cell_id": ["a", "a", "b"],
                "gene": ["G1", "G2", "G1"],
                "count": [5, 3, 2],
            }
        )
        matrix.to_csv(tmp_path / "matrix.csv", index=False)
    else:
        if adapter_cls is CosMxAdapter:
            image_path = tmp_path / "image.zarr"
            root = zarr.open_group(str(image_path), mode="w")
            root.create_dataset("scale0", data=np.ones((1, 2, 2), dtype=np.uint16), chunks=(1, 2, 2))
            cells = pd.DataFrame(
                {
                    "cell_id": ["c1", "c2"],
                    "centroid_x": [0.0, 0.0],
                    "centroid_y": [0.0, 0.0],
                    "polygon_wkt": [
                        "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
                        "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
                    ],
                    "region": ["R1", "R2"],
                }
            )
            cells.to_parquet(tmp_path / "cells.parquet")
            expr = pd.DataFrame(
                {
                    "cell_id": ["c1", "c2"],
                    "target": ["T1", "T1"],
                    "count": [1, 1],
                }
            )
            expr.to_parquet(tmp_path / "expr.parquet")
        else:
            _write_table(file_path)
    adapter = adapter_cls()
    assert adapter.detect(tmp_path)
    dataset = adapter.read(tmp_path)
    assert dataset.tables[0].cell_count == 2


def test_get_adapter_returns_none_for_unknown(tmp_path) -> None:
    """Unknown paths should not raise errors and return None."""
    assert get_adapter(tmp_path / "missing") is None
