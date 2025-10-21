"""Test fixtures for OmniSpatial adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd
import pytest
import tifffile
import zarr
from shapely.affinity import translate
from shapely.geometry import box as shapely_box


def _write_image(base: Path, shape: Tuple[int, int], data: np.ndarray) -> Path:
    images_dir = base / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    image_path = images_dir / "synthetic.tif"
    tifffile.imwrite(image_path, data.astype(np.uint16))
    return image_path


def _write_cells(base: Path, rows: Iterable[Dict[str, object]]) -> Path:
    path = base / "cells.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _write_matrix(base: Path, rows: Iterable[Dict[str, object]]) -> Path:
    path = base / "matrix.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


@pytest.fixture()
def xenium_synthetic_dataset(tmp_path: Path) -> Path:
    """Create a synthetic Xenium-like dataset with image and tables."""
    dataset_path = tmp_path / "xenium_synth"
    dataset_path.mkdir()
    image_array = np.array(
        [
            [0, 10, 20, 30],
            [10, 50, 60, 20],
            [20, 70, 90, 40],
            [5, 15, 25, 35],
        ],
        dtype=np.uint16,
    )
    _write_image(dataset_path, image_array.shape, image_array)
    cells = [
        {
            "cell_id": "cell_1",
            "x": 1.0,
            "y": 1.0,
            "area": 1.0,
            "polygon_wkt": "POLYGON ((0.5 0.5, 1.5 0.5, 1.5 1.5, 0.5 1.5, 0.5 0.5))",
        },
        {
            "cell_id": "cell_2",
            "x": 2.5,
            "y": 2.0,
            "area": 1.5,
            "polygon_wkt": "POLYGON ((2 1.5, 3 1.5, 3 2.5, 2 2.5, 2 1.5))",
        },
    ]
    matrix = [
        {"cell_id": "cell_1", "gene": "G1", "count": 10},
        {"cell_id": "cell_1", "gene": "G2", "count": 5},
        {"cell_id": "cell_2", "gene": "G1", "count": 3},
    ]
    _write_cells(dataset_path, cells)
    _write_matrix(dataset_path, matrix)
    return dataset_path


def _write_cosmx_image(base: Path) -> Path:
    image_path = base / "image.zarr"
    array = np.arange(16, dtype=np.uint16).reshape(1, 4, 4)
    downsampled = array[:, ::2, ::2]
    root = zarr.open_group(str(image_path), mode="w")
    root.attrs["multiscales"] = [
        {
            "name": "scale_pyramid",
            "datasets": [
                {"path": "scale0"},
                {"path": "scale1"},
            ],
        }
    ]
    root.create_dataset("scale0", data=array, chunks=array.shape)
    root.create_dataset("scale1", data=downsampled, chunks=downsampled.shape)
    return image_path


@pytest.fixture()
def cosmx_synthetic_dataset(tmp_path: Path) -> Path:
    dataset_path = tmp_path / "cosmx_synth"
    dataset_path.mkdir()
    _write_cosmx_image(dataset_path)

    region_a = shapely_box(0, 0, 1, 1)
    region_b = shapely_box(0, 0, 1, 1)
    region_b_offset = translate(region_b, xoff=0.5, yoff=1.0)

    cells = pd.DataFrame(
        {
            "cell_id": ["cell_a", "cell_b"],
            "centroid_x": [0.5, 0.5],
            "centroid_y": [0.5, 0.5],
            "polygon_wkt": [region_a.wkt, region_b_offset.wkt],
            "region": ["R1", "R2"],
        }
    )
    cells.to_parquet(dataset_path / "cells.parquet")

    expr = pd.DataFrame(
        {
            "cell_id": ["cell_a", "cell_a", "cell_b"],
            "target": ["T1", "T2", "T1"],
            "count": [12, 7, 5],
        }
    )
    expr.to_parquet(dataset_path / "expr.parquet")
    return dataset_path
