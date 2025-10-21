"""Xenium adapter implementation for synthetic CSV exports."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import anndata as ad
import numpy as np
import pandas as pd

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
from omnispatial.utils import dataframe_summary, polygons_from_wkt, read_image_any, read_table_csv

CELLS_FILE = "cells.csv"
MATRIX_FILE = "matrix.csv"
IMAGE_DIR = "images"
PIXEL_UNITS = "micrometer"
PIXEL_SIZE = 0.5


def _candidate_paths(base: Path) -> Iterable[Path]:
    yield base / CELLS_FILE
    yield base / MATRIX_FILE


def _find_image_path(base: Path) -> Optional[Path]:
    image_root = base / IMAGE_DIR
    if not image_root.exists():
        return None
    for suffix in ("*.tif", "*.tiff", "*.zarr"):
        matches = list(image_root.rglob(suffix))
        if matches:
            return matches[0]
    for candidate in image_root.rglob("*"):
        if candidate.is_file() or candidate.is_dir():
            return candidate
    return None


def _affine_scale(scale: float) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
    return (
        (scale, 0.0, 0.0),
        (0.0, scale, 0.0),
        (0.0, 0.0, 1.0),
    )


@register_adapter
class XeniumAdapter(SpatialAdapter):
    """Adapter for Xenium-style CSV exports."""

    name = "xenium"

    def metadata(self) -> Dict[str, Any]:
        return {"name": self.name, "vendor": "10x Genomics", "modalities": ["transcriptomics"]}

    def detect(self, input_path: Path) -> bool:
        path = Path(input_path)
        if not path.exists():
            return False
        required = list(_candidate_paths(path))
        return all(candidate.exists() for candidate in required)

    def read(self, input_path: Path) -> SpatialDataset:
        path = Path(input_path)
        cells = self._load_cells(path / CELLS_FILE)
        matrix = self._load_matrix(path / MATRIX_FILE)
        image_path = _find_image_path(path)
        if image_path is None:
            raise FileNotFoundError("Unable to locate image resource under images/ directory.")
        image_data, _ = read_image_any(image_path)
        local_frame = CoordinateFrame(
            name="xenium_pixel",
            axes=("x", "y", "1"),
            units=(PIXEL_UNITS, PIXEL_UNITS, "dimensionless"),
            description="Xenium pixel coordinate frame.",
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
        image_layer = self._build_image_layer(image_path, image_data, transform, local_frame)
        label_layer = self._build_label_layer(cells, transform, local_frame)
        table_layer = self._build_table_layer(path, cells, matrix, transform, local_frame)
        return SpatialDataset(
            images=[image_layer],
            labels=[label_layer],
            tables=[table_layer],
            frames={global_frame.name: global_frame, local_frame.name: local_frame},
            global_frame=global_frame.name,
        )

    @staticmethod
    def _load_cells(path: Path) -> pd.DataFrame:
        cells = read_table_csv(path)
        required_columns = {"cell_id", "x", "y", "polygon_wkt"}
        missing = required_columns - set(cells.columns)
        if missing:
            missing_cols = ", ".join(sorted(missing))
            raise ValueError(f"Cells table missing required columns: {missing_cols}")
        numeric_columns = {"x", "y"}
        for column in numeric_columns:
            if not np.issubdtype(cells[column].dtype, np.number):
                raise TypeError(f"Column '{column}' must be numeric.")
        return cells.set_index("cell_id", drop=False)

    @staticmethod
    def _load_matrix(path: Path) -> pd.DataFrame:
        matrix = read_table_csv(path)
        required_columns = {"cell_id", "gene", "count"}
        missing = required_columns - set(matrix.columns)
        if missing:
            missing_cols = ", ".join(sorted(missing))
            raise ValueError(f"Matrix table missing required columns: {missing_cols}")
        return matrix

    @staticmethod
    def _build_image_layer(
        image_path: Path,
        image_data: np.ndarray,
        transform: AffineTransform,
        local_frame: CoordinateFrame,
    ) -> ImageLayer:
        return ImageLayer(
            name="xenium_image",
            frame=local_frame.name,
            path=image_path,
            pixel_size=(PIXEL_SIZE, PIXEL_SIZE, 1.0),
            units=PIXEL_UNITS,
            channel_names=["intensity"],
            multiscale=[{"path": image_path.name, "scale": [1, PIXEL_SIZE, PIXEL_SIZE]}],
            transform=transform,
        )

    @staticmethod
    def _build_label_layer(
        cells: pd.DataFrame,
        transform: AffineTransform,
        local_frame: CoordinateFrame,
    ) -> LabelLayer:
        polygons = polygons_from_wkt(cells["polygon_wkt"].tolist())
        return LabelLayer(
            name="xenium_cells",
            frame=local_frame.name,
            crs=PIXEL_UNITS,
            geometries=[geom.wkt for geom in polygons],
            properties={"source": CELLS_FILE},
            transform=transform,
        )

    def _build_table_layer(
        self,
        base_path: Path,
        cells: pd.DataFrame,
        matrix: pd.DataFrame,
        transform: AffineTransform,
        local_frame: CoordinateFrame,
    ) -> TableLayer:
        counts = (
            matrix.pivot_table(index="cell_id", columns="gene", values="count", aggfunc="sum", fill_value=0)
            .sort_index()
        )
        counts = counts.sort_index(axis=1)
        obs = cells.loc[counts.index]
        var = pd.DataFrame(index=counts.columns)
        adata = ad.AnnData(X=counts.astype(float).values, obs=obs.copy(), var=var)
        adata_path = base_path / "matrix.h5ad"
        adata.write(adata_path, compression="gzip")
        summary = dataframe_summary(obs.reset_index(drop=True))
        summary.update({"var_count": int(adata.n_vars), "adata_path": str(adata_path)})
        return TableLayer(
            name="xenium_table",
            frame=local_frame.name,
            transform=transform,
            adata_path=adata_path,
            obs_columns=list(obs.columns),
            var_columns=list(var.index),
            coordinate_columns=("x", "y"),
            summary=summary,
        )


__all__ = ["PIXEL_SIZE", "XeniumAdapter"]
