# Architecture

OmniSpatial organises spatial omics tooling into several layers:

## Adapters

Vendor-specific adapters convert raw exports into the canonical `SpatialDataset`. Each adapter derives from `SpatialAdapter` and implements three methods:

- `detect(path)`: quickly inspect a directory to determine compatibility.
- `read(path)`: parse files into images, label polygons, and observation tables.
- `metadata()`: describe supported modalities for discovery.

Adapters register themselves via the `register_adapter` decorator in `omnispatial.adapters.registry`. The registry powers CLI detection and enables discovery of third-party plugins.

## Canonical Model

`omnispatial.core.model` defines typed Pydantic models representing:

- `ImageLayer`: multiscale imagery with pixel size metadata and transforms to the global frame.
- `LabelLayer`: segmentation masks or vector geometries linked to the same coordinate system.
- `TableLayer`: AnnData-backed measurements mapping observations to coordinates or polygons.
- `SpatialDataset`: an aggregate that tracks coordinate frames and ensures transforms are invertible.

Adapters produce a `SpatialDataset`, which becomes the single source of truth for downstream tooling.

## Writers

`omnispatial.ngff.writer` provides `write_ngff` and `write_spatialdata`:

- `write_ngff` streams imagery, rasterised labels, and AnnData tables into an OME-NGFF Zarr store, emitting NGFF metadata and coordinate transforms.
- `write_spatialdata` materialises a SpatialData object that links image, labels, and tables and flushes to Zarr for interoperability with the Python ecosystem.

Both writers respect the transforms defined in the canonical model so that viewers can locate pixels, labels, and observations in a shared frame.

## Validator

`omnispatial.validate.validator` performs structural checks over NGFF and SpatialData bundles and emits machine-readable reports. Checks include:

- Presence of required NGFF metadata and multiscale descriptors.
- Monotonic scale factors and valid units for spatial axes.
- Table observation indices aligned with label masks or polygon counts.
- Bounding box consistency between labels and imagery.

The CLI exposes these checks through `omnispatial validate`, returning exit codes suitable for CI pipelines.

## Viewer and Plugin

The Next.js web viewer consumes NGFF pyramids directly in the browser using Viv and overlays observation geometry fetched via a lightweight GeoJSON API. The napari plugin registers a reader and dock widget so that desktop inspections stay in sync with the canonical model.
