"""Integration tests for the OmniSpatial napari plugin."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from omnispatial.adapters.xenium import XeniumAdapter
from omnispatial.cli import app
from omnispatial.napari_plugin import omnispatial_reader

runner = CliRunner()


@pytest.fixture()
def xenium_bundle(tmp_path: Path, xenium_synthetic_dataset: Path) -> Path:
    adapter = XeniumAdapter()
    out_path = tmp_path / "xenium_bundle.zarr"
    args = [
        "convert",
        str(xenium_synthetic_dataset),
        "--out",
        str(out_path),
        "--format",
        "ngff",
        "--vendor",
        adapter.name,
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout
    return out_path


def test_reader_produces_layers(xenium_bundle: Path) -> None:
    napari = pytest.importorskip("napari", reason="napari is required for plugin test")
    ViewerModel = pytest.importorskip("napari.components.viewer_model").ViewerModel  # type: ignore[attr-defined]

    layers = omnispatial_reader(str(xenium_bundle))
    assert layers is not None
    assert len(layers) >= 2
    viewer = ViewerModel()
    for data, meta, layer_type in layers:
        add_method = getattr(viewer, f"add_{layer_type}")
        add_method(data, **meta)
    points_layers = [layer for layer in viewer.layers if layer.__class__.__name__ == "Points"]
    assert points_layers, "Expected points layer from AnnData table"


def test_reader_points_properties(xenium_bundle: Path) -> None:
    layers = omnispatial_reader(str(xenium_bundle))
    assert layers is not None
    points_layer = next((layer for layer in layers if layer[2] == "points"), None)
    assert points_layer is not None
    data, meta, _ = points_layer
    assert isinstance(data, np.ndarray)
    assert data.shape[1] == 2
    properties = meta.get("properties")
    assert properties is not None
    assert "cell_id" in properties
