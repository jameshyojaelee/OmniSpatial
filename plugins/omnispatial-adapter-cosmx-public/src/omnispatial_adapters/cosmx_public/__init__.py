"""CosMx public release adapter plugin for OmniSpatial."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import anndata as ad
import pandas as pd
from shapely import wkt
from shapely.affinity import translate

from omnispatial.adapters.base import SpatialAdapter
from omnispatial.core.model import (
    AffineTransform,
    CoordinateFrame,
    ImageLayer,
    LabelLayer,
    SpatialDataset,
    TableLayer,
)
from omnispatial.utils import dataframe_summary, load_tabular_file, read_image_any, temporary_output_path

PIXEL_UNITS = "micrometer"
PIXEL_SIZE = 0.75

_CELL_CANDIDATES = ("cells.parquet", "Cells.parquet", "cells.csv", "Cells.csv")
_EXPR_CANDIDATES = ("exprMat_file.parquet", "exprMat_file.csv", "ExprMat_file.csv", "expression.csv")
_LOOKUP_DIRS = ("", "tables", "Table", "derived", "metadata")
_IMAGE_DIRS = ("", "images", "Image", "CellComposite", "composite", "stitched")
_IMAGE_CANDIDATES = (
    "image.zarr",
    "stitched.zarr",
    "CellComposite.ome.tif",
    "CellComposite.ome.tiff",
    "composite.ome.tif",
    "cosmx_ome.tif",
)


def _normalise_column(name: str) -> str:
    return name.lower().replace(" ", "_").replace(".", "_")


def _resolve_column(columns: Dict[str, str], candidates: Iterable[str]) -> str:
    for candidate in candidates:
        key = candidate.lower()
        if key in columns:
            return columns[key]
    raise KeyError(f"Missing required column, expected one of: {', '.join(candidates)}")


class CosMxPublicAdapter(SpatialAdapter):
    """Adapter for NanoString CosMx public release CSV datasets."""

    name = "cosmx-public"

    def metadata(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "vendor": "NanoString",
            "release": "public",
            "modalities": ["transcriptomics"],
        }

    def detect(self, input_path: Path) -> bool:
        base = Path(input_path)
        return (
            base.exists()
            and self._resolve_cells(base) is not None
            and self._resolve_expression(base) is not None
            and self._resolve_image(base) is not None
        )

    def read(self, input_path: Path) -> SpatialDataset:
        base = Path(input_path)
        cells_path = self._resolve_cells(base)
        expr_path = self._resolve_expression(base)
        image_path = self._resolve_image(base)

        if cells_path is None or expr_path is None or image_path is None:
            raise FileNotFoundError("CosMx public release dataset is missing cells, expression, or image resources.")

        cells = self._load_cells(cells_path)
        expr = self._load_expression(expr_path)
        image_data, _ = read_image_any(image_path)
        width = int(image_data.shape[-1])

        region_offsets = self._compute_region_offsets(cells, width)
        stitched_cells = self._apply_offsets(cells, region_offsets)

        local_frame = CoordinateFrame(
            name="cosmx_public_pixel",
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
            matrix=self._affine_scale(PIXEL_SIZE),
            units=PIXEL_UNITS,
            source=local_frame.name,
            target=global_frame.name,
        )

        image_layer = ImageLayer(
            name="cosmx_public_image",
            frame=local_frame.name,
            path=image_path,
            pixel_size=(PIXEL_SIZE, PIXEL_SIZE, 1.0),
            units=PIXEL_UNITS,
            channel_names=["intensity"],
            multiscale=[{"path": "scale0", "scale": [1, PIXEL_SIZE, PIXEL_SIZE]}],
            transform=transform,
        )
        label_layer = self._build_label_layer(stitched_cells, transform, local_frame, source=cells_path.name)
        table_layer = self._build_table_layer(base, stitched_cells, expr, transform, local_frame)
        table_path = Path(table_layer.adata_path) if table_layer.adata_path else None
        if table_path is None or not table_path.exists():
            raise ValueError("CosMx public adapter failed to materialise an AnnData table.")

        provenance = self.build_provenance(
            sources=[cells_path, expr_path, image_path],
            extra={"release": "public", "table": table_path.name},
        )
        return SpatialDataset(
            images=[image_layer],
            labels=[label_layer],
            tables=[table_layer],
            frames={global_frame.name: global_frame, local_frame.name: local_frame},
            global_frame=global_frame.name,
            provenance=provenance,
        )

    def _resolve_cells(self, base: Path) -> Optional[Path]:
        for directory in _LOOKUP_DIRS:
            for candidate in _CELL_CANDIDATES:
                candidate_path = (base / directory / candidate).resolve()
                if candidate_path.exists():
                    return candidate_path
        return None

    def _resolve_expression(self, base: Path) -> Optional[Path]:
        for directory in _LOOKUP_DIRS:
            for candidate in _EXPR_CANDIDATES:
                candidate_path = (base / directory / candidate).resolve()
                if candidate_path.exists():
                    return candidate_path
        return None

    def _resolve_image(self, base: Path) -> Optional[Path]:
        for directory in _IMAGE_DIRS:
            for candidate in _IMAGE_CANDIDATES:
                candidate_path = (base / directory / candidate).resolve()
                if candidate_path.exists():
                    return candidate_path
        return None

    def _load_cells(self, path: Path) -> pd.DataFrame:
        df = load_tabular_file(path)
        normalised = {_normalise_column(col): col for col in df.columns}
        cell_col = _resolve_column(normalised, ("cell_id", "cellid", "cell", "id"))
        x_col = _resolve_column(normalised, ("centroid_x", "center_x", "x_centroid", "centerx", "x"))
        y_col = _resolve_column(normalised, ("centroid_y", "center_y", "y_centroid", "centery", "y"))
        region_col = _resolve_column(normalised, ("region", "fov", "tile", "roi"))
        polygon_col = _resolve_column(normalised, ("polygon_wkt", "geometry", "geom", "outline_wkt"))

        selected = df[[normalised[cell_col], normalised[x_col], normalised[y_col], normalised[region_col], normalised[polygon_col]]].copy()
        selected.columns = ["cell_id", "centroid_x", "centroid_y", "region", "polygon_wkt"]
        if selected["polygon_wkt"].isna().any():
            raise ValueError("Polygon annotations contain null entries.")
        return selected.set_index("cell_id", drop=False)

    def _load_expression(self, path: Path) -> pd.DataFrame:
        df = load_tabular_file(path)
        normalised = {_normalise_column(col): col for col in df.columns}
        required = {"cell_id", "target", "count"}
        if required.issubset(normalised):
            tidy = df[[normalised["cell_id"], normalised["target"], normalised["count"]]].copy()
            tidy.columns = ["cell_id", "target", "count"]
            return tidy

        cell_candidate = _resolve_column(normalised, ("cell_id", "cellid", "cell", "id"))
        wide = df.set_index(normalised[cell_candidate])
        wide.index.name = "cell_id"
        melted = (
            wide.reset_index()
            .melt(id_vars="cell_id", var_name="target", value_name="count")
            .dropna(subset=["count"])
        )
        melted["count"] = pd.to_numeric(melted["count"], errors="coerce").fillna(0).astype(float)
        melted = melted[melted["count"] > 0]
        return melted

    @staticmethod
    def _affine_scale(scale: float) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
        return (
            (scale, 0.0, 0.0),
            (0.0, scale, 0.0),
            (0.0, 0.0, 1.0),
        )

    @staticmethod
    def _compute_region_offsets(cells: pd.DataFrame, width: int) -> Dict[str, float]:
        regions = sorted(cells["region"].astype(str).unique())
        return {region: index * float(width) for index, region in enumerate(regions)}

    @staticmethod
    def _apply_offsets(cells: pd.DataFrame, offsets: Dict[str, float]) -> pd.DataFrame:
        adjusted = cells.copy()
        adjusted["x"] = cells["centroid_x"] + cells["region"].map(offsets)
        adjusted["y"] = cells["centroid_y"]
        polygons: List[str] = []
        for region, wkt_string in zip(cells["region"], cells["polygon_wkt"]):
            polygon = wkt.loads(wkt_string)
            polygon = translate(polygon, xoff=offsets[str(region)], yoff=0.0)
            polygons.append(polygon.wkt)
        adjusted["polygon_wkt"] = polygons
        return adjusted

    def _build_label_layer(
        self,
        cells: pd.DataFrame,
        transform: AffineTransform,
        local_frame: CoordinateFrame,
        *,
        source: str,
    ) -> LabelLayer:
        return LabelLayer(
            name="cosmx_public_cells",
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
        expr: pd.DataFrame,
        transform: AffineTransform,
        local_frame: CoordinateFrame,
    ) -> TableLayer:
        pivot = (
            expr.pivot_table(index="cell_id", columns="target", values="count", aggfunc="sum", fill_value=0)
            .sort_index()
        )
        pivot = pivot.sort_index(axis=1)
        obs = cells.loc[pivot.index]
        var = pd.DataFrame(index=pivot.columns)
        adata = ad.AnnData(X=pivot.astype(float).values, obs=obs.copy(), var=var)
        adata_path = temporary_output_path(stem="cosmx-public-expr", suffix=".h5ad")
        adata.write(adata_path, compression="gzip")
        summary = dataframe_summary(obs.reset_index(drop=True))
        summary.update({"var_count": int(adata.n_vars), "adata_path": str(adata_path)})
        return TableLayer(
            name="cosmx_public_table",
            frame=local_frame.name,
            transform=transform,
            adata_path=adata_path,
            obs_columns=list(obs.columns),
            var_columns=list(var.index),
            coordinate_columns=("x", "y"),
            summary=summary,
        )


__all__ = ["CosMxPublicAdapter"]
