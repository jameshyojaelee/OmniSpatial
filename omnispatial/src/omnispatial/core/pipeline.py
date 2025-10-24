"""High-level conversion pipeline primitives."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from rich.console import Console

from omnispatial.adapters.registry import AdapterRegistry
from omnispatial.api import ConversionResult, convert as api_convert
from omnispatial.core.metadata import SampleMetadata

console = Console()


class ConversionPipeline:
    """A minimal conversion pipeline that delegates work to registered adapters."""

    def __init__(self, adapters: AdapterRegistry | None = None) -> None:
        """Create a pipeline bound to an adapter registry."""
        self._registry = adapters or AdapterRegistry.default()

    def convert(self, input_path: Path, output_path: Path, metadata: SampleMetadata) -> List[ConversionResult]:
        """Convert the input path using all adapters compatible with the metadata."""
        input_path = Path(input_path)
        output_path = Path(output_path)
        console.log("Collecting compatible adapters", style="green")
        matches: Iterable[str] = self._registry.matching(metadata=metadata, input_path=input_path)
        adapter_names = list(dict.fromkeys(matches))
        if not adapter_names:
            raise RuntimeError("No adapters matched the provided metadata and input path.")

        output_path.mkdir(parents=True, exist_ok=True)
        console.log(f"Selected adapters: {', '.join(adapter_names)}", style="cyan")

        results: List[ConversionResult] = []
        for name in adapter_names:
            target = output_path / f"{name}.ngff.zarr"
            console.log(f"Starting conversion with '{name}' → {target}", style="blue")
            result = api_convert(
                input_path,
                target,
                vendor=name,
                output_format="ngff",
            )
            console.log(f"Completed '{name}' conversion at {result.output_path}", style="green")
            results.append(result)
        return results


__all__ = ["ConversionPipeline"]
