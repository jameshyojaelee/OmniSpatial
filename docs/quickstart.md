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

## 7. Use the Python API

For scripted workflows you can call the high-level API directly:

```python
from omnispatial import api

result = api.convert("/data/cosmx", "cosmx_bundle.zarr", vendor="cosmx-public")
api.validate(result.output_path, output_format=result.format)
```

Async variants (`convert_async`, `validate_async`) integrate smoothly with asyncio-based pipelines.

## Data Staging & Storage

- **Inputs:** Keep raw assay exports under a stable mount such as `/data/<vendor>/<sample>` (`/data/xenium/runs/xenium_tissue`, `/data/cosmx/runs/cosmx_panel`, etc.). The workflow templates expect these absolute paths, so avoid moving them once referenced in `params.samples` or `samples.*.input`.
- **Outputs:** By default the CLI and workflow configs write bundles to `build/` (`outdir`) and validation JSON to `build/reports` (`report_dir`). Point these parameters to a scratch volume when processing large cohorts and prune completed runs with `rm -rf build` (or your custom directory) once artifacts are handed off.
- **Shared filesystems:** Network mounts work best when presented read-only for inputs and writeable scratch for outputs. Favour staging to local SSD when the shared store is slow or heavily contended, and always mount both input and output roots inside containers (see [Run with Docker](#8-run-with-docker) and [Orchestrate Workflows in Containers](#9-orchestrate-workflows-in-containers) for bind examples).
- **Chunk sizing & compression:** The example configs default to `image_chunks: 1,512,512` and `label_chunks: 256,256`, a good balance for 2D microscopy tiles. Increase spatial chunk edges to 1024 when exporting very large mosaics, and keep the depth dimension at 1 unless working with volumetric stacks. Validation-ready NGFF bundles use `compression_level: 5`; lower the value to speed up writes on scratch volumes or raise it (6–7) when long-term storage space is a concern.

## 8. Run with Docker

An official image published to GHCR bundles the CLI, Napari plugin, and documentation assets:

```bash
docker run --rm \
  -v /data:/data \
  ghcr.io/omnispatial/omnispatial:latest \
  convert /data/cosmx --out /data/cosmx_ngff.zarr --vendor cosmx-public
```

Mount input/output volumes as required. The image also ships the workflow templates under `/opt/omnispatial/examples`.

## 9. Orchestrate Workflows in Containers

The workflow templates under `examples/workflows/` inherit the same container image. Copy `params.example.yaml` (Nextflow) or `config.example.yaml` (Snakemake), adjust sample paths, and follow the "Containerized Execution" sections in `examples/workflows/nextflow/README.md` and `examples/workflows/snakemake/README.md`. Those guides detail the `-with-docker` / `-with-singularity` flags, using `params.container` in `nextflow.config`, setting `SNAKEMAKE_CONTAINER_IMAGE`, and binding host data volumes.
