"""High-level Python API for OmniSpatial conversions and validation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Optional, Sequence, Tuple

from omnispatial.adapters import SpatialAdapter, get_adapter, iter_adapters, load_adapter_plugins
from omnispatial.core.model import SpatialDataset
from omnispatial.ngff import write_ngff, write_spatialdata
from omnispatial.validate import ValidationReport, validate_bundle as _validate_bundle

OutputFormat = Literal["ngff", "spatialdata"]


class AdapterNotFoundError(LookupError):
    """Raised when no adapter matches the provided dataset or vendor."""


@dataclass(frozen=True)
class ConversionResult:
    """Outcome of a conversion request."""

    adapter: str
    format: OutputFormat
    output_path: Optional[Path]
    dataset: SpatialDataset


def _normalise_chunks(chunks: Optional[Sequence[int]], expected_dims: int) -> Optional[Tuple[int, ...]]:
    if chunks is None:
        return None
    values = tuple(int(value) for value in chunks)
    if len(values) != expected_dims:
        raise ValueError(f"Expected {expected_dims} chunk dimensions, received {len(values)}")
    return values


def _adapter_by_name(name: str) -> Optional[SpatialAdapter]:
    load_adapter_plugins()
    normalised = name.lower()
    for adapter_cls in iter_adapters():
        if adapter_cls.name == normalised:
            return adapter_cls()
    return None


def _resolve_adapter(input_path: Path, vendor: Optional[str]) -> SpatialAdapter:
    if vendor:
        adapter = _adapter_by_name(vendor)
        if adapter is None:
            raise AdapterNotFoundError(f"Unknown adapter '{vendor}'.")
        return adapter

    adapter = get_adapter(input_path)
    if adapter is None:
        raise AdapterNotFoundError(
            "Could not detect a compatible adapter for the provided dataset. "
            "Specify 'vendor' to select an adapter explicitly."
        )
    return adapter


def convert(
    input_path: Path | str,
    out: Path | str,
    *,
    vendor: Optional[str] = None,
    output_format: OutputFormat = "ngff",
    dry_run: bool = False,
    image_chunks: Optional[Sequence[int]] = None,
    label_chunks: Optional[Sequence[int]] = None,
    compressor: Optional[str] = "zstd",
    compression_level: int = 5,
) -> ConversionResult:
    """Convert a spatial assay into NGFF or SpatialData formats."""

    input_path = Path(input_path)
    out_path = Path(out)
    fmt = output_format.lower()
    if fmt not in {"ngff", "spatialdata"}:
        raise ValueError("output_format must be 'ngff' or 'spatialdata'.")

    adapter = _resolve_adapter(input_path, vendor)
    dataset = adapter.read(input_path)

    if dry_run:
        return ConversionResult(adapter=adapter.name, format=fmt, output_path=None, dataset=dataset)

    if fmt == "ngff":
        target = write_ngff(
            dataset,
            str(out_path),
            image_chunks=_normalise_chunks(image_chunks, 3),
            label_chunks=_normalise_chunks(label_chunks, 2),
            compressor=compressor,
            compression_level=compression_level,
        )
    else:
        target = write_spatialdata(dataset, str(out_path))

    return ConversionResult(adapter=adapter.name, format=fmt, output_path=Path(target), dataset=dataset)


async def convert_async(*args, **kwargs) -> ConversionResult:
    """Asynchronous wrapper around :func:`convert` using a worker thread."""

    return await asyncio.to_thread(convert, *args, **kwargs)


def validate(
    bundle: Path | str,
    *,
    output_format: OutputFormat = "ngff",
) -> ValidationReport:
    """Validate an NGFF or SpatialData bundle and return the structured report."""

    fmt = output_format.lower()
    if fmt not in {"ngff", "spatialdata"}:
        raise ValueError("output_format must be 'ngff' or 'spatialdata'.")
    return _validate_bundle(Path(bundle), fmt)


async def validate_async(*args, **kwargs) -> ValidationReport:
    """Asynchronous wrapper around :func:`validate` using a worker thread."""

    return await asyncio.to_thread(validate, *args, **kwargs)


def available_adapter_names() -> Iterable[str]:
    """Return the names of all discovered adapters (including plugin entry points)."""

    load_adapter_plugins()
    return tuple(adapter_cls.name for adapter_cls in iter_adapters())


__all__ = [
    "AdapterNotFoundError",
    "ConversionResult",
    "OutputFormat",
    "available_adapter_names",
    "convert",
    "convert_async",
    "validate",
    "validate_async",
]
