"""Unit tests for NGFF label rasterisation."""

from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import Polygon

from omnispatial.ngff.writer import _rasterize_labels


def test_rasterize_single_polygon() -> None:
    polygon = "POLYGON ((1 1, 4 1, 4 4, 1 4, 1 1))"
    mask = _rasterize_labels([polygon], (6, 6))
    expected = np.zeros((6, 6), dtype=np.uint32)
    expected[1:4, 1:4] = 1
    np.testing.assert_array_equal(mask, expected)


def test_rasterize_multi_polygon_assigns_unique_labels() -> None:
    geometries = [
        "POLYGON ((0 0, 2 0, 2 2, 0 2, 0 0))",
        "MULTIPOLYGON (((3 0, 5 0, 5 2, 3 2, 3 0)))",
    ]
    mask = _rasterize_labels(geometries, (4, 6))
    assert mask.dtype == np.uint32
    assert set(np.unique(mask)) == {0, 1, 2}
    assert mask[1, 1] == 1
    assert mask[1, 4] == 2


def test_rasterize_rejects_non_polygon_geometry() -> None:
    with pytest.raises(TypeError):
        _rasterize_labels(["POINT (1 1)"], (2, 2))


def test_rasterize_rejects_empty_geometry() -> None:
    empty_polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]).buffer(0).difference(
        Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    )
    assert empty_polygon.is_empty
    with pytest.raises(ValueError):
        _rasterize_labels([empty_polygon.wkt], (4, 4))
