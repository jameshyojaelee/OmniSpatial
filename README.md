# OmniSpatial

OmniSpatial is a cross-vendor toolkit for converting, validating, and exploring spatial omics assets. It produces interoperable [OME-NGFF](https://ngff.openmicroscopy.org/latest/) Zarr stores and SpatialData bundles, and ships with both a Python-based workflow CLI and a browser viewer built with Next.js.

## Quickstart

### Python toolkit

```bash
# Install Poetry if needed, see https://python-poetry.org/docs/
poetry install
poetry run omnispatial --help
poetry run omnispatial convert path/to/input.ome.tif output_workspace/
```

### Web viewer

```bash
cd viewer
pnpm install
pnpm dev
```

Then open http://localhost:3000/ and paste an NGFF Zarr URL to explore the dataset.

## Architecture

```
                 +-----------------------+
                 |    Spatial Sources    |
                 |  (vendors, assays)    |
                 +-----------+-----------+
                             |
                             v
+----------------+   +---------------+   +-----------------+
| CLI & Converters|-->| NGFF Writers  |-->| SpatialData I/O |
+--------+-------+   +-------+-------+   +--------+--------+
         |                   |                    |
         |                   v                    v
         |         +-----------------+   +-----------------+
         |         | Data Validators |   | Napari Plugin   |
         |         +-----------------+   +-----------------+
         |                   |
         v                   v
+----------------------+   +-----------------------------+
| Rich Console Reports |   | Web Viewer (@vivjs + MUI)   |
+----------------------+   +-----------------------------+
```

## Project Layout

- `omnispatial/` – Python package, CLI, converters, validation rules, napari plugin, documentation.
- `viewer/` – Next.js web application for remote exploration of NGFF Zarr datasets.
- `docs/` – MkDocs documentation skeleton with quickstart and API notes.

## Canonical Model

The Python toolkit maps diverse vendor exports into a canonical `SpatialDataset` model. It tracks `ImageLayer`, `LabelLayer`, and `TableLayer` objects bound to named coordinate frames with explicit 3×3 affine transforms, unit annotations, and global frame alignment. Geometries are exchanged as WKT via Shapely while tabular measurements reference AnnData-style observations and features. This shared representation powers converters, validators, and adapters.

## Adapters

- `xenium` – exercises the canonical model with a synthetic export comprising `cells.csv`, `matrix.csv`, and a tiny TIFF in `images/`. The adapter builds polygons, AnnData counts, and an intensity image to verify the pipeline end to end.

See `CITATION.cff` for citation guidance and `LICENSE` for the MIT license.
