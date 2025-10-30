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

Use the per-sample vendor fields when mixing assays, and adjust chunk sizes or compression settings when processing larger volumes or tuning IO performance.

The workflow shells out to `../scripts/run_omnispatial.py`, ensuring consistency with the programmatic API exposed via `omnispatial.api`.
