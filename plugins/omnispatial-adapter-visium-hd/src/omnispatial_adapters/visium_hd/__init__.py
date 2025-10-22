"""Visium HD adapter plugin for OmniSpatial."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import anndata as ad
import pandas as pd
from shapely.geometry import Point

from omnispatial.adapters.base import SpatialAdapter
from omnispatial.core.model import (
    AffineTransform,
    CoordinateFrame,
    ImageLayer,
    LabelLayer,
    SpatialDataset,
    TableLayer,
)
from omnispatial.utils import dataframe_summary, load_tabular_file

OUTS_DIR_CANDIDATES = ("outs", ".", "output")
MATRIX_FILES = ("filtered_feature_bc_matrix.h5",)
MATRIX_DIRS = ("filtered_feature_bc_matrix",)
SPATIAL_DIR = "spatial"
POSITIONS_FILES = ("tissue_positions.parquet", "tissue_positions.csv")
SCALEFACTORS_FILE = "scalefactors_json.json"
HIGHRES_IMAGE = "tissue_hires_image.png"


def _normalise_column(name: str) -> str:
    return name.lower().replace(" ", "_")


class VisiumHDAdapter(SpatialAdapter):
    """Adapter for 10x Genomics Visium HD (Space Ranger) outputs."""

    name = "visium_hd"

    def metadata(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "vendor": "10x Genomics",
            "modalities": ["transcriptomics"],
            "release": "visium_hd",
        }

    def detect(self, input_path: Path) -> bool:
        base = Path(input_path)
        outs_dir = self._resolve_outs_dir(base)
        if outs_dir is None:
            return False
        spatial_dir = outs_dir / SPATIAL_DIR
        matrix = self._resolve_matrix(outs_dir)
        return spatial_dir.exists() and matrix is not None and (spatial_dir / HIGHRES_IMAGE).exists()

    def read(self, input_path: Path) -> SpatialDataset:
        base = Path(input_path)
        outs_dir = self._resolve_outs_dir(base)
        if outs_dir is None:
            raise FileNotFoundError("Unable to locate Space Ranger 'outs' directory for Visium HD input.")
        spatial_dir = outs_dir / SPATIAL_DIR
        matrix_path = self._resolve_matrix(outs_dir)
        if matrix_path is None:
            raise FileNotFoundError("Unable to locate filtered feature matrix for Visium HD dataset.")

        adata = self._read_matrix(matrix_path)
        adata.var_names_make_unique()

        positions = self._load_positions(spatial_dir)
        positions = positions.set_index("barcode")
        adata = adata[adata.obs_names.isin(positions.index)].copy()
        adata.obs = positions.loc[adata.obs_names]

        scalefactors = self._load_scalefactors(spatial_dir)
        pixel_units = "micrometer" if scalefactors.get("microns_per_pixel") else "pixel"
        pixel_size = float(scalefactors.get("microns_per_pixel", 1.0))
        radius = float(scalefactors.get("spot_diameter_fullres", 50.0)) / 2.0

        local_frame = CoordinateFrame(
            name="visium_hd_pixel",
            axes=("x", "y", "1"),
            units=(pixel_units, pixel_units, "dimensionless"),
            description="Visium HD pixel frame.",
        )
        global_frame = CoordinateFrame(
            name="visium_hd_global",
            axes=("x", "y", "1"),
            units=(pixel_units, pixel_units, "dimensionless"),
            description="Global specimen frame.",
        )
        transform = AffineTransform(
            matrix=self._affine_scale(pixel_size),
            units=pixel_units,
            source=local_frame.name,
            target=global_frame.name,
        )

        image_layer = self._build_image_layer(spatial_dir / HIGHRES_IMAGE, local_frame, transform, pixel_units, pixel_size)
        label_layer = self._build_label_layer(adata.obs.reset_index(), local_frame, transform, radius, pixel_units)
        table_layer = self._build_table_layer(outs_dir, adata, local_frame, transform)

        provenance = self.build_provenance(
            sources=[matrix_path, spatial_dir / HIGHRES_IMAGE, spatial_dir / SCALEFACTORS_FILE],
            extra={"spots": int(adata.n_obs), "features": int(adata.n_vars)},
        )

        return SpatialDataset(
            images=[image_layer],
            labels=[label_layer],
            tables=[table_layer],
            frames={global_frame.name: global_frame, local_frame.name: local_frame},
            global_frame=global_frame.name,
            provenance=provenance,
        )

    def _resolve_outs_dir(self, base: Path) -> Optional[Path]:
        for candidate in OUTS_DIR_CANDIDATES:
            path = (base / candidate).resolve()
            if path.exists() and path.is_dir() and (path / SPATIAL_DIR).exists():
                return path
        return None

    def _resolve_matrix(self, outs_dir: Path) -> Optional[Path]:
        for candidate in MATRIX_FILES:
            path = outs_dir / candidate
            if path.exists():
                return path
        for candidate in MATRIX_DIRS:
            path = outs_dir / candidate
            if path.exists():
                return path
        return None

    def _read_matrix(self, matrix_path: Path) -> ad.AnnData:
        try:
            import scanpy as sc
        except ImportError as exc:  # pragma: no cover - dependency managed by plugin packaging
            raise RuntimeError("scanpy is required to read Visium HD feature matrices.") from exc

        if matrix_path.is_file():
            return sc.read_10x_h5(matrix_path, gex_only=False)
        return sc.read_10x_mtx(matrix_path, gex_only=False)

    def _load_positions(self, spatial_dir: Path) -> pd.DataFrame:
        for candidate in POSITIONS_FILES:
            path = spatial_dir / candidate
            if not path.exists():
                continue
            df = load_tabular_file(path)
            normalised = {_normalise_column(col): col for col in df.columns}
            barcode_col = normalised.get("barcode")
            x_col = normalised.get("pxl_col_in_fullres") or normalised.get("x")
            y_col = normalised.get("pxl_row_in_fullres") or normalised.get("y")
            if not (barcode_col and x_col and y_col):
                continue
            positions = df[[barcode_col, x_col, y_col]].copy()
            positions.columns = ["barcode", "x", "y"]
            return positions
        raise FileNotFoundError("Unable to locate tissue positions for Visium HD dataset.")

    def _load_scalefactors(self, spatial_dir: Path) -> Dict[str, float]:
        scale_path = spatial_dir / SCALEFACTORS_FILE
        if not scale_path.exists():
            return {}
        with scale_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return {key: float(value) for key, value in data.items()}

    def _build_image_layer(
        self,
        image_path: Path,
        local_frame: CoordinateFrame,
        transform: AffineTransform,
        pixel_units: str,
        pixel_size: float,
    ) -> ImageLayer:
        if not image_path.exists():
            raise FileNotFoundError(f"Visium HD image not found: {image_path}")
        return ImageLayer(
            name="visium_hd_image",
            frame=local_frame.name,
            path=image_path,
            pixel_size=(pixel_size, pixel_size, 1.0),
            units=pixel_units,
            channel_names=["RGB"],
            multiscale=[{"path": "scale0", "scale": [1, pixel_size, pixel_size]}],
            transform=transform,
        )

    def _build_label_layer(
        self,
        spots: pd.DataFrame,
        local_frame: CoordinateFrame,
        transform: AffineTransform,
        radius: float,
        pixel_units: str,
    ) -> LabelLayer:
        polygons = [Point(row["x"], row["y"]).buffer(radius).simplify(0.5).wkt for _, row in spots.iterrows()]
        return LabelLayer(
            name="visium_hd_spots",
            frame=local_frame.name,
            crs=pixel_units,
            geometries=polygons,
            properties={"source": "tissue_positions"},
            transform=transform,
        )

    def _build_table_layer(
        self,
        base: Path,
        adata: ad.AnnData,
        local_frame: CoordinateFrame,
        transform: AffineTransform,
    ) -> TableLayer:
        adata_path = base / "visium_hd_expr.h5ad"
        adata.write(adata_path, compression="gzip")
        summary = dataframe_summary(adata.obs.reset_index(drop=True))
        summary.update({"var_count": int(adata.n_vars), "adata_path": str(adata_path)})
        return TableLayer(
            name="visium_hd_table",
            frame=local_frame.name,
            transform=transform,
            adata_path=adata_path,
            obs_columns=list(adata.obs.columns),
            var_columns=list(adata.var.index),
            coordinate_columns=("x", "y"),
            summary=summary,
        )

    @staticmethod
    def _affine_scale(
        scale: float,
    ) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
        return (
            (scale, 0.0, 0.0),
            (0.0, scale, 0.0),
            (0.0, 0.0, 1.0),
        )


__all__ = ["VisiumHDAdapter"]
