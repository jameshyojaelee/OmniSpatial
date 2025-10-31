# Benchmarking Suite

OmniSpatial ships a performance harness that exercises conversion, validation, and arbitrary shell workloads while collecting CPU, memory, GPU, and I/O metrics. Results are written as JSON artefacts that downstream dashboards can aggregate.

## Dataset cache

Large reference datasets are downloaded with `tools/datasets/fetch_datasets.py`:

```bash
# List available datasets
python tools/datasets/fetch_datasets.py --list

# Download everything into ./datasets (or set OMNISPATIAL_DATASETS)
python tools/datasets/fetch_datasets.py all

# Export manifest
python tools/datasets/fetch_datasets.py --manifest benchmark-datasets.json
```

Each archive is checksummed after download and optional extraction markers prevent redundant work. The cache location defaults to `./datasets` but honours the `OMNISPATIAL_DATASETS` environment variable when set.

## Profiling harness

Use `tools/benchmarks/profile.py` to wrap high-level workflows:

```bash
# Convert a dataset while capturing metrics
python tools/benchmarks/profile.py \
  --label visium_ffpe \
  --report benchmark-artifacts/visium_ffpe_convert.json \
  convert datasets/visium_ffpe_breast data/visium_ffpe_breast_ngff.zarr \
  --vendor visium_hd --format ngff

# Validate an OME-NGFF bundle
python tools/benchmarks/profile.py \
  --label visium_validate \
  validate data/visium_ffpe_breast_ngff.zarr --report-dir benchmark-artifacts

# Profile arbitrary viewer warm-up commands (e.g. Viv CLI)
python tools/benchmarks/profile.py \
  --label viv_load --report benchmark-artifacts/viv.json \
  command "pnpm --dir viewer run load-bundle data/visium_ffpe_breast_ngff.zarr"
```

Summary statistics include peak RSS (GB), average/peak process CPU utilisation, cumulative read/write volumes, and optional GPU utilisation (via `pynvml` when available). Raw samples are embedded in the JSON payload to enable richer post-processing.

Set `--hardware` to annotate the run (e.g. `A100x1`, `M2-Max`) and adjust `--interval` to control sampling cadence. Profiling metadata plus raw metrics enable dashboards/notebooks to trend performance across releases.

## GeoJSON API stress test

The viewer exposes a GeoJSON endpoint that can be exercised offline using the synthetic generator in `viewer/scripts/geojson-stress.ts`:

```bash
pnpm --dir viewer install
pnpm --dir viewer run stress:geojson --features=1000000 --report ../benchmark-artifacts/geojson-stress.json
```

The script generates one million synthetic observation records, transforms them via the API helper, and records execution time and memory usage.

## Viv tile loader stress test

Simulate Viv tile retrieval by sampling random chunks from an OME-NGFF bundle:

```bash
python tools/benchmarks/viv_stress.py datasets/visium_ffpe_breast/visium_image.zarr --samples 256 --report benchmark-artifacts/viv_tiles.json
```

The stress test reads random chunks, reports aggregate throughput (MB/s), average latency, and chunk metadata so regressions in image IO are caught early.

## CI performance budgets

`ci.yaml` includes a `performance` job that executes the GeoJSON and Viv stress tests on GitHub-hosted runners. Budgets are currently configured to ensure 200k feature synthesis completes within 12 seconds and Viv tile throughput stays above 5 MB/s. Failing budgets block releases, providing early warning when regressions are introduced.

For functional QA of converted bundles, combine performance metrics with the validation summaries documented in [Validation Reports](validation-reports.md). The same JSON payloads can feed scorecards, dashboards, or gating logic alongside benchmark outputs.
