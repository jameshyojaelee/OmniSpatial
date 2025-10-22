# Nextflow Template

This DSL2 template converts a set of input datasets with OmniSpatial and optionally validates the generated bundles. Configure `params.samples` in `nextflow.config` or via `-params-file` with a map of sample IDs to input directories:

```groovy
params.samples = [
  "sampleA": "/data/cosmx/sampleA",
  "sampleB": "/data/visium/outs"
]
```

Run the pipeline:

```bash
nextflow run main.nf -params-file params.yaml
```

Key parameters:

- `format`: `ngff` (default) or `spatialdata`.
- `vendor`: optional adapter name (auto-detection when omitted).
- `image_chunks` / `label_chunks`: chunk specifications for NGFF output.
- `validate`: set `true` to run the validation module after conversion.
- `container`: container image to run the processes (e.g., `ghcr.io/omnispatial/omnispatial:latest`).

The modules reuse `../scripts/run_omnispatial.py`, which wraps the `omnispatial.api` module for deterministic workflow-friendly execution.
