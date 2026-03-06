"""
Data Fabric Ingestion — raw → clean → features.

Ingests: Census, permits, parcel data. Writes to data/fabric/.
"""

from __future__ import annotations

import csv
import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("data_fabric")

FABRIC_ROOT = Path(__file__).resolve().parents[2] / "data" / "fabric"
RAW_DIR = FABRIC_ROOT / "raw"
CLEAN_DIR = FABRIC_ROOT / "clean"
FEATURES_DIR = FABRIC_ROOT / "features"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ingest_raw(
    source: str,
    path: str | Path,
    *,
    trace_id: str | None = None,
    format: str = "auto",
) -> dict[str, Any]:
    """
    Ingest raw data into data/fabric/raw/{source}/.
    Supports: CSV, JSON. Auto-detects from extension.
    """
    path = Path(path)
    if not path.exists():
        return {"ok": False, "error": "path not found", "path": str(path)}

    tid = trace_id or str(uuid.uuid4())
    raw_dir = RAW_DIR / source
    raw_dir.mkdir(parents=True, exist_ok=True)

    fmt = format
    if fmt == "auto":
        fmt = "json" if path.suffix.lower() in (".json", ".jsonl") else "csv"

    dest_name = f"{path.stem}_{tid[:8]}_{_utcnow_iso()[:10]}.{path.suffix}"
    dest = raw_dir / dest_name
    shutil.copy2(path, dest)

    meta = {
        "source": source,
        "original_path": str(path),
        "dest_path": str(dest),
        "trace_id": tid,
        "format": fmt,
        "ingested_at": _utcnow_iso(),
    }

    meta_path = raw_dir / f"{dest.stem}.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return {"ok": True, **meta}


def normalize_to_clean(
    dataset: str,
    *,
    trace_id: str | None = None,
    source_file: str | None = None,
) -> dict[str, Any]:
    """
    Normalize raw → clean. Reads from raw/{dataset}/, writes to clean/{dataset}/.
    """
    tid = trace_id or str(uuid.uuid4())
    raw_dir = RAW_DIR / dataset
    clean_dir = CLEAN_DIR / dataset
    clean_dir.mkdir(parents=True, exist_ok=True)

    if not raw_dir.exists():
        return {"ok": False, "error": "raw dir not found", "dataset": dataset}

    files = list(raw_dir.glob("*.csv")) + list(raw_dir.glob("*.json"))
    if source_file:
        files = [f for f in files if source_file in f.name]
    if not files:
        return {"ok": False, "error": "no raw files", "dataset": dataset}

    normalized = []
    errors: list[dict[str, Any]] = []
    for fp in files[:10]:
        try:
            if fp.suffix.lower() == ".csv":
                rows = []
                with open(fp, encoding="utf-8", newline="") as f:
                    for row in csv.DictReader(f):
                        rows.append({k.strip(): v for k, v in row.items()})
                out_path = clean_dir / f"{fp.stem}.json"
                out_path.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
                normalized.append(str(out_path))
            else:
                data = json.loads(fp.read_text(encoding="utf-8"))
                out_path = clean_dir / f"{fp.stem}.json"
                out_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
                normalized.append(str(out_path))
        except Exception as e:
            _LOG.warning("normalize failed %s: %s", fp.name, e)
            errors.append({"file": fp.name, "error": str(e)})

    return {
        "ok": True,
        "dataset": dataset,
        "trace_id": tid,
        "normalized_count": len(normalized),
        "paths": normalized,
        "errors": errors if errors else None,
    }


def build_features(
    dataset: str,
    *,
    trace_id: str | None = None,
    feature_keys: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build features from clean. Extracts numeric/categorical for models.
    """
    tid = trace_id or str(uuid.uuid4())
    clean_dir = CLEAN_DIR / dataset
    features_dir = FEATURES_DIR / dataset
    features_dir.mkdir(parents=True, exist_ok=True)

    if not clean_dir.exists():
        return {"ok": False, "error": "clean dir not found", "dataset": dataset}

    files = list(clean_dir.glob("*.json"))
    if not files:
        return {"ok": False, "error": "no clean files", "dataset": dataset}

    all_features = []
    errors: list[dict[str, Any]] = []
    for fp in files[:10]:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            rows = data if isinstance(data, list) else [data]
            for row in rows:
                if isinstance(row, dict):
                    features = {k: v for k, v in row.items() if feature_keys is None or k in feature_keys}
                    all_features.append(features)
        except Exception as e:
            _LOG.warning("build_features failed %s: %s", fp.name, e)
            errors.append({"file": fp.name, "error": str(e)})

    out_path = features_dir / f"features_{tid[:8]}.json"
    out_path.write_text(json.dumps(all_features[:1000], indent=2, default=str), encoding="utf-8")

    return {
        "ok": True,
        "dataset": dataset,
        "trace_id": tid,
        "feature_count": len(all_features),
        "path": str(out_path),
        "errors": errors if errors else None,
    }
