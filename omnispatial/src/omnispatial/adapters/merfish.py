"""MERFISH adapter implementation for synthetic CSV exports."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import anndata as ad
import numpy as np
import pandas as pd
from shapely import wkt as shapely_wkt
from shapely.geometry import Point
from shapely.geometry import box as shapely_box
from shapely.geometry.base import BaseGeometry

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

SPOTS_FILE = "spots.csv"
CELLS_FILE = "cells.csv"
IMAGE_FILE = "image.tif"
PIXEL_UNITS = "micrometer"
PIXEL_SIZE = 0.65


def _affine_scale(scale: float) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
    return (
        (scale, 0.0, 0.0),
        (0.0, scale, 0.0),
        (0.0, 0.0, 1.0),
    )


@register_adapter
class MerfishAdapter(SpatialAdapter):
    """Adapter for MERFISH-style CSV exports."""

    name = "merfish"

    def metadata(self) -> Dict[str, Any]:
        return {"name": self.name, "vendor": "Vizgen", "modalities": ["transcriptomics"]}

    def detect(self, input_path: Path) -> bool:
        path = Path(input_path)
        if not path.exists():
            return False
        return (path / SPOTS_FILE).exists()

    def read(self, input_path: Path) -> SpatialDataset:
        base = Path(input_path)
        spots = self._load_spots(base / SPOTS_FILE)
        image_path = base / IMAGE_FILE
        image_data, _ = read_image_any(image_path)

        if (base / CELLS_FILE).exists():
            cells, source = self._load_cells(base / CELLS_FILE)
        else:
            cells, source = self._derive_bins(spots)

        polygons = {row.cell_id: self._ensure_polygon(row.polygon_wkt) for row in cells.itertuples()}
        counts = self._aggregate_spots(spots, polygons)

        local_frame = CoordinateFrame(
            name="merfish_pixel",
            axes=("x", "y", "1"),
            units=(PIXEL_UNITS, PIXEL_UNITS, "dimensionless"),
            description="MERFISH stitched pixel frame.",
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
            name="merfish_image",
            frame=local_frame.name,
            path=image_path,
            pixel_size=(PIXEL_SIZE, PIXEL_SIZE, 1.0),
            units=PIXEL_UNITS,
            channel_names=["intensity"],
            multiscale=[{"path": image_path.name, "scale": [1, PIXEL_SIZE, PIXEL_SIZE]}],
            transform=transform,
        )
        label_layer = self._build_label_layer(cells, source, transform, local_frame)
        table_layer = self._build_table_layer(base, cells, counts, transform, local_frame)
        if table_layer.adata_path is None:
            raise ValueError("MERFISH adapter failed to materialise an AnnData table.")
        table_path = Path(table_layer.adata_path)
        if not table_path.exists():
            raise ValueError(f"AnnData table '{table_path}' was not created.")
        candidates = [
            base / SPOTS_FILE,
            image_path,
        ]
        cells_file = base / CELLS_FILE
        if cells_file.exists():
            candidates.append(cells_file)
        existing_sources = sorted({candidate.resolve() for candidate in candidates if candidate.exists()})
        provenance = self.build_provenance(
            sources=[str(source) for source in existing_sources],
            extra={"bins": list(polygons.keys()), "table": table_path.name},
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
    def _load_spots(path: Path) -> pd.DataFrame:
        df = load_tabular_file(path)
        required = {"x", "y", "gene", "intensity"}
        missing = required - set(df.columns)
        if missing:
            missing_cols = ", ".join(sorted(missing))
            raise ValueError(f"Spots table missing required columns: {missing_cols}")
        return df

    @staticmethod
    def _load_cells(path: Path) -> Tuple[pd.DataFrame, str]:
        df = load_tabular_file(path)
        required = {"cell_id", "polygon_wkt"}
        missing = required - set(df.columns)
        if missing:
            missing_cols = ", ".join(sorted(missing))
            raise ValueError(f"Cells table missing required columns: {missing_cols}")
        if "x" not in df.columns or "y" not in df.columns:
            centroids_x: List[float] = []
            centroids_y: List[float] = []
            for polygon_wkt in df["polygon_wkt"]:
                polygon = MerfishAdapter._ensure_polygon(polygon_wkt)
                centroids_x.append(polygon.centroid.x)
                centroids_y.append(polygon.centroid.y)
            df = df.assign(x=centroids_x, y=centroids_y)
        return df.set_index("cell_id", drop=False), CELLS_FILE

    @staticmethod
    def _derive_bins(spots: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
        min_x = float(spots["x"].min())
        max_x = float(spots["x"].max())
        min_y = float(spots["y"].min())
        max_y = float(spots["y"].max())
        width = max_x - min_x
        padding = max(width, max_y - min_y) * 0.05 or 0.1
        min_x -= padding
        max_x += padding
        min_y -= padding
        max_y += padding
        mid_x = min_x + (max_x - min_x) / 2.0
        left = shapely_box(min_x, min_y, mid_x, max_y)
        right = shapely_box(mid_x, min_y, max_x, max_y)
        cells = pd.DataFrame(
            {
                "cell_id": ["bin_left", "bin_right"],
                "polygon_wkt": [left.wkt, right.wkt],
                "x": [left.centroid.x, right.centroid.x],
                "y": [left.centroid.y, right.centroid.y],
            }
        )
        return cells.set_index("cell_id", drop=False), "derived"

    @staticmethod
    def _ensure_polygon(wkt_string: str) -> BaseGeometry:
        polygon = shapely_wkt.loads(wkt_string)
        if polygon.geom_type not in {"Polygon", "MultiPolygon"}:
            raise TypeError("Cells must be polygonal geometries.")
        return polygon

    def _aggregate_spots(self, spots: pd.DataFrame, polygons: Dict[str, BaseGeometry]) -> pd.DataFrame:
        totals: Dict[str, Dict[str, float]] = {cell_id: {} for cell_id in polygons}
        for row in spots.itertuples():
            point = Point(float(row.x), float(row.y))
            assigned = False
            for cell_id, polygon in polygons.items():
                if polygon.covers(point):
                    totals[cell_id][row.gene] = totals[cell_id].get(row.gene, 0.0) + float(row.intensity)
                    assigned = True
                    break
            if not assigned:
                raise ValueError("Encountered spot outside derived bins.")
        genes = sorted({row.gene for row in spots.itertuples()})
        order = list(polygons.keys())
        data = []
        for cell_id in order:
            data.append([totals[cell_id].get(gene, 0.0) for gene in genes])
        counts = pd.DataFrame(data, index=order, columns=genes)
        return counts

    def _build_label_layer(
        self,
        cells: pd.DataFrame,
        source: str,
        transform: AffineTransform,
        local_frame: CoordinateFrame,
    ) -> LabelLayer:
        return LabelLayer(
            name="merfish_bins",
            frame=local_frame.name,
            crs=PIXEL_UNITS,
            geometries=cells["polygon_wkt"].tolist(),
            properties={"source": source},
            transform=transform,
        )

    def _build_table_layer(
        self,
        base: Path,
        cells: pd.DataFrame,
        counts: pd.DataFrame,
        transform: AffineTransform,
        local_frame: CoordinateFrame,
    ) -> TableLayer:
        obs = cells.loc[counts.index][["cell_id", "x", "y"]]
        var = pd.DataFrame(index=counts.columns)
        adata = ad.AnnData(X=counts.astype(float).values, obs=obs.copy(), var=var)
        adata_path = temporary_output_path(stem="merfish-spots", suffix=".h5ad")
        adata.write(adata_path, compression="gzip")
        summary = dataframe_summary(obs.reset_index(drop=True))
        summary.update({"var_count": int(adata.n_vars), "adata_path": str(adata_path)})
        return TableLayer(
            name="merfish_table",
            frame=local_frame.name,
            transform=transform,
            adata_path=adata_path,
            obs_columns=list(obs.columns),
            var_columns=list(var.index),
            coordinate_columns=("x", "y"),
            summary=summary,
        )


__all__ = ["PIXEL_SIZE", "MerfishAdapter"]
