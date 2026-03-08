"""
Deterministic Headless Builder — produces reproducible outputs from structured JSON specs.

Guarantees:
- Same input → same output (deterministic)
- Canonical JSON ordering (no random key order)
- Stable hashes for governance frozen spine
- Build receipts with full audit trail

Usage:
    builder = DeterministicBuilder()
    spec = {
        "target": "file",
        "path": "output.json",
        "schema": {...},
        "data": {...}
    }
    receipt = await builder.build(spec)
    print(receipt.output_hash)  # Same every time for same spec
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class BuildReceipt:
    """Result of a deterministic build."""
    build_id: str
    spec_hash: str  # SHA-256 of spec (frozen immutable anchor)
    output_hash: str  # SHA-256 of output
    output_path: str  # Where file was written
    duration_ms: int
    status: str  # success, validation_failed, write_failed
    error: Optional[str] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


class DeterministicBuilder:
    """Builds deterministic, auditable outputs from JSON specs."""
    
    def __init__(self, base_output_dir: Optional[str] = None):
        """
        Initialize builder.
        
        Args:
            base_output_dir: Directory for output files. If None, uses temp dir.
        """
        self.base_output_dir = base_output_dir or tempfile.gettempdir()
        Path(self.base_output_dir).mkdir(parents=True, exist_ok=True)
    
    async def build(self, spec: dict[str, Any]) -> BuildReceipt:
        """
        Build output from spec.
        
        Args:
            spec: Build specification with keys:
                - target: "file" or "data" (default: "file")
                - path: output file path (for target="file")
                - data: dict to output (for target="data")
                - schema: optional JSON schema for validation
        
        Returns:
            BuildReceipt with hashes, paths, and status
        """
        import time
        start = time.time()
        build_id = str(uuid.uuid4())
        
        try:
            # Validate spec
            spec_hash = self._hash_spec(spec)
            
            if "schema" in spec:
                validation_error = self._validate_schema(spec.get("data", {}), spec["schema"])
                if validation_error:
                    return BuildReceipt(
                        build_id=build_id,
                        spec_hash=spec_hash,
                        output_hash="",
                        output_path="",
                        duration_ms=int((time.time() - start) * 1000),
                        status="validation_failed",
                        error=validation_error,
                    )
            
            # Build output
            target = spec.get("target", "file")
            
            if target == "data":
                output_data = spec.get("data", {})
                output_hash = self._hash_data(output_data)
                return BuildReceipt(
                    build_id=build_id,
                    spec_hash=spec_hash,
                    output_hash=output_hash,
                    output_path="",
                    duration_ms=int((time.time() - start) * 1000),
                    status="success",
                )
            
            elif target == "file":
                output_path = spec.get("path", f"{self.base_output_dir}/output_{build_id}.json")
                output_data = spec.get("data", {})
                
                # Ensure deterministic JSON (sorted keys, consistent formatting)
                output_json = json.dumps(
                    output_data,
                    indent=2,
                    sort_keys=True,
                    default=str,
                    separators=(",", ": "),
                )
                
                # Write file
                try:
                    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(output_json)
                except Exception as e:
                    return BuildReceipt(
                        build_id=build_id,
                        spec_hash=spec_hash,
                        output_hash="",
                        output_path=output_path,
                        duration_ms=int((time.time() - start) * 1000),
                        status="write_failed",
                        error=f"Failed to write {output_path}: {e}",
                    )
                
                # Hash output
                output_hash = self._hash_file(output_path)
                
                return BuildReceipt(
                    build_id=build_id,
                    spec_hash=spec_hash,
                    output_hash=output_hash,
                    output_path=output_path,
                    duration_ms=int((time.time() - start) * 1000),
                    status="success",
                )
            
            else:
                return BuildReceipt(
                    build_id=build_id,
                    spec_hash=spec_hash,
                    output_hash="",
                    output_path="",
                    duration_ms=int((time.time() - start) * 1000),
                    status="validation_failed",
                    error=f"Unknown target: {target}",
                )
        
        except Exception as e:
            return BuildReceipt(
                build_id=build_id,
                spec_hash="",
                output_hash="",
                output_path="",
                duration_ms=int((time.time() - start) * 1000),
                status="validation_failed",
                error=str(e),
            )
    
    def _hash_spec(self, spec: dict[str, Any]) -> str:
        """Hash the spec deterministically (frozen anchor)."""
        spec_json = json.dumps(spec, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(spec_json.encode()).hexdigest()
    
    def _hash_data(self, data: dict[str, Any]) -> str:
        """Hash data deterministically."""
        data_json = json.dumps(data, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(data_json.encode()).hexdigest()
    
    def _hash_file(self, filepath: str) -> str:
        """Hash file contents deterministically."""
        with open(filepath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    def _validate_schema(self, data: dict[str, Any], schema: dict[str, Any]) -> Optional[str]:
        """Validate data against schema. Returns error message or None."""
        try:
            import jsonschema
            jsonschema.validate(instance=data, schema=schema)
            return None
        except ImportError:
            # jsonschema not available; skip validation
            return None
        except Exception as e:
            return f"Schema validation failed: {e}"


# Spoke flow integration: expose as a flow handler
async def deterministic_build_flow(inp: dict[str, Any]) -> dict[str, Any]:
    """Flow handler for deterministic builder."""
    builder = DeterministicBuilder()
    spec = inp.get("spec", {})
    receipt = await builder.build(spec)
    return receipt.to_dict()
