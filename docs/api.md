# API Reference

## `omnispatial.core`

- `SampleMetadata` – Pydantic model describing assays.
- `ConversionPipeline` – High-level orchestration entry point.

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
