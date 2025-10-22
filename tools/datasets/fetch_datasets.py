#!/usr/bin/env python3
"""Download and cache large benchmarking datasets for OmniSpatial."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tarfile
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if __package__ is None or __package__ == "":
    import sys

    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.append(str(PROJECT_ROOT))
    from tools.datasets.manifest import DATASET_MANIFEST, DatasetConfig, DatasetFile
else:  # pragma: no cover
    from .manifest import DATASET_MANIFEST, DatasetConfig, DatasetFile

USER_AGENT = "OmniSpatialBenchmark/0.1"
DEFAULT_DATA_DIR = Path("datasets")
INDEX_FILE_NAME = "index.json"


def load_index(root: Path) -> Dict[str, Dict[str, str]]:
    """Read the cached checksum index if available."""
    index_path = root / INDEX_FILE_NAME
    if not index_path.exists():
        return {}
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_index(root: Path, index: Dict[str, Dict[str, str]]) -> None:
    """Persist the checksum index."""
    (root / INDEX_FILE_NAME).write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")


def compute_sha256(path: Path) -> str:
    """Compute the SHA256 checksum for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, destination: Path) -> None:
    """Download a URL to the specified destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req) as response, destination.open("wb") as handle:
            total = int(response.headers.get("Content-Length", "0")) or None
            downloaded = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                if total:
                    downloaded += len(chunk)
                    percent = (downloaded / total) * 100
                    print(f"\r  -> {destination.name}: {downloaded / 1e6:.1f} / {total / 1e6:.1f} MB ({percent:5.1f}%)", end="")
            if total:
                print()
    except HTTPError as exc:  # pragma: no cover - network failure
        raise RuntimeError(f"Failed to download {url}: HTTP {exc.code}") from exc
    except URLError as exc:  # pragma: no cover - network failure
        raise RuntimeError(f"Failed to download {url}: {exc.reason}") from exc


def extract_file(archive: Path, target_dir: Path) -> None:
    """Extract an archive into the target directory if not already present."""
    target_dir.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        mode = "r"
        with zipfile.ZipFile(archive, mode) as zip_handle:
            zip_handle.extractall(target_dir)
    elif (
        archive.suffix in {".tar", ".tgz", ".gz", ".bz2"}
        or len(archive.suffixes) >= 2
        and archive.suffixes[-2:] in [
            [".tar", ".gz"],
            [".tar", ".bz2"],
            [".tar", ".xz"],
        ]
    ):
        with tarfile.open(archive) as tar_handle:
            tar_handle.extractall(target_dir)
    else:
        raise ValueError(f"Unsupported archive format for extraction: {archive}")


def ensure_dataset(
    dataset: DatasetConfig,
    *,
    root: Path,
    index: Dict[str, Dict[str, str]],
    force: bool = False,
    skip_extract: bool = False,
) -> Tuple[int, int]:
    dataset_dir = root / dataset.name
    dataset_dir.mkdir(parents=True, exist_ok=True)
    dataset_index = index.setdefault(dataset.name, {})

    downloaded_files = 0
    extracted_files = 0

    for file in dataset.files:
        destination = dataset_dir / file.filename
        needs_download = force or not destination.exists()

        if not needs_download:
            recorded = dataset_index.get(file.filename)
            current = compute_sha256(destination)
            if recorded and recorded != current:
                print(f"Checksum mismatch for {destination}, re-downloading.")
                needs_download = True
            elif file.checksum and file.checksum.lower() != current:
                print(f"Checksum mismatch against manifest for {destination}, re-downloading.")
                needs_download = True

        if needs_download:
            print(f"Downloading {file.url}")
            download_file(file.url, destination)
            downloaded_files += 1

        checksum = compute_sha256(destination)
        dataset_index[file.filename] = checksum
        if file.checksum and file.checksum.lower() != checksum:
            raise RuntimeError(
                f"Checksum verification failed for {file.filename}: expected {file.checksum}, observed {checksum}"
            )

        if file.extract and not skip_extract:
            target_subdir = file.target_subdir or destination.stem
            extraction_dir = dataset_dir / target_subdir
            marker = extraction_dir / ".extracted"
            if force or not marker.exists():
                print(f"Extracting {file.filename} -> {extraction_dir}")
                extract_file(destination, extraction_dir)
                marker.touch()
                extracted_files += 1

    return downloaded_files, extracted_files


def list_datasets(datasets: Iterable[DatasetConfig]) -> None:
    """Pretty print available dataset metadata."""
    for dataset in datasets:
        print(f"{dataset.name}")
        print(f"  Provider : {dataset.provider}")
        print(f"  Summary  : {dataset.description}")
        if dataset.citation:
            print(f"  Citation : {dataset.citation}")
        if dataset.estimated_cells:
            print(f"  Cells    : ~{dataset.estimated_cells:,}")
        if dataset.modalities:
            print(f"  Modalities: {', '.join(dataset.modalities)}")
        for file in dataset.files:
            print(f"    - {file.filename} <- {file.url}")
        print()


def serialize_manifest(output: Path) -> None:
    """Write the manifest metadata to disk for reference."""
    payload = {
        name: {
            "provider": cfg.provider,
            "description": cfg.description,
            "citation": cfg.citation,
            "estimated_cells": cfg.estimated_cells,
            "modalities": cfg.modalities,
            "files": [asdict(file) for file in cfg.files],
        }
        for name, cfg in DATASET_MANIFEST.items()
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "datasets",
        nargs="*",
        default=["all"],
        help="Datasets to download (default: all available).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Root directory for cached datasets (default: ./datasets).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download archives even if they already exist locally.",
    )
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Do not extract archives after downloading.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available datasets and exit.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Write the dataset manifest to this JSON file and exit.",
    )

    args = parser.parse_args()
    env_root = os.environ.get("OMNISPATIAL_DATASETS")
    if env_root and args.data_dir == DEFAULT_DATA_DIR:
        args.data_dir = Path(env_root)
    selected = list(DATASET_MANIFEST.values())

    if args.list:
        list_datasets(selected)
        return

    if args.manifest:
        serialize_manifest(args.manifest)
        print(f"Wrote manifest to {args.manifest}")
        if args.datasets == ["all"]:
            return

    if args.datasets != ["all"]:
        missing = [name for name in args.datasets if name not in DATASET_MANIFEST]
        if missing:
            known = ", ".join(DATASET_MANIFEST)
            raise SystemExit(f"Unknown datasets: {', '.join(missing)}. Known: {known}")
        selected = [DATASET_MANIFEST[name] for name in args.datasets]

    args.data_dir.mkdir(parents=True, exist_ok=True)
    index = load_index(args.data_dir)

    total_downloaded = 0
    total_extracted = 0
    for dataset in selected:
        print(f"==> {dataset.name}")
        downloaded, extracted = ensure_dataset(
            dataset,
            root=args.data_dir,
            index=index,
            force=args.force,
            skip_extract=args.skip_extract,
        )
        total_downloaded += downloaded
        total_extracted += extracted

    save_index(args.data_dir, index)
    print(f"Completed. Downloaded {total_downloaded} archive(s); extracted {total_extracted} archive(s).")


if __name__ == "__main__":
    main()
