"""
Data Fabric — raw → clean → features pipeline.

Ingests: Census, permits, parcel data. Writes to data/fabric/.
"""

from pathlib import Path

from .ingest import ingest_raw, normalize_to_clean, build_features

FABRIC_ROOT = Path(__file__).resolve().parents[2] / "data" / "fabric"
RAW_DIR = FABRIC_ROOT / "raw"
CLEAN_DIR = FABRIC_ROOT / "clean"
FEATURES_DIR = FABRIC_ROOT / "features"
RUNS_DIR = FABRIC_ROOT / "runs"
EVIDENCE_DIR = FABRIC_ROOT / "evidence"

__all__ = ["ingest_raw", "normalize_to_clean", "build_features", "RAW_DIR", "CLEAN_DIR", "FEATURES_DIR"]
