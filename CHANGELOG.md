# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Functional `ConversionPipeline` orchestration that emits per-adapter NGFF bundles and returns `ConversionResult` metadata.
- Initial end-to-end tutorial notebook and documentation restructure.
- Napari plugin enhancements, GeoJSON streaming API, and web viewer improvements.
- Validation pipeline with machine-readable reports and release automation.
- Provenance metadata across adapters, writers, and validators with configurable chunk/compression options.
- Structured logging, dry-run support, and chunk/compression CLI flags for `omnispatial convert`.
- Cached tabular IO utilities shared by adapters to avoid redundant reads.
- Adapter plugin discovery via entry points with CosMx public release and Visium HD packages.
- Programmatic `omnispatial.api` module with sync/async conversion and validation helpers.
- Nextflow and Snakemake workflow templates wired to the shared API under `examples/workflows/`.
- Container image definition (`Dockerfile`) bundling the CLI, Napari plugin, and docs for GHCR publishing.
- Dataset cache tooling (`tools/datasets/fetch_datasets.py`) with checksum tracking and GEO presets.
- Profiling harness (`tools/benchmarks/profile.py`) plus GeoJSON/Viv stress generators and budget checks (`tools/benchmarks/check_budget.py`).
- Benchmarking documentation with dashboards and badges integrated into MkDocs.

### Changed
- Consolidated CLI commands with vendor detection and output controls.
- Writers now persist OmniSpatial provenance and honour user-configurable chunk/compression settings with graceful fallbacks.
- Documentation updated with architecture details on provenance, caching, and writer configuration.
- CI/CD now builds container images for GHCR and seeds GitHub Releases directly from `CHANGELOG.md` entries.
- GeoJSON API now supports configurable request limits, cached WKT parsing, and concurrent column reads.
- NGFF writer improves chunk heuristics based on dtype size to reduce IO overhead for large imagery.

### Fixed
- Assorted adapter robustness fixes revealed during integration work.
