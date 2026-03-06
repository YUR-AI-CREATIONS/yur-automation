"""
Enterprise RBAC and auth: role-based access control, SSO stubs.

Roles:
  - admin: full access, tenant management, user provisioning
  - ops: operational access (approvals, tasks, ingest, finance, sales)
  - viewer: read-only (audit, config, reports)
  - service: API/service account (limited to specific scopes)

SSO: SAML/OIDC stubs for enterprise integration (implement via authlib or python-saml).
"""

from __future__ import annotations

import os
from contextvars import ContextVar
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional

# Context variable for request-scoped user/role (set by auth middleware)
_user_ctx: ContextVar[dict[str, Any]] = ContextVar("auth_user", default={})


class Role(str, Enum):
    ADMIN = "admin"
    OPS = "ops"
    VIEWER = "viewer"
    SERVICE = "service"


# Route -> required roles (any of)
ROUTE_ROLES: dict[str, set[Role]] = {
    "/api/config": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/autonomy": {Role.ADMIN, Role.OPS},
    "/api/approvals": {Role.ADMIN, Role.OPS},
    "/api/audit": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/tasks": {Role.ADMIN, Role.OPS},
    "/api/ingest": {Role.ADMIN, Role.OPS},
    "/api/doc_index": {Role.ADMIN, Role.OPS},
    "/api/ops_chat": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/sales": {Role.ADMIN, Role.OPS},
    "/api/finance": {Role.ADMIN, Role.OPS},
    "/api/grokstmate": {Role.ADMIN, Role.OPS},
    "/api/fleet": {Role.ADMIN, Role.OPS},
    "/api/bidzone": {Role.ADMIN, Role.OPS},
    "/api/project_controls": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/integrations": {Role.ADMIN, Role.OPS},
    "/api/pilot": {Role.ADMIN, Role.OPS},
    "/api/metrics": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/tire": {Role.ADMIN, Role.OPS},
    "/api/onboarding": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/concierge": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/ollama": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/download": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/support": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/admin": {Role.ADMIN},
    "/api/tenants": {Role.ADMIN},
    "/api/governance": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/kernel": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/development": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/flows": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/geo-economic": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/economic-fabric": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/data-fabric": {Role.ADMIN, Role.OPS},
    "/api/reality-feedback": {Role.ADMIN, Role.OPS, Role.VIEWER},
    "/api/forensic": {Role.ADMIN, Role.OPS, Role.VIEWER},
}


def _path_prefix_match(path: str) -> Optional[set[Role]]:
    """Return required roles for path (prefix match)."""
    path = path.rstrip("/") or "/"
    for prefix, roles in sorted(ROUTE_ROLES.items(), key=lambda x: -len(x[0])):
        if path.startswith(prefix) or path == prefix:
            return roles
    return None


def get_current_user() -> dict[str, Any]:
    """Return current request user from context (role, tenant_id, etc.)."""
    try:
        return _user_ctx.get()
    except LookupError:
        return {"role": Role.OPS, "tenant_id": "default", "user_id": "anonymous"}


def set_current_user(user: dict[str, Any]) -> None:
    """Set current user in context (used by auth middleware)."""
    _user_ctx.set(user)


def require_role(*roles: Role) -> Callable:
    """Decorator to require one of the given roles."""

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = get_current_user()
            user_role = user.get("role")
            if isinstance(user_role, str):
                user_role = Role(user_role) if user_role in [r.value for r in Role] else Role.OPS
            if user_role not in roles and user_role != Role.ADMIN:
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            return f(*args, **kwargs)

        return wrapper

    return decorator


def validate_api_key(api_key: Optional[str], allowed_keys: list[str]) -> bool:
    """
    Validate API key against allowed list.
    Stub: when FRANKLINOPS_API_KEYS is set, Bearer token must match one.
    Returns True if valid or when no keys configured (permissive).
    """
    if not allowed_keys:
        return True
    if not api_key or not api_key.strip():
        return False
    return api_key.strip() in allowed_keys


def resolve_user_from_request(
    *,
    api_key: Optional[str] = None,
    x_role: Optional[str] = None,
    tenant_id: str = "default",
    allowed_api_keys: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Resolve user from request headers.
    In production: validate API key, JWT, or SAML/OIDC assertion.
    """
    role = Role.OPS
    if x_role and x_role.lower() in ("admin", "ops", "viewer", "service"):
        role = Role(x_role.lower())
    # API key could map to service role; validate when keys configured
    if api_key and api_key.startswith("sk_service_"):
        role = Role.SERVICE
    if allowed_api_keys and not validate_api_key(api_key, allowed_api_keys):
        return {"role": role, "tenant_id": tenant_id, "user_id": "anonymous", "_api_key_invalid": True}
    return {"role": role, "tenant_id": tenant_id, "user_id": "anonymous"}
