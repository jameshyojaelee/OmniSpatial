"""Helpers for writing NGFF datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import numpy as np


class NGFFWriter:
    """Minimal writer that prepares an empty NGFF-compliant Zarr hierarchy."""

    def __init__(self, store_path: Path) -> None:
        """Store the target path for the NGFF dataset."""
        self._store_path = store_path

    def initialize(self, metadata: Dict[str, Any] | None = None) -> None:
        """Create a placeholder NGFF hierarchy with basic multiscale metadata."""
        import zarr

        metadata = metadata or {}
        root = zarr.open_group(store=str(self._store_path), mode="w")
        pyramid = root.create_group("0")
        pyramid.array(
            name="labels",
            data=np.zeros((1, 1, 1), dtype="uint8"),
            compressor=None,
            chunks=(1, 1, 1),
        )
        root.attrs.update(metadata)
        root.attrs.setdefault("multiscales", [])


__all__ = ["NGFFWriter"]
