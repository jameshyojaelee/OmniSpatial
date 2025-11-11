"""CosMx adapter implementation for synthetic parquet exports."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import anndata as ad
import numpy as np
import pandas as pd
from shapely import wkt
from shapely.affinity import translate

from omnispatial.adapters.base import SpatialAdapter
from omnispatial.adapters.registry import register_adapter
from omnispatial.core.model import (
    AffineTransform,
    CoordinateFrame,
    ImageLayer,
    LabelLayer,
    SpatialDataset,
    TableLayer,
)
from omnispatial.utils import dataframe_summary, read_image_any, load_tabular_file, temporary_output_path

CELLS_FILE = "cells.parquet"
EXPR_FILE = "expr.parquet"
IMAGE_PATH = "image.zarr"
PIXEL_UNITS = "micrometer"
PIXEL_SIZE = 0.75


def _candidate_paths(base: Path) -> Iterable[Path]:
    yield base / CELLS_FILE
    yield base / EXPR_FILE


def _affine_scale(scale: float) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
    return (
        (scale, 0.0, 0.0),
        (0.0, scale, 0.0),
        (0.0, 0.0, 1.0),
    )


@register_adapter
class CosMxAdapter(SpatialAdapter):
    """Adapter for NanoString CosMx synthetic exports."""

    name = "cosmx"

    def metadata(self) -> Dict[str, Any]:
        return {"name": self.name, "vendor": "NanoString", "modalities": ["transcriptomics"]}

    def detect(self, input_path: Path) -> bool:
        path = Path(input_path)
        if not path.exists():
            return False
        return all(candidate.exists() for candidate in _candidate_paths(path))

    def read(self, input_path: Path) -> SpatialDataset:
        base = Path(input_path)
        cells = self._load_cells(base / CELLS_FILE)
        expr = self._load_expr(base / EXPR_FILE)
        image_path = base / IMAGE_PATH
        image_data, _ = read_image_any(image_path)
        region_offsets = self._compute_region_offsets(cells, image_data.shape[-1])
        stitched_cells = self._apply_offsets(cells, region_offsets)

        local_frame = CoordinateFrame(
            name="cosmx_pixel",
            axes=("x", "y", "1"),
            units=(PIXEL_UNITS, PIXEL_UNITS, "dimensionless"),
            description="CosMx stitched pixel frame.",
        )
        global_frame = CoordinateFrame(
            name="global",
            axes=("x", "y", "1"),
            units=(PIXEL_UNITS, PIXEL_UNITS, "dimensionless"),
            description="Global specimen frame.",
        )
        transform = AffineTransform(
            matrix=_affine_scale(PIXEL_SIZE),
            units=PIXEL_UNITS,
            source=local_frame.name,
            target=global_frame.name,
        )

        image_layer = ImageLayer(
            name="cosmx_image",
            frame=local_frame.name,
            path=image_path,
            pixel_size=(PIXEL_SIZE, PIXEL_SIZE, 1.0),
            units=PIXEL_UNITS,
            channel_names=["intensity"],
            multiscale=[{"path": "scale0", "scale": [1, PIXEL_SIZE, PIXEL_SIZE]}],
            transform=transform,
        )
        label_layer = self._build_label_layer(stitched_cells, transform, local_frame)
        table_layer = self._build_table_layer(base, stitched_cells, expr, transform, local_frame)
        if table_layer.adata_path is None:
            raise ValueError("CosMx adapter failed to materialise an AnnData table.")
        table_path = Path(table_layer.adata_path)
        if not table_path.exists():
            raise ValueError(f"AnnData table '{table_path}' was not created.")
        provenance_sources = [
            base / CELLS_FILE,
            base / EXPR_FILE,
            image_path,
        ]
        existing_sources = sorted(
            {candidate.resolve() for candidate in provenance_sources if candidate.exists()}
        )
        provenance = self.build_provenance(
            sources=[str(source) for source in existing_sources],
            extra={"table": table_path.name},
        )
        return SpatialDataset(
            images=[image_layer],
            labels=[label_layer],
            tables=[table_layer],
            frames={global_frame.name: global_frame, local_frame.name: local_frame},
            global_frame=global_frame.name,
            provenance=provenance,
        )

    @staticmethod
    def _load_cells(path: Path) -> pd.DataFrame:
        if path.suffix.lower() != ".parquet":
            raise ValueError("Expected parquet cells file.")
        df = load_tabular_file(path)
        required = {"cell_id", "centroid_x", "centroid_y", "polygon_wkt", "region"}
        missing = required - set(df.columns)
        if missing:
            missing_cols = ", ".join(sorted(missing))
            raise ValueError(f"Cells table missing required columns: {missing_cols}")
        return df.set_index("cell_id", drop=False)

    @staticmethod
    def _load_expr(path: Path) -> pd.DataFrame:
        if path.suffix.lower() != ".parquet":
            raise ValueError("Expected parquet expression file.")
        df = load_tabular_file(path)
        required = {"cell_id", "target", "count"}
        missing = required - set(df.columns)
        if missing:
            missing_cols = ", ".join(sorted(missing))
            raise ValueError(f"Expression table missing required columns: {missing_cols}")
        return df

    @staticmethod
    def _compute_region_offsets(cells: pd.DataFrame, width: int) -> Dict[str, float]:
        regions = sorted(cells["region"].unique())
        return {region: index * float(width) for index, region in enumerate(regions)}

    @staticmethod
    def _apply_offsets(cells: pd.DataFrame, offsets: Dict[str, float]) -> pd.DataFrame:
        adjusted = cells.copy()
        adjusted["x"] = cells["centroid_x"] + cells["region"].map(offsets)
        adjusted["y"] = cells["centroid_y"]
        polygons = []
        for region, wkt_string in zip(cells["region"], cells["polygon_wkt"]):
            polygon = wkt.loads(wkt_string)
            polygon = translate(polygon, xoff=offsets[region], yoff=0.0)
            polygons.append(polygon.wkt)
        adjusted["polygon_wkt"] = polygons
        return adjusted

    def _build_label_layer(
        self,
        cells: pd.DataFrame,
        transform: AffineTransform,
        local_frame: CoordinateFrame,
    ) -> LabelLayer:
        return LabelLayer(
            name="cosmx_cells",
            frame=local_frame.name,
            crs=PIXEL_UNITS,
            geometries=cells["polygon_wkt"].tolist(),
            properties={"source": CELLS_FILE},
            transform=transform,
        )

    def _build_table_layer(
        self,
        base: Path,
        cells: pd.DataFrame,
        expr: pd.DataFrame,
        transform: AffineTransform,
        local_frame: CoordinateFrame,
    ) -> TableLayer:
        counts = (
            expr.pivot_table(index="cell_id", columns="target", values="count", aggfunc="sum", fill_value=0)
            .sort_index()
        )
        counts = counts.sort_index(axis=1)
        obs = cells.loc[counts.index]
        var = pd.DataFrame(index=counts.columns)
        adata = ad.AnnData(X=counts.astype(float).values, obs=obs.copy(), var=var)
        adata_path = temporary_output_path(stem="cosmx-expr", suffix=".h5ad")
        adata.write(adata_path, compression="gzip")
        summary = dataframe_summary(obs.reset_index(drop=True))
        summary.update({"var_count": int(adata.n_vars), "adata_path": str(adata_path)})
        return TableLayer(
            name="cosmx_table",
            frame=local_frame.name,
            transform=transform,
            adata_path=adata_path,
            obs_columns=list(obs.columns),
            var_columns=list(var.index),
            coordinate_columns=("x", "y"),
            summary=summary,
        )


__all__ = ["PIXEL_SIZE", "CosMxAdapter"]
