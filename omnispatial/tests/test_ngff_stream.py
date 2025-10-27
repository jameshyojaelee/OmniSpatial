"""Tests for streaming image writes in NGFF writer."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import tifffile
import zarr

from omnispatial.core.model import (
    AffineTransform,
    CoordinateFrame,
    ImageLayer,
    ProvenanceMetadata,
    SpatialDataset,
)
from omnispatial.ngff import write_ngff

IDENTITY = (
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
)


def _dataset_with_image(path: Path) -> SpatialDataset:
    local_frame = CoordinateFrame(
        name="local",
        axes=("x", "y", "1"),
        units=("micrometer", "micrometer", "dimensionless"),
        description="Local frame.",
    )
    global_frame = CoordinateFrame(
        name="global",
        axes=("x", "y", "1"),
        units=("micrometer", "micrometer", "dimensionless"),
        description="Global frame.",
    )
    transform = AffineTransform(matrix=IDENTITY, units="micrometer", source="local", target="global")
    image_layer = ImageLayer(
        name="test_image",
        frame="local",
        path=path,
        pixel_size=(1.0, 1.0, 1.0),
        units="micrometer",
        channel_names=["intensity"],
        multiscale=[{"path": "scale0", "scale": [1.0, 1.0, 1.0]}],
        transform=transform,
    )
    provenance = ProvenanceMetadata(
        adapter="test-adapter",
        version="0.0-test",
        source_files=[str(path)],
    )
    return SpatialDataset(
        images=[image_layer],
        labels=[],
        tables=[],
        frames={"local": local_frame, "global": global_frame},
        global_frame="global",
        provenance=provenance,
    )


def test_write_ngff_streams_tiff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = (np.arange(4096 * 4096, dtype=np.uint16) % 256).reshape(4096, 4096)
    image_path = tmp_path / "large.tif"
    tifffile.imwrite(image_path, data, bigtiff=True)

    def _raise(*args, **kwargs):
        raise RuntimeError("tifffile.imread should not be called for streaming writes.")

    monkeypatch.setattr("omnispatial.utils.io.tifffile.imread", _raise)

    dataset = _dataset_with_image(image_path)
    output = tmp_path / "out.zarr"
    result_path = Path(write_ngff(dataset, str(output)))
    assert result_path.exists()

    root = zarr.open_group(str(result_path), mode="r")
    written = root["images"]["test_image"]["0"]
    assert written.shape == (1, data.shape[0], data.shape[1])
    np.testing.assert_array_equal(written[0], data)


def test_write_ngff_streams_zarr(tmp_path: Path) -> None:
    image_store = tmp_path / "image.zarr"
    root = zarr.open_group(str(image_store), mode="w")
    data = np.random.randint(0, 1000, size=(1, 1024, 1024), dtype=np.uint16)
    root.create_dataset("scale0", data=data, chunks=(1, 256, 256))

    dataset = _dataset_with_image(image_store)
    output = tmp_path / "zarr_out.zarr"
    result_path = Path(write_ngff(dataset, str(output)))
    assert result_path.exists()

    out_root = zarr.open_group(str(result_path), mode="r")
    written = out_root["images"]["test_image"]["0"][:]
    np.testing.assert_array_equal(written, data)
