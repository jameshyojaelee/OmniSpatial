# API Reference

## `omnispatial.core`

- `SampleMetadata` – Pydantic model describing assays.
- `ConversionPipeline` – High-level orchestration entry point.

  Typical usage returns a list of `ConversionResult` objects with the emitted bundle paths:

  ```python
  from pathlib import Path
  from omnispatial.core import ConversionPipeline, SampleMetadata

  pipeline = ConversionPipeline()
  metadata = SampleMetadata(sample_id="S1", organism="human", assay="transcriptomics")
  results = pipeline.convert(Path("data/xenium"), Path("outputs"), metadata)
  for result in results:
      print(result.adapter, result.output_path)
  # yields outputs/xenium.ngff.zarr and similar per matched adapter
  ```

## `omnispatial.api`

- `convert` / `convert_async` – Invoke adapter-driven conversions programmatically, returning a `ConversionResult` with the emitted bundle path.
- `validate` / `validate_async` – Validate NGFF or SpatialData bundles and receive a structured `ValidationReport`.
- `available_adapter_names` – Enumerate built-in and plugin-supplied adapters discovered via entry points.
- `AdapterNotFoundError`, `ConversionResult` – Convenience types surfaced by the high-level API.

## `omnispatial.validate`

- `ValidationReport` – Pydantic report surfaced by the CLI and validation API.
- `validate_bundle` – High-level dispatcher for NGFF and SpatialData targets.
- `validate_store` – Legacy helper for schema-based checks.

## `omnispatial.ngff`

- `write_ngff` – Persist a `SpatialDataset` as OME-NGFF.
- `write_spatialdata` – Persist a `SpatialDataset` as a SpatialData Zarr bundle.

## `omnispatial.cli`

- `app` – Typer application hosting the CLI commands.

## `omnispatial.napari_plugin`

- `omnispatial_reader` – Napari reader that returns image, label, and feature layers.
- `OmniSpatialDock` – Dock widget for filtering and colouring observation layers.

More modules will appear as the project evolves.
