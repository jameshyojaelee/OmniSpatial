"""Tests for the MERFISH adapter synthetic pipeline."""

from __future__ import annotations

from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd

from omnispatial.adapters.merfish import PIXEL_SIZE, MerfishAdapter
from omnispatial.utils import read_image_any


def test_merfish_adapter_bins_and_counts(merfish_synthetic_dataset: Path) -> None:
    adapter = MerfishAdapter()
    assert adapter.detect(merfish_synthetic_dataset)
    dataset = adapter.read(merfish_synthetic_dataset)

    image_layer = dataset.images[0]
    assert image_layer.pixel_size == (PIXEL_SIZE, PIXEL_SIZE, 1.0)
    image_data, _ = read_image_any(image_layer.path)
    assert image_data.shape[-2:] == (4, 4)

    label_layer = dataset.labels[0]
    polygons = list(label_layer.iter_geometries())
    assert len(polygons) == 2
    for polygon in polygons:
        assert polygon.is_valid

    centroids = [polygon.centroid.x for polygon in polygons]
    assert centroids[1] > centroids[0]

    table_layer = dataset.tables[0]
    assert table_layer.summary["obs_count"] == 2
    assert table_layer.adata_path is not None
    adata_path = Path(table_layer.adata_path)
    assert adata_path.exists()

    adata = ad.read_h5ad(table_layer.adata_path)
    spots = pd.read_csv(merfish_synthetic_dataset / "spots.csv")
    total_intensity = float(spots["intensity"].sum())
    assert np.isclose(float(adata.X.sum()), total_intensity)
    assert set(adata.var_names) == set(spots["gene"])
    assert adata.n_obs == len(polygons)
    assert not list(merfish_synthetic_dataset.glob("*.h5ad"))
    assert not adata_path.resolve().is_relative_to(merfish_synthetic_dataset.resolve())
