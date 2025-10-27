"""Adapter registry primitives."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Type

from omnispatial.adapters.base import SpatialAdapter
from omnispatial.core.metadata import SampleMetadata

LOG = logging.getLogger(__name__)

_ENTRYPOINT_GROUP = "omnispatial.adapters"
_REGISTERED_ADAPTERS: Dict[str, Type[SpatialAdapter]] = {}
_ENTRYPOINTS_LOADED = False


def register_adapter(adapter_cls: Type[SpatialAdapter]) -> Type[SpatialAdapter]:
    """Decorator to register a SpatialAdapter implementation."""
    name = getattr(adapter_cls, "name", adapter_cls.__name__).lower()
    adapter_cls.name = name  # type: ignore[attr-defined]
    _REGISTERED_ADAPTERS[name] = adapter_cls
    return adapter_cls


def _select_entry_points(group: str):
    try:
        entry_points = metadata.entry_points()
    except Exception as exc:  # pragma: no cover - importlib edge case
        LOG.debug("Unable to enumerate adapter entry points: %s", exc)
        return []
    select = getattr(entry_points, "select", None)
    if callable(select):  # Python 3.10+
        return list(select(group=group))
    # Python 3.9 compatibility
    return [entry for entry in entry_points if getattr(entry, "group", None) == group]


def load_adapter_plugins(force: bool = False) -> None:
    """Load adapter implementations exposed via entry points."""
    global _ENTRYPOINTS_LOADED
    if _ENTRYPOINTS_LOADED and not force:
        return

    _ENTRYPOINTS_LOADED = True
    for entry in _select_entry_points(_ENTRYPOINT_GROUP):
        try:
            resolved = entry.load()
        except Exception as exc:  # pragma: no cover - importlib edge case
            LOG.warning("Failed to load adapter entry point '%s': %s", entry.name, exc)
            continue

        adapter_cls: Optional[Type[SpatialAdapter]] = None
        if isinstance(resolved, type) and issubclass(resolved, SpatialAdapter):
            adapter_cls = resolved
        elif callable(resolved):
            candidate = resolved()
            if isinstance(candidate, type) and issubclass(candidate, SpatialAdapter):
                adapter_cls = candidate

        if adapter_cls is None:
            LOG.warning(
                "Entry point '%s' did not resolve to a SpatialAdapter subclass.",
                entry.name,
            )
            continue
        register_adapter(adapter_cls)


def iter_adapters() -> Iterator[Type[SpatialAdapter]]:
    """Yield all registered adapter classes."""
    load_adapter_plugins()
    yield from _REGISTERED_ADAPTERS.values()


def available_adapters() -> List[str]:
    """Return the names of all registered adapters."""
    load_adapter_plugins()
    return list(_REGISTERED_ADAPTERS)


def get_adapter(input_path: str | Path) -> Optional[SpatialAdapter]:
    """Return the first adapter that detects the provided input path."""
    load_adapter_plugins()
    path = Path(input_path)
    for adapter_cls in iter_adapters():
        adapter = adapter_cls()
        try:
            if adapter.detect(path):
                return adapter
        except FileNotFoundError:
            continue
        except Exception:  # pragma: no cover - adapter-specific failure
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

        load_adapter_plugins()
        return cls()

    def register(self, adapter_cls: Type[SpatialAdapter]) -> None:
        """Register a SpatialAdapter subclass."""
        name = getattr(adapter_cls, "name", adapter_cls.__name__).lower()
        self._entries[name] = adapter_cls

    def matching(
        self,
        metadata: SampleMetadata,
        input_path: Path,
        *,
        require_detect: bool = True,
    ) -> Iterator[str]:
        """Yield adapter names that can operate on the provided metadata.

        Args:
            metadata: Sample metadata describing the assay.
            input_path: Filesystem path to the dataset under consideration.
            require_detect: When True (default), only adapters whose ``detect`` method
                returns True are yielded. When False, adapters whose modalities match
                the assay are also included as a metadata-only fallback.
        """
        metadata_assay = metadata.assay.lower()
        for name, adapter_cls in self._entries.items():
            adapter = adapter_cls()
            info = adapter.metadata()
            modalities = [str(mod).lower() for mod in info.get("modalities", [])]
            try:
                detected = adapter.detect(input_path)
            except Exception:
                detected = False
            if detected:
                yield name
                continue
            if not require_detect and (not modalities or metadata_assay in modalities):
                yield name


# Ensure built-in adapters are registered when the registry module is imported.
from . import cosmx as _cosmx  # noqa: F401
from . import merfish as _merfish  # noqa: F401
from . import xenium as _xenium  # noqa: F401

load_adapter_plugins()


__all__ = [
    "AdapterRegistry",
    "AdapterSpec",
    "available_adapters",
    "get_adapter",
    "iter_adapters",
    "load_adapter_plugins",
    "register_adapter",
]
