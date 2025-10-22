from __future__ import annotations

import asyncio
from pathlib import Path

import numpy as np
import pytest
import tifffile

from omnispatial import api
from omnispatial.adapters import registry
from omnispatial.adapters.base import SpatialAdapter
from omnispatial.core.model import AffineTransform, CoordinateFrame, ImageLayer, SpatialDataset
from omnispatial.validate import ValidationReport


def _identity_transform(source: str, target: str) -> AffineTransform:
    return AffineTransform(
        matrix=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        units="micrometer",
        source=source,
        target=target,
    )


def _dataset(image_path: Path) -> SpatialDataset:
    local = CoordinateFrame(name="local", axes=("x", "y", "1"), units=("micrometer", "micrometer", "dimensionless"))
    global_frame = CoordinateFrame(
        name="global",
        axes=("x", "y", "1"),
        units=("micrometer", "micrometer", "dimensionless"),
    )
    transform = _identity_transform(local.name, global_frame.name)
    image_layer = ImageLayer(
        name="img",
        frame=local.name,
        path=image_path,
        pixel_size=(1.0, 1.0, 1.0),
        units="micrometer",
        channel_names=["intensity"],
        multiscale=[{"path": "scale0", "scale": [1, 1, 1]}],
        transform=transform,
    )
    return SpatialDataset(
        images=[image_layer],
        labels=[],
        tables=[],
        frames={local.name: local, global_frame.name: global_frame},
        global_frame=global_frame.name,
    )


class _APIAdapter(SpatialAdapter):
    name = "api-test"

    def __init__(self, dataset: SpatialDataset) -> None:
        self._dataset = dataset

    def metadata(self) -> dict:
        return {"vendor": "test", "modalities": ["synthetic"]}

    def detect(self, input_path: Path) -> bool:
        return True

    def read(self, input_path: Path) -> SpatialDataset:
        return self._dataset


@pytest.fixture
def image_path(tmp_path: Path) -> Path:
    path = tmp_path / "image.tif"
    tifffile.imwrite(path, np.ones((4, 4), dtype=np.uint16))
    return path


@pytest.fixture
def stub_adapter(monkeypatch: pytest.MonkeyPatch, image_path: Path):
    dataset = _dataset(image_path)

    class FactoryAdapter(_APIAdapter):
        def __init__(self):  # type: ignore[override]
            super().__init__(dataset)

    monkeypatch.setattr(registry, "_REGISTERED_ADAPTERS", {FactoryAdapter.name: FactoryAdapter})
    monkeypatch.setattr(registry, "_ENTRYPOINTS_LOADED", True)
    return dataset


def test_convert_writes_ngff(tmp_path: Path, stub_adapter: SpatialDataset) -> None:
    target = tmp_path / "out.zarr"
    result = api.convert(tmp_path, target, vendor="api-test", output_format="ngff")

    assert result.adapter == "api-test"
    assert result.format == "ngff"
    assert result.output_path == target
    assert target.exists()
    assert result.dataset.images[0].name == "img"


def test_convert_async(tmp_path: Path, stub_adapter: SpatialDataset) -> None:
    target = tmp_path / "async.zarr"
    result = asyncio.run(api.convert_async(tmp_path, target, vendor="api-test", output_format="ngff"))
    assert result.output_path == target


def test_convert_dry_run(tmp_path: Path, stub_adapter: SpatialDataset) -> None:
    result = api.convert(tmp_path, tmp_path / "unused.zarr", vendor="api-test", dry_run=True)
    assert result.output_path is None


def test_validate_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    report = ValidationReport.example()
    monkeypatch.setattr(api, "_validate_bundle", lambda bundle, fmt: report)
    outcome = api.validate("bundle", output_format="ngff")
    assert outcome is report


def test_validate_async(monkeypatch: pytest.MonkeyPatch) -> None:
    report = ValidationReport.example()
    monkeypatch.setattr(api, "_validate_bundle", lambda bundle, fmt: report)
    outcome = asyncio.run(api.validate_async("bundle", output_format="spatialdata"))
    assert outcome is report
