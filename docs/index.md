# OmniSpatial Overview

OmniSpatial is a mono-repository that streamlines spatial omics interoperability. It provides:

- A canonical data model that normalises images, labels, and observations from vendor exports.
- Adapter plugins for common platforms (Xenium, CosMx, MERFISH) with a registry for new sources.
- CLIs to convert datasets into OME-NGFF and SpatialData bundles, validate outputs, and launch viewers.
- A Next.js web viewer and a napari plugin for lightweight inspection.
- Validation, documentation, and release tooling to keep deployments reproducible.

Use the navigation on the left to walk through the quickstart, architecture, and developer guide. The `examples/` directory contains a runnable notebook that demonstrates the full workflow from synthetic data generation to viewer inspection.
