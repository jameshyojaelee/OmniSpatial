# Snakemake Template

This Snakemake workflow converts each configured dataset with OmniSpatial and optionally validates the output bundles. Edit `config.yaml` to specify input paths, adapter overrides, and output preferences.

Duplicate `config.example.yaml` into your working location, update the sample paths (and optional per-sample vendor overrides), and launch Snakemake with:

```bash
snakemake --directory /path/to/work --configfile config.example.yaml -j 4
```

Execute the workflow with your own configuration file:

```bash
snakemake --directory /path/to/work -j 4
```

Configuration highlights:

- `format`: `ngff` (default) or `spatialdata`.
- `vendor`: global default adapter; per-sample overrides can be set under `samples.*.vendor`.
- `image_chunks` / `label_chunks`: optional NGFF chunk sizing.
- `validate`: when `true`, emits JSON reports under `report_dir` using the `omnispatial.api.validate` helper.
- `output_dir` / `report_dir`: control where converted bundles and validation reports land; mirror these paths with the example config when adapting chunking or compression levels.
- Validation reports: consult `docs/validation-reports.md` for aggregation strategies and CI integration pointers.

Use the per-sample vendor fields when mixing assays, and adjust chunk sizes or compression settings when processing larger volumes or tuning IO performance.

The workflow shells out to `../scripts/run_omnispatial.py`, ensuring consistency with the programmatic API exposed via `omnispatial.api`.

## Containerized Execution

Snakemake can execute the rules inside the published container without a local Poetry environment. Export the desired image (or rely on Snakemake’s `SNAKEMAKE_CONTAINER_IMAGE` helper) and launch with Singularity/Apptainer:

```bash
SNAKEMAKE_CONTAINER_IMAGE=ghcr.io/omnispatial/omnispatial:latest \
snakemake \
  --directory /path/to/work \
  --configfile config.example.yaml \
  --use-singularity \
  --singularity-args "-B /data"
```

When using Conda environments in place of containers, keep the same configuration file and enable `--use-conda`:

```bash
snakemake \
  --directory /path/to/work \
  --configfile config.example.yaml \
  --use-conda
```

Ensure host directories referenced in the config (for example `/data/xenium/...`) are available inside the container bind, and adjust the `--singularity-args` mount list if your storage paths differ. Consult `config.example.yaml` for the expected layout when preparing additional mounts.
