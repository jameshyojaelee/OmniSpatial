"""Adapter interface definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from omnispatial import __version__
from omnispatial.core.model import ProvenanceMetadata, SpatialDataset


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

    def build_provenance(
        self,
        sources: Iterable[Path | str],
        extra: Optional[Dict[str, Any]] = None,
    ) -> ProvenanceMetadata:
        """Construct provenance metadata for downstream consumers."""
        source_strings = sorted({str(Path(source)) for source in sources})
        return ProvenanceMetadata(
            adapter=self.name,
            version=__version__,
            source_files=source_strings,
            extra=extra or {},
        )


__all__ = ["ProvenanceMetadata", "SpatialAdapter"]
