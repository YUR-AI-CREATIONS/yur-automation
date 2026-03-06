"""
Enterprise multi-tenancy: tenant context and isolation.

Tenant ID is resolved from (in order):
  1. X-Tenant-ID request header
  2. X-Tenant-Id (alternate casing)
  3. Default tenant from env FRANKLINOPS_DEFAULT_TENANT or "default"

All tenant-scoped data (OpsDB, DocIndex, Audit) is filtered by tenant_id.
"""

from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Optional

# Context variable for request-scoped tenant ID (set by middleware)
_tenant_id_ctx: ContextVar[str] = ContextVar("tenant_id", default="default")


def get_tenant_id() -> str:
    """Return the current request's tenant ID (from context or default)."""
    try:
        return _tenant_id_ctx.get()
    except LookupError:
        return os.getenv("FRANKLINOPS_DEFAULT_TENANT", "default")


def set_tenant_id(tenant_id: str) -> None:
    """Set the tenant ID for the current context (used by middleware)."""
    _tenant_id_ctx.set(tenant_id or "default")


def resolve_tenant_from_request(header_value: Optional[str]) -> str:
    """Resolve tenant ID from request header or env default."""
    if header_value and header_value.strip():
        return header_value.strip()
    return os.getenv("FRANKLINOPS_DEFAULT_TENANT", "default")
