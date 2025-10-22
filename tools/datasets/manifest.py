"""Dataset manifest describing large public spatial omics resources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class DatasetFile:
    """Metadata about a downloadable artefact."""

    url: str
    filename: str
    checksum: Optional[str] = None
    checksum_type: str = "sha256"
    size: Optional[int] = None
    extract: bool = False
    target_subdir: str = ""
    description: Optional[str] = None


@dataclass(frozen=True)
class DatasetConfig:
    """Configuration for a benchmark dataset."""

    name: str
    provider: str
    description: str
    files: List[DatasetFile] = field(default_factory=list)
    citation: Optional[str] = None
    estimated_cells: Optional[int] = None
    modalities: List[str] = field(default_factory=list)


DATASET_MANIFEST: Dict[str, DatasetConfig] = {
    "visium_ffpe_breast": DatasetConfig(
        name="visium_ffpe_breast",
        provider="NCBI GEO (GSE189725)",
        description="10x Genomics Visium FFPE breast tumour section.",
        citation="10x Genomics Visium FFPE Breast Cancer, GEO GSE189725.",
        estimated_cells=45000,
        modalities=["transcriptomics", "histology"],
        files=[
            DatasetFile(
                url="https://ftp.ncbi.nlm.nih.gov/geo/series/GSE189nnn/GSE189725/suppl/GSE189725_RAW.tar",
                filename="GSE189725_RAW.tar",
                extract=True,
                description="Archive containing FFPE spaceranger outputs.",
            ),
        ],
    ),
    "slideseqv2_mouse_hippocampus": DatasetConfig(
        name="slideseqv2_mouse_hippocampus",
        provider="NCBI GEO (GSE139307)",
        description="Slide-seqV2 mouse hippocampus release dataset.",
        citation="Stickels et al., Slide-seqV2 (Science 2021), GEO GSE139307.",
        estimated_cells=500000,
        modalities=["transcriptomics"],
        files=[
            DatasetFile(
                url="https://ftp.ncbi.nlm.nih.gov/geo/series/GSE139nnn/GSE139307/suppl/GSE139307_RAW.tar",
                filename="GSE139307_RAW.tar",
                extract=True,
                description="Release tarball with bead-by-gene matrices and metadata.",
            ),
        ],
    ),
    "merfish_mouse_hypothalamus": DatasetConfig(
        name="merfish_mouse_hypothalamus",
        provider="NCBI GEO (GSE139256)",
        description="MERFISH large-format mouse hypothalamus dataset.",
        citation="Moffitt et al., Molecular, spatial, and functional single-cell profiling (Science 2018), GEO GSE139256.",
        estimated_cells=1000000,
        modalities=["transcriptomics", "imaging"],
        files=[
            DatasetFile(
                url="https://ftp.ncbi.nlm.nih.gov/geo/series/GSE139nnn/GSE139256/suppl/GSE139256_RAW.tar",
                filename="GSE139256_RAW.tar",
                extract=True,
                description="Archive with stitched MERFISH tables and segmentations.",
            ),
        ],
    ),
}
