"""Helpers for writing NGFF and SpatialData datasets."""

from __future__ import annotations

import shutil
from itertools import product
from pathlib import Path
from typing import Any, Iterable, Iterator, List, NamedTuple, Optional, Tuple

import numpy as np
import tifffile
from numcodecs import Blosc
from rasterio import features
from shapely import wkt as shapely_wkt
from shapely.geometry.base import BaseGeometry

from omnispatial.core.model import AffineTransform, SpatialDataset
from omnispatial.utils import read_image_any


class _ImageSource(NamedTuple):
    data: object
    shape: Tuple[int, ...]
    dtype: np.dtype
    expanded: bool


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
    """Rasterise polygon geometries into a label mask with uint32 dtype."""
    height, width = shape
    if height <= 0 or width <= 0:
        raise ValueError("Raster shape must be positive and non-zero.")

    shapes: List[Tuple[BaseGeometry, int]] = []
    for index, geom_wkt in enumerate(geometries, start=1):
        geometry = shapely_wkt.loads(geom_wkt)
        if geometry.is_empty:
            raise ValueError("Encountered empty geometry while rasterising labels.")
        if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise TypeError(f"Label geometry must be polygonal, received '{geometry.geom_type}'.")
        shapes.append((geometry, index))

    if not shapes:
        return np.zeros(shape, dtype=np.uint32)

    mask = features.rasterize(
        shapes=shapes,
        out_shape=shape,
        dtype="uint32",
        fill=0,
        default_value=0,
        all_touched=True,
    )
    return mask


def _prepare_image_source(path: Path) -> _ImageSource:
    """Open an image resource for chunked reading."""
    suffix = path.suffix.lower()
    if suffix in {".tif", ".tiff"}:
        array = tifffile.memmap(path)
        shape = array.shape
        expanded = False
        if array.ndim == 2:
            shape = (1, *shape)
            expanded = True
        return _ImageSource(data=array, shape=tuple(int(dim) for dim in shape), dtype=np.dtype(array.dtype), expanded=expanded)

    if suffix == ".zarr" or path.is_dir():
        import zarr  # local import to avoid mandatory dependency at module import

        try:
            store = zarr.open(str(path), mode="r")
        except Exception:
            store = None
        array = None
        if store is not None and hasattr(store, "shape"):
            array = store
        else:
            group = zarr.open_group(str(path), mode="r")
            array_keys = list(getattr(group, "array_keys", lambda: [])())
            if not array_keys:
                array_keys = [key for key in group]  # type: ignore[index]
            if not array_keys:
                raise ValueError(f"No arrays found in Zarr store: {path}")
            first_key = sorted(array_keys)[0]
            array = group[first_key]
        shape = array.shape
        expanded = False
        if array.ndim == 2:
            shape = (1, *shape)
            expanded = True
        return _ImageSource(data=array, shape=tuple(int(dim) for dim in shape), dtype=np.dtype(array.dtype), expanded=expanded)

    data, _ = read_image_any(path)
    if data.ndim == 2:
        data = np.expand_dims(data, axis=0)
    return _ImageSource(
        data=data,
        shape=tuple(int(dim) for dim in data.shape),
        dtype=np.dtype(data.dtype),
        expanded=False,
    )


def _chunk_slices(shape: Tuple[int, ...], chunk_shape: Tuple[int, ...]) -> Iterator[Tuple[slice, ...]]:
    steps = []
    for dim, chunk in zip(shape, chunk_shape):
        step = int(chunk) if chunk and chunk > 0 else int(dim)
        steps.append(step)
    ranges = [range(0, dim, step) for dim, step in zip(shape, steps)]
    for starts in product(*ranges):
        slices = tuple(slice(start, min(start + step, dim)) for start, step, dim in zip(starts, steps, shape))
        yield slices


def _copy_source_to_zarr(source: _ImageSource, dest: Any) -> None:
    chunk_shape = dest.chunks
    shape = dest.shape
    for selection in _chunk_slices(shape, chunk_shape):
        if source.expanded:
            src_selection = selection[1:]
            data = np.asarray(source.data[src_selection])  # type: ignore[index]
            data = np.expand_dims(data, axis=0)
        else:
            data = np.asarray(source.data[selection])  # type: ignore[index]
        dest[selection] = data


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
        source = _prepare_image_source(Path(image.path))
        chunks = _resolve_chunks(source.shape, image_chunks, dtype_size=source.dtype.itemsize)
        image_group = images_group.create_group(image.name)
        try:
            image_dataset = image_group.create_dataset(
                "0",
                shape=source.shape,
                dtype=source.dtype,
                chunks=chunks,
                overwrite=True,
                compressor=compressor_obj,
            )
        except ValueError:
            fallback_chunks = _resolve_chunks(
                source.shape,
                None,
                dtype_size=source.dtype.itemsize,
                min_chunk=32,
            )
            image_dataset = image_group.create_dataset(
                "0",
                shape=source.shape,
                dtype=source.dtype,
                chunks=fallback_chunks,
                overwrite=True,
                compressor=compressor_obj,
            )
        _copy_source_to_zarr(source, image_dataset)
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
        first_image_shape = source.shape[-2:]

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
