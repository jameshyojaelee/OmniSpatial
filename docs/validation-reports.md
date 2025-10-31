# Validation Reports

Both workflow templates emit machine-readable validation summaries that can be aggregated for quality gates or dashboards.

## Where Reports Are Written

- **Nextflow** publishes `<sample>.validation.json` to `params.report_dir` when `params.validate` is true.
- **Snakemake** writes `<sample>.validation.json` under `report_dir` whenever `validate: true` in `config.yaml` (or the example config).

Each JSON document mirrors the structure returned by `omnispatial.api.validate`, including `ok`, `issues`, `summary`, and `metrics` fields.

## Aggregating Results

Pick whichever tooling fits your environment:

- **Python snippet**

  ```python
  import json
  from pathlib import Path

  reports = []
  for path in Path("build/reports").glob("*.validation.json"):
      data = json.loads(path.read_text())
      reports.append({"sample": path.stem.replace(".validation", ""), "ok": data["ok"], "issues": data["issues"]})

  failures = [r for r in reports if not r["ok"]]
  if failures:
      for report in failures:
          print(f"[FAIL] {report['sample']}: {len(report['issues'])} issues")
      raise SystemExit(1)
  print(f"All {len(reports)} bundles passed validation.")
  ```

- **jq / shell**

  ```bash
  jq -r '.summary.target + "," + (.ok|tostring)' build/reports/*.validation.json
  ```

- **Budget checks**

  Use `tools/benchmarks/check_budget.py` to guard metrics (e.g., pyramid size or processing time) by pointing it at the JSON payloads.

  ```bash
  python tools/benchmarks/check_budget.py build/reports/sample.validation.json --metric summary:pyramid_levels --max 6
  ```

## Surfacing in CI

1. Add a post-run step that collects the reports into the CI artifacts directory (e.g., `actions/upload-artifact` on GitHub Actions).
2. Run the Python snippet (or `jq`) to fail the pipeline on validation errors.
3. Optionally emit Markdown summaries or badges using the aggregated results.

## Dashboards

For richer visualisations, point your reporting stack at the same JSON files. See [`docs/benchmark-dashboard.md`](benchmark-dashboard.md) for examples on combining validation metrics with performance data.
