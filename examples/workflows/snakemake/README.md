# Snakemake Template

This Snakemake workflow converts each configured dataset with OmniSpatial and optionally validates the output bundles. Edit `config.yaml` to specify input paths, adapter overrides, and output preferences.

Execute the workflow:

```bash
snakemake --directory /path/to/work -j 4
```

Configuration highlights:

- `format`: `ngff` (default) or `spatialdata`.
- `vendor`: global default adapter; per-sample overrides can be set under `samples.*.vendor`.
- `image_chunks` / `label_chunks`: optional NGFF chunk sizing.
- `validate`: when `true`, emits JSON reports under `report_dir` using the `omnispatial.api.validate` helper.

The workflow shells out to `../scripts/run_omnispatial.py`, ensuring consistency with the programmatic API exposed via `omnispatial.api`.
