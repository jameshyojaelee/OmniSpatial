"""Property based tests for the canonical spatial model."""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd
from hypothesis import given, strategies as st
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from omnispatial.core.model import (
    AffineTransform,
    CoordinateFrame,
    LabelLayer,
    SpatialDataset,
    TableLayer,
)
from omnispatial.utils import dataframe_summary

IDENTITY: Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]] = (
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
)


float_values = st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False)
scale_values = st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False)


@st.composite
def affine_pair_strategy(draw: st.DrawFn) -> Tuple[AffineTransform, AffineTransform]:
    """Generate composable affine transforms with shared units."""
    units = draw(st.sampled_from(["micrometer", "nanometer"]))
    matrix_one = (
        (draw(scale_values), draw(float_values), draw(float_values)),
        (draw(float_values), draw(scale_values), draw(float_values)),
        (0.0, 0.0, 1.0),
    )
    matrix_two = (
        (draw(scale_values), draw(float_values), draw(float_values)),
        (draw(float_values), draw(scale_values), draw(float_values)),
        (0.0, 0.0, 1.0),
    )
    first = AffineTransform(matrix=matrix_one, units=units, source="intermediate", target="global")
    second = AffineTransform(matrix=matrix_two, units=units, source="local", target="intermediate")
    return first, second


@given(affine_pair_strategy())
def test_affine_composition(pair: Tuple[AffineTransform, AffineTransform]) -> None:
    """Composed transforms should match explicit matrix multiplication."""
    first, second = pair
    composed = first.compose(second)
    expected = first.to_numpy() @ second.to_numpy()
    np.testing.assert_allclose(composed.to_numpy(), expected)
    assert composed.source == second.source
    assert composed.target == first.target


@st.composite
def polygon_dataset_strategy(draw: st.DrawFn) -> Tuple[SpatialDataset, float, int]:
    """Create a dataset with a simple polygon label and tabular summary."""
    min_x = draw(st.floats(min_value=-50.0, max_value=0.0, allow_nan=False, allow_infinity=False))
    min_y = draw(st.floats(min_value=-50.0, max_value=0.0, allow_nan=False, allow_infinity=False))
    width = draw(st.floats(min_value=1.0, max_value=20.0, allow_nan=False, allow_infinity=False))
    height = draw(st.floats(min_value=1.0, max_value=20.0, allow_nan=False, allow_infinity=False))
    polygon = box(min_x, min_y, min_x + width, min_y + height)
    rows = draw(st.integers(min_value=1, max_value=5))
    xs = np.linspace(polygon.bounds[0], polygon.bounds[2], rows)
    ys = np.linspace(polygon.bounds[1], polygon.bounds[3], rows)
    table = pd.DataFrame(
        {
            "cell_id": [f"cell_{i}" for i in range(rows)],
            "x": xs,
            "y": ys,
            "gene_a": np.ones(rows),
        }
    )
    global_frame = CoordinateFrame(
        name="global",
        axes=("x", "y", "1"),
        units=("micrometer", "micrometer", "dimensionless"),
        description="Global specimen frame.",
    )
    local_frame = CoordinateFrame(
        name="local",
        axes=("x", "y", "1"),
        units=("micrometer", "micrometer", "dimensionless"),
        description="Local image frame.",
    )
    transform = AffineTransform(matrix=IDENTITY, units="micrometer", source=local_frame.name, target=global_frame.name)
    label_layer = LabelLayer(
        name="synthetic_labels",
        frame=local_frame.name,
        crs="micrometer",
        geometries=[polygon],
        transform=transform,
    )
    table_layer = TableLayer(
        name="synthetic_table",
        frame=local_frame.name,
        transform=transform,
        obs_columns=["cell_id"],
        var_columns=["gene_a"],
        coordinate_columns=("x", "y"),
        summary=dataframe_summary(table),
    )
    dataset = SpatialDataset(
        images=[],
        labels=[label_layer],
        tables=[table_layer],
        frames={global_frame.name: global_frame, local_frame.name: local_frame},
        global_frame=global_frame.name,
    )
    return dataset, polygon, rows


@given(polygon_dataset_strategy())
def test_polygon_roundtrip(data: Tuple[SpatialDataset, BaseGeometry, int]) -> None:
    """Serialising geometries should preserve their area and table counts."""
    dataset, original_polygon, rows = data
    geometries = list(dataset.labels[0].iter_geometries())
    assert geometries, "Expected at least one geometry."
    assert geometries[0].equals_exact(original_polygon, 1e-6)
    assert np.isclose(geometries[0].area, original_polygon.area)
    assert dataset.tables[0].cell_count == rows
