"""Adapter registry primitives."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Type

from omnispatial.adapters.base import SpatialAdapter
from omnispatial.core.metadata import SampleMetadata

_REGISTERED_ADAPTERS: Dict[str, Type[SpatialAdapter]] = {}


def register_adapter(adapter_cls: Type[SpatialAdapter]) -> Type[SpatialAdapter]:
    """Decorator to register a SpatialAdapter implementation."""
    name = getattr(adapter_cls, "name", adapter_cls.__name__).lower()
    adapter_cls.name = name  # type: ignore[attr-defined]
    _REGISTERED_ADAPTERS[name] = adapter_cls
    return adapter_cls


def iter_adapters() -> Iterator[Type[SpatialAdapter]]:
    """Yield all registered adapter classes."""
    yield from _REGISTERED_ADAPTERS.values()


def available_adapters() -> List[str]:
    """Return the names of all registered adapters."""
    return list(_REGISTERED_ADAPTERS)


def get_adapter(input_path: str | Path) -> Optional[SpatialAdapter]:
    """Return the first adapter that detects the provided input path."""
    path = Path(input_path)
    for adapter_cls in iter_adapters():
        adapter = adapter_cls()
        try:
            if adapter.detect(path):
                return adapter
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return None


@dataclass(frozen=True)
class AdapterSpec:
    """Description of a converter adapter (legacy compatibility)."""

    name: str
    modalities: List[str]
    vendor: str


class AdapterRegistry:
    """In-memory registry wrapper that supports legacy matching workflows."""

    def __init__(self, adapters: Iterable[Type[SpatialAdapter]] | None = None) -> None:
        """Initialize the registry with optional adapter classes."""
        self._entries: Dict[str, Type[SpatialAdapter]] = {}
        adapters = adapters or list(iter_adapters())
        for adapter_cls in adapters:
            self.register(adapter_cls)

    @classmethod
    def default(cls) -> "AdapterRegistry":
        """Create a registry seeded with all registered adapters."""
        # Ensure built-in adapters are imported so they register themselves.
        from . import cosmx, merfish, xenium  # noqa: F401

        return cls()

    def register(self, adapter_cls: Type[SpatialAdapter]) -> None:
        """Register a SpatialAdapter subclass."""
        name = getattr(adapter_cls, "name", adapter_cls.__name__).lower()
        self._entries[name] = adapter_cls

    def matching(self, metadata: SampleMetadata, input_path: Path) -> Iterator[str]:
        """Yield adapter names that could operate on the provided metadata."""
        metadata_assay = metadata.assay.lower()
        for name, adapter_cls in self._entries.items():
            adapter = adapter_cls()
            info = adapter.metadata()
            modalities = [str(mod).lower() for mod in info.get("modalities", [])]
            try:
                detected = adapter.detect(input_path)
            except Exception:
                detected = False
            if detected or not modalities or metadata_assay in modalities:
                yield name


# Ensure built-in adapters are registered when the registry module is imported.
from . import cosmx as _cosmx  # noqa: F401
from . import merfish as _merfish  # noqa: F401
from . import xenium as _xenium  # noqa: F401


__all__ = [
    "AdapterRegistry",
    "AdapterSpec",
    "available_adapters",
    "get_adapter",
    "iter_adapters",
    "register_adapter",
]
