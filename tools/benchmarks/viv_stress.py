#!/usr/bin/env python3
"""Simulate Viv tile loading by sampling random chunks from an OME-NGFF image."""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import zarr


def discover_image(store: zarr.Group) -> Tuple[str, zarr.Array]:
    """Return the first multiscale array within the images group."""
    images = store.get("images")
    if images is None or not isinstance(images, zarr.Group):
        raise RuntimeError("Store does not contain an 'images' group.")
    for name, group in images.groups():
        if not isinstance(group, zarr.Group):
            continue
        # Prefer the highest resolution scale (usually '0').
        for scale_name in sorted(group.array_keys()):
            array = group.get(scale_name)
            if isinstance(array, zarr.Array):
                return f"{name}/{scale_name}", array
    raise RuntimeError("Unable to locate multiscale image array in store.")


def sample_chunks(array: zarr.Array, samples: int) -> Dict[str, float]:
    """Read random chunks from the array and collect throughput metrics."""
    chunk_sizes = array.chunks
    shape = array.shape
    dtype_size = array.dtype.itemsize
    timings: List[float] = []
    bytes_read: List[int] = []

    for _ in range(samples):
        slices = []
        for dim, (dim_size, chunk) in enumerate(zip(shape, chunk_sizes)):
            max_index = max(1, math.ceil(dim_size / chunk))
            chunk_index = random.randrange(max_index)
            start = chunk_index * chunk
            stop = min(start + chunk, dim_size)
            slices.append(slice(start, stop))
        start_time = time.perf_counter()
        block = array[tuple(slices)]
        duration = time.perf_counter() - start_time
        timings.append(duration)
        bytes_read.append(block.size * dtype_size)

    total_bytes = sum(bytes_read)
    total_time = sum(timings)
    return {
        "samples": samples,
        "avg_mb_per_s": (total_bytes / (1024**2)) / total_time if total_time else 0.0,
        "avg_latency_ms": (total_time / samples) * 1000 if samples else 0.0,
        "bytes_read_mb": total_bytes / (1024**2),
        "chunk_shape": chunk_sizes,
        "array_shape": shape,
        "dtype": str(array.dtype),
    }


def create_synthetic_store(path: Path, size: int, channels: int) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    root = zarr.open_group(str(path), mode="w")
    img_group = root.create_group("images")
    dataset = img_group.create_group("synthetic")
    multiscale = dataset.create_group("0")
    shape = (channels, size, size)
    chunks = (1, min(512, size), min(512, size))
    array = multiscale.create_dataset(
        "0",
        shape=shape,
        chunks=chunks,
        dtype="uint16",
        compressor=zarr.Blosc(cname="zstd", clevel=5, shuffle=zarr.Blosc.BITSHUFFLE),
    )
    rng = np.random.default_rng(42)
    array[:] = rng.integers(0, 4096, size=shape, dtype="uint16")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("store", type=Path, help="Path or URL to an OME-NGFF store.")
    parser.add_argument("--samples", type=int, default=128, help="Number of random chunks to read (default: 128).")
    parser.add_argument("--report", type=Path, help="Optional JSON file to write metrics.")
    parser.add_argument("--synthetic", type=int, help="Generate a synthetic pyramid with the provided edge length in pixels.")
    parser.add_argument("--channels", type=int, default=4, help="Channel count for synthetic pyramids (default: 4).")
    args = parser.parse_args()

    if args.synthetic:
        create_synthetic_store(args.store, args.synthetic, args.channels)

    store = zarr.open_group(str(args.store), mode="r")
    image_path, array = discover_image(store)
    metrics = sample_chunks(array, samples=args.samples)
    metrics.update({"store": str(args.store), "image_path": image_path})
    print(json.dumps(metrics, indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(metrics, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
