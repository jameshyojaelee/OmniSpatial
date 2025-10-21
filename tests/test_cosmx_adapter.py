"""Tests for the CosMx adapter synthetic pipeline."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from omnispatial.adapters.cosmx import PIXEL_SIZE, CosMxAdapter
from omnispatial.utils import read_image_any


def test_cosmx_adapter_applies_region_offsets(cosmx_synthetic_dataset: Path) -> None:
    adapter = CosMxAdapter()
    assert adapter.detect(cosmx_synthetic_dataset)
    dataset = adapter.read(cosmx_synthetic_dataset)

    image_layer = dataset.images[0]
    assert image_layer.pixel_size == (PIXEL_SIZE, PIXEL_SIZE, 1.0)
    image_data, _ = read_image_any(image_layer.path)
    width = image_data.shape[-1]

    label_layer = dataset.labels[0]
    polygons = list(label_layer.iter_geometries())
    assert len(polygons) == 2
    centroids = sorted([polygon.centroid.x for polygon in polygons])
    assert np.isclose(centroids[0], 0.5)
    assert np.isclose(centroids[1], 0.5 + width)

    table_layer = dataset.tables[0]
    assert table_layer.summary["obs_count"] == 2
    assert table_layer.summary["var_count"] == 2
    assert Path(table_layer.adata_path).exists()  # type: ignore[arg-type]
    assert set(table_layer.var_columns) == {"T1", "T2"}
    assert table_layer.coordinate_columns == ("x", "y")
