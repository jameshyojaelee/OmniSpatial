# Nextflow Template

This DSL2 template converts a set of input datasets with OmniSpatial and optionally validates the generated bundles. Configure `params.samples` in `nextflow.config` or via `-params-file` with a map of sample IDs to input directories:

```groovy
params.samples = [
  "sampleA": "/data/cosmx/sampleA",
  "sampleB": "/data/visium/outs"
]
```

To get started quickly, copy `params.example.yaml` to a working directory, adjust the sample paths, and run with:

```bash
cp params.example.yaml params.yaml
nextflow run main.nf -params-file params.yaml
```

Run the pipeline directly from the template with your own params file:

```bash
nextflow run main.nf -params-file params.example.yaml
```

Key parameters:

- `format`: `ngff` (default) or `spatialdata`.
- `vendor`: optional adapter name (auto-detection when omitted).
- `image_chunks` / `label_chunks`: chunk specifications for NGFF output.
- `validate`: set `true` to run the validation module after conversion.
- `container`: container image to run the processes (e.g., `ghcr.io/omnispatial/omnispatial:latest`); this value is passed through from `params.container` into `nextflow.config`.
- Validation reports: see `docs/validation-reports.md` for aggregation options and CI recipes.

The modules reuse `../scripts/run_omnispatial.py`, which wraps the `omnispatial.api` module for deterministic workflow-friendly execution.

## Containerized Execution

Set `params.container` to `ghcr.io/omnispatial/omnispatial:latest` (as shown in `params.example.yaml`) and Nextflow forwards the value to `nextflow.config`, enabling both Docker and Singularity launches.

```bash
nextflow run main.nf \
  -params-file params.example.yaml \
  -with-docker \
  -DSL2
```

When running with Singularity/Apptainer:

```bash
nextflow run main.nf \
  -params-file params.example.yaml \
  -with-singularity \
  -DSL2 \
  -config ./singularity.config
```

Add `singularity.enabled = true` (or `singularity.autoMounts = true`) inside an override config when targeting Apptainer, and ensure host data directories (for example `/data`) are available via Nextflow’s volume handling or explicit `process.containerOptions` mount flags.
