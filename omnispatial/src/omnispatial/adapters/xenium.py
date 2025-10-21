"""Xenium adapter stub."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from shapely.geometry import Point

from omnispatial.adapters.base import SpatialAdapter
from omnispatial.adapters.registry import register_adapter
from omnispatial.core.model import (
    AffineTransform,
    CoordinateFrame,
    LabelLayer,
    SpatialDataset,
    TableLayer,
)
from omnispatial.utils import dataframe_summary, geometries_to_wkt, load_spatial_table

IDENTITY: Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]] = (
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
)


def _candidate_paths(base: Path) -> Iterable[Path]:
    yield base / "xenium_cells.csv"
    yield base / "xenium_cells.parquet"


@register_adapter
class XeniumAdapter(SpatialAdapter):
    """Adapter for 10x Genomics Xenium outputs."""

    name = "xenium"

    def metadata(self) -> Dict[str, Any]:
        return {"name": self.name, "vendor": "10x Genomics", "modalities": ["transcriptomics"]}

    def detect(self, input_path: Path) -> bool:
        path = Path(input_path)
        if not path.exists():
            return False
        return any(candidate.exists() for candidate in _candidate_paths(path))

    def read(self, input_path: Path) -> SpatialDataset:
        path = Path(input_path)
        table_path = self._resolve_table(path)
        table = load_spatial_table(table_path)
        local_frame = CoordinateFrame(
            name="xenium_pixel",
            axes=("x", "y", "1"),
            units=("micrometer", "micrometer", "dimensionless"),
            description="Xenium native pixel frame.",
        )
        global_frame = CoordinateFrame(
            name="global",
            axes=("x", "y", "1"),
            units=("micrometer", "micrometer", "dimensionless"),
            description="Global specimen frame.",
        )
        transform = AffineTransform(
            matrix=IDENTITY,
            units="micrometer",
            source=local_frame.name,
            target=global_frame.name,
        )
        label_layer = LabelLayer(
            name="xenium_cells",
            frame=local_frame.name,
            crs="micrometer",
            geometries=geometries_to_wkt(Point(row["x"], row["y"]).buffer(0.5) for _, row in table.iterrows()),
            transform=transform,
        )
        feature_columns = [col for col in table.columns if col not in {"x", "y"}]
        table_layer = TableLayer(
            name="xenium_table",
            frame=local_frame.name,
            transform=transform,
            obs_columns=["cell_id"] if "cell_id" in table.columns else [],
            var_columns=feature_columns,
            coordinate_columns=("x", "y"),
            summary=dataframe_summary(table),
        )
        return SpatialDataset(
            images=[],
            labels=[label_layer],
            tables=[table_layer],
            frames={global_frame.name: global_frame, local_frame.name: local_frame},
            global_frame=global_frame.name,
        )

    @staticmethod
    def _resolve_table(path: Path) -> Path:
        for candidate in _candidate_paths(path):
            if candidate.exists():
                return candidate
        raise FileNotFoundError("No Xenium table found in input path.")


__all__ = ["XeniumAdapter"]
