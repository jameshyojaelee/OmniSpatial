"""Metadata models for describing spatial experiments."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class SampleMetadata(BaseModel):
    """Metadata describing a spatial assay acquisition."""

    sample_id: str = Field(..., description="Unique identifier for the sample.")
    organism: str = Field(..., description="Organism name or ontology label.")
    assay: str = Field(..., description="Spatial omics assay name.")
    contributors: List[str] = Field(default_factory=list, description="List of contributors.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp.")
    reference_links: Dict[str, HttpUrl] = Field(default_factory=dict, description="Reference resources.")
    notes: Optional[str] = Field(default=None, description="Additional freeform notes.")

    model_config = {
        "validate_assignment": True,
        "json_schema_extra": {
            "examples": [
                {
                    "sample_id": "SAMPLE-123",
                    "organism": "Homo sapiens",
                    "assay": "Visium",
                    "contributors": ["Jane Doe"],
                    "reference_links": {"protocol": "https://example.org/protocol"},
                }
            ]
        },
    }


__all__ = ["SampleMetadata"]
