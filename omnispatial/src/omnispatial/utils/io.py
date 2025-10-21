"""I/O helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml
import zarr
from pandas import DataFrame
from pandas.api.types import is_numeric_dtype
from shapely import wkt
from shapely.geometry.base import BaseGeometry
import tifffile


def load_yaml(path: Path) -> dict:
    """Load a YAML file into a dictionary."""
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_tabular_file(path: Path) -> DataFrame:
    """Load a CSV, TSV, or Parquet file into a DataFrame with basic validation."""
    if not path.exists():
        raise FileNotFoundError(f"Tabular file does not exist: {path}")
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        df = pd.read_csv(path)
    elif suffix in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported tabular format for file: {path}")
    if df.empty:
        raise ValueError(f"Table at {path} is empty.")
    return df


def load_spatial_table(path: Path, coordinate_columns: Sequence[str] = ("x", "y")) -> DataFrame:
    """Load a spatial transcriptomics table with strict coordinate validation."""
    df = load_tabular_file(path)
    missing = [col for col in coordinate_columns if col not in df.columns]
    if missing:
        missing_cols = ", ".join(missing)
        raise ValueError(f"Missing required coordinate columns: {missing_cols}")
    for column in coordinate_columns:
        if not is_numeric_dtype(df[column]):
            raise TypeError(f"Coordinate column '{column}' must be numeric.")
    return df


def dataframe_summary(df: DataFrame) -> dict:
    """Return a compact summary for storage in metadata."""
    return {"obs_count": int(df.shape[0]), "columns": list(df.columns)}


def geometries_to_wkt(geometries: Iterable[BaseGeometry | str]) -> List[str]:
    """Normalise a set of geometries to WKT strings."""
    serialised: List[str] = []
    for geometry in geometries:
        if isinstance(geometry, BaseGeometry):
            serialised.append(geometry.wkt)
        elif isinstance(geometry, str):
            # Validate string serialisation
            wkt.loads(geometry)
            serialised.append(geometry)
        else:
            raise TypeError("Geometries must be shapely geometries or WKT strings.")
    return serialised


def geometries_from_wkt(wkt_strings: Iterable[str]) -> List[BaseGeometry]:
    """Materialise WKT strings as Shapely geometries."""
    return [wkt.loads(value) for value in wkt_strings]


def polygons_from_wkt(wkt_strings: Iterable[str]) -> List[BaseGeometry]:
    """Return geometries from WKT and ensure they are polygonal."""
    geometries = [wkt.loads(value) for value in wkt_strings]
    for geometry in geometries:
        if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise TypeError("Expected polygonal geometry in WKT string.")
    return geometries


def read_table_csv(path: Path) -> DataFrame:
    """Load a CSV file into a DataFrame with strict validation."""
    if path.suffix.lower() != ".csv":
        raise ValueError(f"Expected CSV file, received: {path}")
    return load_tabular_file(path)


def read_image_any(path: Path) -> Tuple[np.ndarray, dict]:
    """Load a TIFF or Zarr array and return the numpy data and metadata."""
    if not path.exists():
        raise FileNotFoundError(f"Image resource not found: {path}")
    if path.suffix.lower() in {".tif", ".tiff"}:
        data = tifffile.imread(path)
        return np.asarray(data), {"format": "tiff"}
    if path.suffix.lower() in {".zarr"} or path.is_dir():
        store = zarr.open(path, mode="r")
        if hasattr(store, "shape"):
            data = np.asarray(store)
        else:
            array_keys = list(getattr(store, "array_keys", lambda: [])())
            if not array_keys:
                array_keys = [key for key in store]  # type: ignore[index]
            if not array_keys:
                raise ValueError(f"No arrays found in Zarr store: {path}")
            first_key = sorted(array_keys)[0]
            data = np.asarray(store[first_key])
        return data, {"format": "zarr"}
    raise ValueError(f"Unsupported image format for: {path}")


__all__ = [
    "dataframe_summary",
    "geometries_from_wkt",
    "geometries_to_wkt",
    "polygons_from_wkt",
    "load_spatial_table",
    "load_tabular_file",
    "load_yaml",
    "read_table_csv",
    "read_image_any",
]
