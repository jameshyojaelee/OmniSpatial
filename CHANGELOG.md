# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Initial end-to-end tutorial notebook and documentation restructure.
- Napari plugin enhancements, GeoJSON streaming API, and web viewer improvements.
- Validation pipeline with machine-readable reports and release automation.
- Provenance metadata across adapters, writers, and validators with configurable chunk/compression options.
- Structured logging, dry-run support, and chunk/compression CLI flags for `omnispatial convert`.
- Cached tabular IO utilities shared by adapters to avoid redundant reads.

### Changed
- Consolidated CLI commands with vendor detection and output controls.
- Writers now persist OmniSpatial provenance and honour user-configurable chunk/compression settings with graceful fallbacks.
- Documentation updated with architecture details on provenance, caching, and writer configuration.

### Fixed
- Assorted adapter robustness fixes revealed during integration work.
