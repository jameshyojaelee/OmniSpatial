"""Canonical spatial omics data model for OmniSpatial."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator
from shapely import wkt
from shapely.geometry.base import BaseGeometry

from omnispatial.utils.io import geometries_to_wkt

Matrix3x3 = Tuple[
    Tuple[float, float, float],
    Tuple[float, float, float],
    Tuple[float, float, float],
]


class AffineTransform(BaseModel):
    """Explicit 3x3 affine transform with unit annotations."""

    matrix: Matrix3x3 = Field(..., description="Column-major 3x3 affine matrix.")
    units: str = Field(..., description="Units for the transform distances, e.g., micrometer.")
    source: str = Field(..., description="Source coordinate frame name.")
    target: str = Field(..., description="Target coordinate frame name.")

    model_config = {"validate_assignment": True}

    @field_validator("matrix")
    @classmethod
    def _validate_matrix(cls, value: Matrix3x3) -> Matrix3x3:
        if len(value) != 3 or any(len(row) != 3 for row in value):
            msg = "Affine transform must be a 3x3 matrix."
            raise ValueError(msg)
        if not np.isclose(value[2][2], 1.0):
            msg = "Affine transform must have homogeneous bottom-right entry equal to 1."
            raise ValueError(msg)
        if not np.isclose(value[2][0], 0.0) or not np.isclose(value[2][1], 0.0):
            msg = "Affine transform must preserve homogeneous coordinates (last row [0, 0, 1])."
            raise ValueError(msg)
        return value

    def to_numpy(self) -> np.ndarray:
        """Return the matrix as a NumPy array."""
        return np.array(self.matrix, dtype=float)

    def compose(self, other: "AffineTransform") -> "AffineTransform":
        """Compose this transform after another, ensuring frames are compatible."""
        if other.target != self.source:
            msg = (
                f"Cannot compose transforms: other.target '{other.target}' != self.source '{self.source}'."
            )
        elif other.units != self.units:
            msg = "Transforms must share identical units to compose."
        else:
            msg = ""
        if msg:
            raise ValueError(msg)
        result_matrix = self.to_numpy() @ other.to_numpy()
        return AffineTransform(
            matrix=tuple(tuple(float(entry) for entry in row) for row in result_matrix),
            units=self.units,
            source=other.source,
            target=self.target,
        )


class CoordinateFrame(BaseModel):
    """Named coordinate frame with axis ordering and units."""

    name: str
    axes: Tuple[str, str, str]
    units: Tuple[str, str, str]
    description: Optional[str] = None


class ImageLayer(BaseModel):
    """Image layer referencing a raster pyramid."""

    name: str
    frame: str = Field(..., description="Coordinate frame in which the raster is defined.")
    path: Optional[Path] = Field(
        default=None, description="Path to the image array or group within a Zarr store."
    )
    array_uri: Optional[str] = Field(
        default=None, description="Logical handle for in-memory arrays or remote references."
    )
    pixel_size: Tuple[float, float, float] = Field(
        ..., description="Physical pixel size along (x, y, z) axes."
    )
    units: str = Field(..., description="Units associated with the pixel size (e.g., micrometer).")
    channel_names: List[str] = Field(default_factory=list, description="Ordered channel labels.")
    multiscale: List[Dict[str, object]] = Field(
        default_factory=list, description="Multiscale descriptors for OME-NGFF."
    )
    transform: AffineTransform = Field(..., description="Transform from frame to global.")

    model_config = {"validate_assignment": True}

    @model_validator(mode="after")
    def _validate_paths(self) -> "ImageLayer":
        if not self.path and not self.array_uri:
            msg = "Either 'path' or 'array_uri' must be provided for an ImageLayer."
            raise ValueError(msg)
        return self


class LabelLayer(BaseModel):
    """Segmentation labels or vector geometries aligned to an image frame."""

    name: str
    frame: str
    crs: str = Field(..., description="Coordinate reference system identifier.")
    geometries: List[str] = Field(
        default_factory=list,
        description="Geometries stored as WKT strings for portability.",
    )
    properties: Dict[str, object] = Field(
        default_factory=dict, description="Optional per-layer properties."
    )
    transform: AffineTransform

    model_config = {"validate_assignment": True}

    @field_validator("geometries", mode="before")
    @classmethod
    def _ensure_wkt(cls, value: Iterable[BaseGeometry | str]) -> List[str]:
        return geometries_to_wkt(value)

    def iter_geometries(self) -> Iterable[BaseGeometry]:
        """Yield Shapely geometries for the stored WKT strings."""
        for geom_wkt in self.geometries:
            yield wkt.loads(geom_wkt)


class TableLayer(BaseModel):
    """Tabular layers storing AnnData-backed measurements."""

    name: str
    frame: str
    transform: AffineTransform
    adata_path: Optional[Path] = Field(
        default=None, description="Path to an AnnData file (e.g., .h5ad) on disk."
    )
    obs_columns: List[str] = Field(
        default_factory=list, description="Names of observation-level metadata columns."
    )
    var_columns: List[str] = Field(
        default_factory=list, description="Names of feature-level metadata columns."
    )
    coordinate_columns: Tuple[str, str] = Field(
        default=("x", "y"), description="Columns describing x/y coordinates in table space."
    )
    summary: Dict[str, object] = Field(
        default_factory=dict, description="Additional summary statistics (e.g., counts)."
    )

    model_config = {"validate_assignment": True}

    @property
    def cell_count(self) -> Optional[int]:
        """Return the number of observations if stored in the summary."""
        value = self.summary.get("obs_count")
        return int(value) if value is not None else None


class ProvenanceMetadata(BaseModel):
    """Capture provenance for a SpatialDataset."""

    adapter: str = Field(..., description="Registered adapter name responsible for the dataset.")
    version: str = Field(..., description="OmniSpatial version used to generate the dataset.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp of creation.")
    source_files: List[str] = Field(default_factory=list, description="Paths of input files used during conversion.")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Adapter-specific provenance metadata.")

    model_config = {"validate_assignment": True}


class SpatialDataset(BaseModel):
    """Aggregate of image, label, and table layers with shared coordinate frames."""

    images: List[ImageLayer] = Field(default_factory=list)
    labels: List[LabelLayer] = Field(default_factory=list)
    tables: List[TableLayer] = Field(default_factory=list)
    frames: Dict[str, CoordinateFrame] = Field(default_factory=dict)
    global_frame: str = Field(default="global", description="Name of the global reference frame.")
    provenance: Optional[ProvenanceMetadata] = Field(
        default=None,
        description="Provenance metadata describing the adapter run and source files.",
    )

    model_config = {"validate_assignment": True}

    @model_validator(mode="after")
    def _validate_frames(self) -> "SpatialDataset":
        if self.global_frame not in self.frames:
            msg = f"Global frame '{self.global_frame}' must be defined in frames registry."
            raise ValueError(msg)
        referenced = {
            layer.frame for layer in (*self.images, *self.labels, *self.tables)
        } | {
            layer.transform.source for layer in (*self.images, *self.labels, *self.tables)
        } | {
            layer.transform.target for layer in (*self.images, *self.labels, *self.tables)
        }
        undefined = referenced - set(self.frames)
        if undefined:
            missing = ", ".join(sorted(undefined))
            msg = f"Referenced frames missing from registry: {missing}"
            raise ValueError(msg)
        if self.provenance is None:
            msg = "SpatialDataset.provenance must be provided."
            raise ValueError(msg)
        return self

    def frame_names(self) -> List[str]:
        """Return the ordered list of coordinate frame names."""
        return list(self.frames)


__all__ = [
    "AffineTransform",
    "CoordinateFrame",
    "ImageLayer",
    "LabelLayer",
    "TableLayer",
    "SpatialDataset",
    "ProvenanceMetadata",
]
