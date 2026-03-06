"""
Reality Feedback Engine — prediction vs actual, error metrics, model improvement.

Stores predictions and outcomes. Computes error. Future: auto-adjust model params.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FEEDBACK_DIR = Path(__file__).resolve().parents[2] / "data" / "fabric" / "runs" / "feedback"
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_prediction(
    prediction_id: str,
    model: str,
    predicted: dict[str, Any],
    *,
    trace_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> str:
    """
    Record a prediction. Returns prediction_id.
    Stored in data/fabric/runs/feedback/{prediction_id}.json
    """
    tid = trace_id or str(uuid.uuid4())
    rec = {
        "prediction_id": prediction_id,
        "trace_id": tid,
        "model": model,
        "predicted": predicted,
        "recorded_at": _utcnow_iso(),
        "context": context or {},
        "outcome": None,
    }
    path = FEEDBACK_DIR / f"{prediction_id}.json"
    path.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    return prediction_id


def record_outcome(
    prediction_id: str,
    actual: dict[str, Any],
    *,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """
    Record actual outcome for a prediction. Computes error metrics.
    """
    path = FEEDBACK_DIR / f"{prediction_id}.json"
    if not path.exists():
        return {"ok": False, "error": "prediction not found", "prediction_id": prediction_id}

    rec = json.loads(path.read_text(encoding="utf-8"))
    rec["outcome"] = actual
    rec["outcome_recorded_at"] = recorded_at or _utcnow_iso()

    # Compute error metrics (keys that exist in both)
    pred = rec.get("predicted", {})
    errors = {}
    for k in pred:
        if k in actual and isinstance(pred[k], (int, float)) and isinstance(actual[k], (int, float)):
            errors[k] = {
                "predicted": pred[k],
                "actual": actual[k],
                "error": actual[k] - pred[k],
                "pct_error": (actual[k] - pred[k]) / pred[k] * 100 if pred[k] else 0,
            }
    rec["error_metrics"] = errors

    path.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    return {"ok": True, "prediction_id": prediction_id, "error_metrics": errors}


def get_prediction_errors(model: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Get recent predictions with outcomes and errors."""
    out = []
    for p in sorted(FEEDBACK_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        if limit <= 0:
            break
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            if model and rec.get("model") != model:
                continue
            if rec.get("outcome") and rec.get("error_metrics"):
                out.append(rec)
                limit -= 1
        except Exception:
            continue
    return out
