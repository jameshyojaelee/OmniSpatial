# Examples

## End-to-End Notebook

The [examples/omnispatial_end_to_end.ipynb](https://github.com/omnispatial/omnispatial/blob/main/examples/omnispatial_end_to_end.ipynb) notebook walks through:

1. Generating a synthetic Xenium-style dataset.
2. Converting it to OME-NGFF and SpatialData with the CLI.
3. Validating the outputs and inspecting the machine-readable report.
4. Launching napari and the web viewer for interactive exploration.

Launch the notebook using Poetry to ensure the project environment is active:

```bash
cd omnispatial
poetry run jupyter lab ../examples/omnispatial_end_to_end.ipynb
```

Each cell is annotated with comments explaining the workflow and can be adapted for automated testing or demonstrations.

## Workflow Templates

Reusable Nextflow and Snakemake templates live under `examples/workflows/` and call the shared `omnispatial.api` module via `scripts/run_omnispatial.py`.

- `examples/workflows/nextflow/` contains a DSL2 pipeline with modular conversion and validation processes. Configure `params.samples` to point at datasets and optionally set `params.vendor`, `params.validate`, and chunking parameters.
- `examples/workflows/snakemake/` ships a `Snakefile` and `config.yaml` that can be customised per sample. Enable validation by setting `validate: true` in the config.

Both templates work against local checkouts or the published container image, making it easy to embed OmniSpatial in larger orchestration stacks.
