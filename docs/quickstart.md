# CLI Quickstart

This quickstart assumes you have installed Poetry and Node.js (with `pnpm`). All commands are executed from the repository root unless noted.

## 1. Install dependencies

```bash
cd omnispatial
poetry install --with dev
cd ..
cd viewer
pnpm install
cd ..
```

## 2. Generate a synthetic dataset

The repository ships with adapter fixtures and an example notebook. The `examples/omnispatial_end_to_end.ipynb` notebook (see the Examples section) builds a dataset inline using the same routines as the integration tests. Run the notebook or craft the CSV/TIFF inputs manually following the adapter descriptions.

## 3. Convert to NGFF and SpatialData

```bash
cd omnispatial
poetry run omnispatial convert ../examples/artifacts/xenium_synth --out ../examples/artifacts/xenium_ngff.zarr --format ngff --vendor xenium
poetry run omnispatial convert ../examples/artifacts/xenium_synth --out ../examples/artifacts/xenium_sdata.zarr --format spatialdata --vendor xenium
```

## 4. Validate the output

```bash
poetry run omnispatial validate ../examples/artifacts/xenium_ngff.zarr --format ngff --json ../examples/artifacts/ngff_report.json
cat ../examples/artifacts/ngff_report.json
```

## 5. Inspect in napari

```bash
cd omnispatial
poetry run napari ../examples/artifacts/xenium_ngff.zarr
```

Use the "OmniSpatial Inspector" dock widget to filter or colour the annotations.

## 6. Explore in the web viewer

Serve the NGFF bundle locally:

```bash
cd examples/artifacts
python -m http.server 8000
```

Then start the viewer:

```bash
cd viewer
pnpm dev
```

Open http://localhost:3000 and paste `http://localhost:8000/xenium_ngff.zarr` to stream the dataset with overlays.

The [example notebook](../examples/omnispatial_end_to_end.ipynb) stitches all steps together programmatically and is ideal for reproducible demos or testing.
