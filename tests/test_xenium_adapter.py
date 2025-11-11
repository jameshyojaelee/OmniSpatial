"""End-to-end tests for the Xenium adapter."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from shapely.geometry import box

from omnispatial.adapters.xenium import PIXEL_SIZE, XeniumAdapter
from omnispatial.utils import read_image_any


def test_xenium_adapter_round_trip(xenium_synthetic_dataset: Path) -> None:
    adapter = XeniumAdapter()
    assert adapter.detect(xenium_synthetic_dataset)
    dataset = adapter.read(xenium_synthetic_dataset)

    image_layer = dataset.images[0]
    label_layer = dataset.labels[0]
    table_layer = dataset.tables[0]

    assert image_layer.pixel_size == (PIXEL_SIZE, PIXEL_SIZE, 1.0)
    image_data, _ = read_image_any(image_layer.path)
    assert image_data.shape[-2:] == (4, 4)
    assert label_layer.crs == "micrometer"

    polygons = list(label_layer.iter_geometries())
    assert len(polygons) == 2
    image_bounds = box(0, 0, image_data.shape[1], image_data.shape[0])
    for polygon in polygons:
        assert polygon.within(image_bounds)

    assert table_layer.summary["obs_count"] == 2
    assert table_layer.summary["var_count"] == 2
    assert table_layer.adata_path is not None
    adata_path = Path(table_layer.adata_path)
    assert adata_path.exists()
    assert set(table_layer.var_columns) == {"G1", "G2"}
    assert {geom.area for geom in polygons} == {1.0}
    assert not list(xenium_synthetic_dataset.glob("*.h5ad"))
    assert not adata_path.resolve().is_relative_to(xenium_synthetic_dataset.resolve())
