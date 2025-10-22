"""Round-trip tests for NGFF and SpatialData writers via the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import anndata as ad
import numpy as np
import pytest
import zarr
from typer.testing import CliRunner

from omnispatial.adapters.cosmx import CosMxAdapter
from omnispatial.adapters.merfish import MerfishAdapter
from omnispatial.adapters.xenium import XeniumAdapter
from omnispatial.cli import app
from omnispatial.utils import read_image_any

runner = CliRunner()


def _invoke_convert(input_dir: Path, out_path: Path, fmt: str, vendor: str | None = None) -> None:
    args = ["convert", str(input_dir), "--out", str(out_path), "--format", fmt]
    if vendor:
        args.extend(["--vendor", vendor])
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout


def _open_ngff(path: Path, image_name: str, table_name: str) -> Tuple[np.ndarray, ad.AnnData]:
    store = zarr.open_group(str(path), mode="r")
    image_data = store["images"][image_name]["0"][:]
    adata = ad.read_zarr(str(path / "tables" / table_name))
    return image_data, adata


@pytest.mark.parametrize(
    "fixture_name", ["xenium_synthetic_dataset", "cosmx_synthetic_dataset", "merfish_synthetic_dataset"]
)
def test_convert_to_ngff(request, fixture_name: str, tmp_path: Path) -> None:
    input_dir: Path = request.getfixturevalue(fixture_name)
    if fixture_name == "xenium_synthetic_dataset":
        adapter = XeniumAdapter()
        vendor = "xenium"
    elif fixture_name == "cosmx_synthetic_dataset":
        adapter = CosMxAdapter()
        vendor = "cosmx"
    else:
        adapter = MerfishAdapter()
        vendor = "merfish"

    dataset = adapter.read(input_dir)
    out_path = tmp_path / f"{vendor}_ngff.zarr"
    _invoke_convert(input_dir, out_path, "ngff", vendor)

    image_data, adata = _open_ngff(out_path, dataset.images[0].name, dataset.tables[0].name)
    original_image, _ = read_image_any(Path(dataset.images[0].path))  # type: ignore[arg-type]
    if original_image.ndim == 2:
        original_shape = original_image.shape
    else:
        original_shape = original_image.shape[-2:]
    assert image_data.shape[-2:] == original_shape
    original_table = ad.read_h5ad(dataset.tables[0].adata_path)
    assert np.isclose(float(adata.X.sum()), float(original_table.X.sum()))
    root = zarr.open_group(str(out_path), mode="r")
    assert "omnispatial_provenance" in root.attrs


@pytest.mark.parametrize(
    "fixture_name", ["xenium_synthetic_dataset", "cosmx_synthetic_dataset", "merfish_synthetic_dataset"]
)
def test_convert_to_spatialdata(request, fixture_name: str, tmp_path: Path) -> None:
    spatialdata = pytest.importorskip("spatialdata")
    from spatialdata.io import read_zarr

    input_dir: Path = request.getfixturevalue(fixture_name)
    if fixture_name == "xenium_synthetic_dataset":
        adapter = XeniumAdapter()
        vendor = "xenium"
    elif fixture_name == "cosmx_synthetic_dataset":
        adapter = CosMxAdapter()
        vendor = "cosmx"
    else:
        adapter = MerfishAdapter()
        vendor = "merfish"

    dataset = adapter.read(input_dir)
    out_path = tmp_path / f"{vendor}_sdata.zarr"
    _invoke_convert(input_dir, out_path, "spatialdata", vendor)

    sdata = read_zarr(str(out_path))
    image_key = next(iter(sdata.images))
    image = sdata.images[image_key]
    image_array = image.xdata if hasattr(image, "xdata") else image
    image_values = np.asarray(image_array.values if hasattr(image_array, "values") else image_array)
    assert image_values.shape[-2:] == np.asarray(read_image_any(Path(dataset.images[0].path))[0]).shape[-2:]  # type: ignore[arg-type]

    table = sdata.table
    assert np.isclose(float(table.X.sum()), float(ad.read_h5ad(dataset.tables[0].adata_path).X.sum()))


def test_convert_dry_run(tmp_path: Path, xenium_synthetic_dataset: Path) -> None:
    out_path = tmp_path / "dry_run.zarr"
    result = runner.invoke(
        app,
        [
            "convert",
            str(xenium_synthetic_dataset),
            "--vendor",
            "xenium",
            "--out",
            str(out_path),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert not out_path.exists()
