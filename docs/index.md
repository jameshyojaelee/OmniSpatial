# OmniSpatial Overview

OmniSpatial is a mono-repository that streamlines spatial omics interoperability. It provides:

- A canonical data model that normalises images, labels, and observations from vendor exports.
- Adapter plugins for common platforms (Xenium, CosMx, MERFISH) with a registry and entry-point system for optional packages (e.g., CosMx public release, Visium HD).
- CLIs to convert datasets into OME-NGFF and SpatialData bundles, validate outputs, and launch viewers.
- A Python API (`omnispatial.api`) for embedding conversions and validation in automation frameworks.
- A Next.js web viewer and a napari plugin for lightweight inspection.
- A published Docker image bundling the CLI, docs, and Napari plugin for reproducible deployments.
- Validation, documentation, and release tooling to keep deployments reproducible.

Use the navigation on the left to walk through the quickstart, architecture, and developer guide. The `examples/` directory contains a runnable notebook that demonstrates the full workflow from synthetic data generation to viewer inspection.
