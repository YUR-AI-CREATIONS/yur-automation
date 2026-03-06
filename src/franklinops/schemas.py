"""
Franklin OS API Schemas — Pydantic models for all endpoints.

Zero-gap validation: every API body is validated before processing.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# --- Data Fabric ---
class DataFabricIngestIn(BaseModel):
    source: str = Field(..., min_length=1, max_length=128, description="Dataset source key (e.g. census, permits, parcel)")
    path: str = Field(..., min_length=1, description="Absolute path to file (CSV or JSON)")
    trace_id: Optional[str] = Field(default=None, max_length=64)


class DataFabricNormalizeIn(BaseModel):
    dataset: str = Field(..., min_length=1, max_length=128)
    trace_id: Optional[str] = Field(default=None, max_length=64)
    source_file: Optional[str] = Field(default=None, max_length=256)


class DataFabricFeaturesIn(BaseModel):
    dataset: str = Field(..., min_length=1, max_length=128)
    trace_id: Optional[str] = Field(default=None, max_length=64)
    feature_keys: Optional[list[str]] = Field(default=None, max_length=100)


# --- Economic Fabric ---
class EconomicIndexIn(BaseModel):
    region_id: str = Field(..., min_length=1, max_length=64)
    use_connectors: bool = Field(default=True)
    use_fabric: bool = Field(default=True)


class EconomicRefreshIn(BaseModel):
    regions: list[str] = Field(..., min_length=1, max_length=100)
    use_connectors: bool = Field(default=True)


# --- Geo-Economic ---
class RegionScoreIn(BaseModel):
    region_id: str = Field(default="default", max_length=64)
    migration_score: float = Field(default=0.7, ge=0, le=1)
    permit_growth: float = Field(default=0.6, ge=0, le=1)
    infrastructure_investment: float = Field(default=0.5, ge=0, le=1)
    employment_expansion: float = Field(default=0.6, ge=0, le=1)
    land_price_trend: float = Field(default=0.5, ge=0, le=1)


class GeoEconomicCorridorsIn(BaseModel):
    regions: list[RegionScoreIn] = Field(default_factory=lambda: [RegionScoreIn()], max_length=50)
    trace_id: Optional[str] = Field(default=None, max_length=64)
    tenant_id: str = Field(default="default", max_length=64)
    threshold: float = Field(default=0.6, ge=0, le=1)


# --- Reality Feedback ---
class RealityFeedbackPredictionIn(BaseModel):
    prediction_id: Optional[str] = Field(default=None, max_length=64)
    model: str = Field(default="default", max_length=64)
    predicted: dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = Field(default=None, max_length=64)
    context: Optional[dict[str, Any]] = Field(default=None)


class RealityFeedbackOutcomeIn(BaseModel):
    prediction_id: str = Field(..., min_length=1, max_length=64)
    actual: dict[str, Any] = Field(default_factory=dict)


# --- Development Pipeline / Land Deal ---
class ParcelIn(BaseModel):
    parcel_id: Optional[str] = Field(default="unknown", max_length=64)
    acres: float = Field(default=10.0, gt=0, le=1_000_000)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)
    address: Optional[str] = Field(default=None, max_length=512)
    region_id: Optional[str] = Field(default=None, max_length=64)
    base_profit: float = Field(default=12_000_000, ge=0)
    extra: Optional[dict[str, Any]] = Field(default=None)

    def to_pipeline_dict(self) -> dict[str, Any]:
        d = self.model_dump(exclude_none=True, exclude={"extra"})
        if self.extra:
            d.update(self.extra)
        return {k: v for k, v in d.items() if v is not None}


class DevelopmentPipelineIn(BaseModel):
    parcel: Optional[ParcelIn] = Field(default=None)
    parcel_id: Optional[str] = Field(default=None, max_length=64)
    acres: Optional[float] = Field(default=None, gt=0, le=1_000_000)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)
    base_profit: Optional[float] = Field(default=None, ge=0)
    trace_id: Optional[str] = Field(default=None, max_length=64)
    tenant_id: str = Field(default="default", max_length=64)

    def to_pipeline_input(self) -> dict[str, Any]:
        """Build parcel dict for kernel.invoke (development_pipeline_flow)."""
        if self.parcel:
            p = self.parcel.to_pipeline_dict()
        else:
            p = {
                "parcel_id": self.parcel_id or "unknown",
                "acres": self.acres or 10.0,
                "lat": self.lat,
                "lon": self.lon,
                "base_profit": self.base_profit or 12_000_000,
            }
        p["tenant_id"] = self.tenant_id
        if self.trace_id:
            p["trace_id"] = self.trace_id
        return p


# --- Flow Invoke (generic) ---
class FlowInvokeIn(BaseModel):
    """Generic flow input. Flow-specific validation in handler."""
    trace_id: Optional[str] = Field(default=None, max_length=64)
    tenant_id: Optional[str] = Field(default=None, max_length=64)
    payload: Optional[dict[str, Any]] = Field(default=None)


# --- Project Controls Logs ---
class ProjectControlLogCreateIn(BaseModel):
    source: str = Field(default="pc_document", max_length=64)
    log_type: str = Field(default="entry", max_length=64)
    entry_data: dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field(default="api", max_length=64)


class ProjectControlLogUpdateIn(BaseModel):
    entry_data: dict[str, Any] = Field(default_factory=dict)


# --- GROKSTMATE / BID-ZONE Estimate ---
class ProjectSpecIn(BaseModel):
    """Project specification for cost estimates."""
    project_spec: Optional[dict[str, Any]] = Field(default=None, description="Nested project spec when provided")
    project_name: Optional[str] = Field(default=None, max_length=256)
    address: Optional[str] = Field(default=None, max_length=512)
    square_feet: Optional[float] = Field(default=None, gt=0)
    scope: Optional[str] = Field(default=None, max_length=512)
    extra: Optional[dict[str, Any]] = Field(default=None)

    model_config = {"extra": "allow"}

    def to_spec_dict(self) -> dict[str, Any]:
        """Extract project spec dict for bridge/estimate calls."""
        if self.project_spec:
            return self.project_spec
        return self.model_dump(exclude_none=True, exclude={"project_spec"})


class GrokstmateCreateProjectIn(BaseModel):
    """Create project plan request."""
    project_id: str = Field(default="proj_new", max_length=64)
    project_name: str = Field(default="New Project", max_length=256)
    project_spec: Optional[dict[str, Any]] = Field(default=None)

    model_config = {"extra": "allow"}
