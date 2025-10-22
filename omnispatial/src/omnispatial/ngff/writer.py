"""Helpers for writing NGFF and SpatialData datasets."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import numpy as np
from shapely import wkt as shapely_wkt
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from numcodecs import Blosc

from omnispatial.core.model import AffineTransform, SpatialDataset
from omnispatial.utils import read_image_any


def _ensure_parent(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.parent.mkdir(parents=True, exist_ok=True)


def _extract_scale_translation(transform: AffineTransform) -> Tuple[List[float], List[float]]:
    matrix = transform.matrix
    scale = [1.0, float(matrix[1][1]), float(matrix[0][0])]
    translation = [0.0, float(matrix[1][2]), float(matrix[0][2])]
    return scale, translation


def _rasterize_labels(geometries: Iterable[str], shape: Tuple[int, int]) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint32)
    for index, geom_wkt in enumerate(geometries, start=1):
        geometry: BaseGeometry = shapely_wkt.loads(geom_wkt)
        min_x, min_y, max_x, max_y = geometry.bounds
        x_min = max(int(np.floor(min_x)), 0)
        x_max = min(int(np.ceil(max_x)), shape[1])
        y_min = max(int(np.floor(min_y)), 0)
        y_max = min(int(np.ceil(max_y)), shape[0])
        for y in range(y_min, y_max):
            for x in range(x_min, x_max):
                point = Point(x + 0.5, y + 0.5)
                if geometry.covers(point):
                    mask[y, x] = index
    return mask


def _resolve_chunks(
    shape: Tuple[int, ...],
    request: Optional[Tuple[int, ...]],
    *,
    dtype_size: int,
    min_chunk: int = 64,
    target_bytes: int = 8 * 1024 * 1024,
) -> Tuple[int, ...]:
    if request:
        return request

    chunk = list(shape)
    if len(shape) >= 3:
        chunk[0] = 1
    for axis, dim in enumerate(shape):
        chunk[axis] = min(dim, min_chunk if axis >= len(shape) - 2 else dim)

    def chunk_bytes() -> int:
        total = 1
        for value in chunk:
            total *= max(1, value)
        return total * dtype_size

    while chunk_bytes() > target_bytes:
        reduced = False
        for axis in range(len(chunk) - 1, -1, -1):
            if chunk[axis] > 1:
                chunk[axis] = max(1, chunk[axis] // 2)
                reduced = True
                if chunk_bytes() <= target_bytes:
                    break
        if not reduced:
            break
    return tuple(max(1, value) for value in chunk)


def _build_compressor(name: Optional[str], level: int) -> Optional[Blosc]:
    if not name or name.lower() in {"none", "false"}:
        return None
    cname = name.lower()
    if cname not in {"zstd", "lz4", "zlib", "snappy"}:
        raise ValueError(f"Unsupported compressor '{name}'.")
    return Blosc(cname=cname, clevel=max(1, min(level, 9)), shuffle=Blosc.BITSHUFFLE)


def write_ngff(
    dataset: SpatialDataset,
    out_path: str,
    *,
    image_chunks: Optional[Tuple[int, int, int]] = None,
    label_chunks: Optional[Tuple[int, int]] = None,
    compressor: Optional[str] = "zstd",
    compression_level: int = 5,
) -> str:
    """Write the spatial dataset to an NGFF Zarr store."""
    import anndata as ad
    import zarr

    output = Path(out_path)
    _ensure_parent(output)

    root = zarr.open_group(str(output), mode="w")
    images_group = root.create_group("images")
    labels_group = root.create_group("labels")
    tables_group = root.create_group("tables")
    compressor_obj = _build_compressor(compressor, compression_level)
    provenance = dataset.provenance.model_dump() if dataset.provenance else {}
    root.attrs["omnispatial_provenance"] = provenance

    first_image_shape: Tuple[int, int] | None = None

    for image in dataset.images:
        if image.path is None:
            raise ValueError("ImageLayer requires a concrete file path to write NGFF output.")
        data, _ = read_image_any(Path(image.path))
        if data.ndim == 2:
            data = np.expand_dims(data, axis=0)
        chunks = _resolve_chunks(data.shape, image_chunks, dtype_size=data.dtype.itemsize)
        image_group = images_group.create_group(image.name)
        try:
            image_group.create_dataset(
                "0",
                data=data,
                chunks=chunks,
                overwrite=True,
                compressor=compressor_obj,
            )
        except ValueError:
            fallback_chunks = _resolve_chunks(
                data.shape,
                None,
                dtype_size=data.dtype.itemsize,
                min_chunk=32,
            )
            image_group.create_dataset(
                "0",
                data=data,
                chunks=fallback_chunks,
                overwrite=True,
                compressor=compressor_obj,
            )
        scale, translation = _extract_scale_translation(image.transform)
        axes = [
            {"name": "c", "type": "channel"},
            {"name": "y", "type": "space", "unit": image.units},
            {"name": "x", "type": "space", "unit": image.units},
        ]
        image_group.attrs["multiscales"] = [
            {
                "name": image.name,
                "version": "0.4",
                "axes": axes,
                "datasets": [
                    {
                        "path": "0",
                        "coordinateTransformations": [
                            {"type": "scale", "scale": scale},
                            {"type": "translation", "translation": translation},
                        ],
                    }
                ],
            }
        ]
        first_image_shape = data.shape[-2:]

    if dataset.labels:
        if first_image_shape is None:
            raise ValueError("Writing labels requires at least one image to define the reference shape.")
        for label in dataset.labels:
            mask = _rasterize_labels(label.geometries, first_image_shape)
            label_group = labels_group.create_group(label.name)
            chunks = label_chunks or _resolve_chunks(
                mask.shape,
                None,
                dtype_size=mask.dtype.itemsize,
                min_chunk=128,
            )
            try:
                label_group.create_dataset(
                    "0",
                    data=mask,
                    chunks=chunks,
                    overwrite=True,
                    compressor=compressor_obj,
                )
            except ValueError:
                fallback_chunks = _resolve_chunks(
                    mask.shape,
                    None,
                    dtype_size=mask.dtype.itemsize,
                    min_chunk=64,
                )
                label_group.create_dataset(
                    "0",
                    data=mask,
                    chunks=fallback_chunks,
                    overwrite=True,
                    compressor=compressor_obj,
                )
            scale, translation = _extract_scale_translation(label.transform)
            axes = [
                {"name": "y", "type": "space", "unit": label.transform.units},
                {"name": "x", "type": "space", "unit": label.transform.units},
            ]
            label_group.attrs["image-label"] = {
                "version": "0.4",
                "source": {"image": {"path": "../images"}},
            }
            label_group.attrs["multiscales"] = [
                {
                    "name": label.name,
                    "version": "0.4",
                    "axes": axes,
                    "datasets": [
                        {
                            "path": "0",
                            "coordinateTransformations": [
                                {"type": "scale", "scale": scale[1:]},
                                {"type": "translation", "translation": translation[1:]},
                            ],
                        }
                    ],
                }
            ]

    for table in dataset.tables:
        if table.adata_path is None:
            raise ValueError("TableLayer requires adata_path for NGFF export.")
        adata = ad.read_h5ad(table.adata_path)
        table_path = tables_group.create_group(table.name)
        adata.write_zarr(table_path, chunks="auto", overwrite=True)

    return str(output)


def write_spatialdata(dataset: SpatialDataset, out_path: str) -> str:
    """Write the spatial dataset to a SpatialData bundle."""
    import anndata as ad
    import xarray as xr
    from spatialdata import SpatialData
    from spatialdata.io import write_zarr
    from spatialdata.models import Image2DModel, Labels2DModel, TableModel
    import zarr

    output = Path(out_path)
    _ensure_parent(output)

    if not dataset.images:
        raise ValueError("SpatialDataset must contain at least one image to write SpatialData output.")

    image = dataset.images[0]
    if image.path is None:
        raise ValueError("ImageLayer requires a concrete file path to write SpatialData output.")
    image_data, _ = read_image_any(Path(image.path))
    if image_data.ndim == 2:
        image_data = np.expand_dims(image_data, axis=0)
    scale, translation = _extract_scale_translation(image.transform)
    # scale list includes channel axis; drop leading element for spatial axes when constructing model.
    image_da = xr.DataArray(image_data, dims=("c", "y", "x"))
    image_model = Image2DModel.parse(image_da, scale=tuple(scale[1:]), translation=tuple(translation[1:]))

    labels_model_dict = {}
    if dataset.labels:
        mask_shape = image_data.shape[-2:]
        for label in dataset.labels:
            mask = _rasterize_labels(label.geometries, mask_shape)
            lbl_scale, lbl_translation = _extract_scale_translation(label.transform)
            labels_da = xr.DataArray(mask, dims=("y", "x"))
            labels_model = Labels2DModel.parse(
                labels_da,
                scale=tuple(lbl_scale[1:]),
                translation=tuple(lbl_translation[1:]),
            )
            labels_model_dict[label.name] = labels_model

    table_obj = None
    if dataset.tables:
        table_layer = dataset.tables[0]
        if table_layer.adata_path is None:
            raise ValueError("TableLayer requires adata_path for SpatialData export.")
        adata = ad.read_h5ad(table_layer.adata_path)
        if "region" not in adata.obs:
            adata.obs["region"] = dataset.labels[0].name if dataset.labels else image.name
        if "region_key" not in adata.obs:
            region_key = table_layer.obs_columns[0] if table_layer.obs_columns else "cell_id"
            adata.obs["region_key"] = adata.obs[region_key] if region_key in adata.obs else adata.obs.index
        table_obj = TableModel.parse(adata, region=adata.obs["region"].iloc[0], region_key="region_key")

    sdata = SpatialData(images={image.name: image_model}, labels=labels_model_dict, table=table_obj)
    write_zarr(sdata, str(output), overwrite=True)
    root = zarr.open_group(str(output), mode="a")
    if dataset.provenance:
        root.attrs["omnispatial_provenance"] = dataset.provenance.model_dump()
    return str(output)


__all__ = ["write_ngff", "write_spatialdata"]
