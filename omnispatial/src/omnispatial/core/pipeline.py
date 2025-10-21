"""High-level conversion pipeline primitives."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from rich.console import Console

from omnispatial.adapters.registry import AdapterRegistry
from omnispatial.core.metadata import SampleMetadata

console = Console()


class ConversionPipeline:
    """A minimal conversion pipeline that delegates work to registered adapters."""

    def __init__(self, adapters: AdapterRegistry | None = None) -> None:
        """Create a pipeline bound to an adapter registry."""
        self._registry = adapters or AdapterRegistry.default()

    def convert(self, input_path: Path, output_path: Path, metadata: SampleMetadata) -> None:
        """Convert the input path using all adapters compatible with the metadata."""
        console.log("Collecting compatible adapters", style="green")
        matches: Iterable[str] = self._registry.matching(metadata=metadata, input_path=input_path)
        for name in matches:
            console.log(f"Adapter '{name}' is not implemented yet.", style="yellow")
        console.log(f"Writing placeholder outputs to {output_path}", style="cyan")


__all__ = ["ConversionPipeline"]
