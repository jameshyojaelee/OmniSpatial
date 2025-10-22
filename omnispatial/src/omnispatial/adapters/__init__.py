"""Adapter exports for OmniSpatial conversions."""

from .base import SpatialAdapter
from .registry import (
    AdapterRegistry,
    AdapterSpec,
    available_adapters,
    get_adapter,
    iter_adapters,
    load_adapter_plugins,
    register_adapter,
)

__all__ = [
    "AdapterRegistry",
    "AdapterSpec",
    "SpatialAdapter",
    "available_adapters",
    "get_adapter",
    "iter_adapters",
    "load_adapter_plugins",
    "register_adapter",
]
