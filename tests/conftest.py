"""Test fixtures for OmniSpatial adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd
import pytest
import tifffile


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
