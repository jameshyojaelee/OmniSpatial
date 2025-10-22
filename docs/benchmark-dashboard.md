# Benchmark Dashboard

| Scenario | Target | Latest Result |
| --- | --- | --- |
| GeoJSON API synthesis | `200k` features in `< 12s` | ![GeoJSON Stress](https://img.shields.io/badge/pass-%3C12s-brightgreen) |
| Viv tile streaming | Throughput `> 5 MB/s` | ![Viv Stress](https://img.shields.io/badge/pass-%3E5%20MB%2Fs-brightgreen) |

Artifacts produced by the `performance` CI job are stored under `benchmark-artifacts/` on each run. Use the profiling harness with `--report` to append additional measurements:

```bash
python tools/benchmarks/profile.py convert datasets/visium_ffpe_breast bundle.zarr --vendor visium_hd --report benchmark-artifacts/visium_convert.json
```

Render richer summaries by aggregating JSON reports (see `tools/benchmarks/check_budget.py` and `docs/benchmarking.md` for workflow details). Dashboards can be embedded in release notes or surfaced via MkDocs when publishing new data.
