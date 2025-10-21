"""Adapter interface definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

from omnispatial.core.model import SpatialDataset


class SpatialAdapter(ABC):
    """Abstract base class for vendor-specific spatial adapters."""

    name: str = "adapter"

    @abstractmethod
    def detect(self, input_path: Path) -> bool:
        """Return True if the adapter can handle the provided input path."""

    @abstractmethod
    def read(self, input_path: Path) -> SpatialDataset:
        """Parse the input path into a canonical SpatialDataset."""

    @abstractmethod
    def metadata(self) -> Dict[str, Any]:
        """Return metadata describing the adapter, vendor, and supported modalities."""


__all__ = ["SpatialAdapter"]
