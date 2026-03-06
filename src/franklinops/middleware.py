"""
Enterprise middleware: tenant context, RBAC user context, API versioning headers.
"""

from __future__ import annotations

import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

try:
    from ..core.tenant import set_tenant_id, resolve_tenant_from_request
except ImportError:
    def set_tenant_id(tid: str) -> None:
        pass
    def resolve_tenant_from_request(h: str | None) -> str:
        return "default"

try:
    from ..core.auth import (
        set_current_user,
        resolve_user_from_request,
        _path_prefix_match,
        Role,
    )
except ImportError:
    def set_current_user(u: dict) -> None:
        pass
    def resolve_user_from_request(*, api_key: str | None = None, x_role: str | None = None, tenant_id: str = "default", allowed_api_keys: list | None = None) -> dict:
        return {"role": "ops", "tenant_id": tenant_id, "user_id": "anonymous"}
    def _path_prefix_match(path: str):
        return None
    Role = type("Role", (), {"ADMIN": "admin", "OPS": "ops", "VIEWER": "viewer", "SERVICE": "service"})


def _get_allowed_api_keys() -> list[str]:
    from .settings import FranklinOpsSettings
    return FranklinOpsSettings().api_keys


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Sets tenant context from X-Tenant-ID header and user/role from X-Role for all /api/* and /ui/* requests.
    Health and static routes bypass. RBAC enforced when FRANKLINOPS_RBAC_ENABLED=true.
    """

    SKIP_PATHS = ("/healthz", "/docs", "/redoc", "/openapi.json", "/favicon.ico", "/static")

    async def dispatch(self, request: Request, call_next: callable) -> Response:
        path = request.scope.get("path", "")
        if any(path.startswith(p) for p in self.SKIP_PATHS):
            return await call_next(request)

        header_value = request.headers.get("X-Tenant-ID") or request.headers.get("X-Tenant-Id")
        tenant_id = resolve_tenant_from_request(header_value)
        set_tenant_id(tenant_id)

        # Resolve user/role for RBAC
        api_key = request.headers.get("Authorization", "").replace("Bearer ", "").strip() or request.headers.get("X-API-Key")
        x_role = request.headers.get("X-Role")
        allowed_keys = _get_allowed_api_keys()
        user = resolve_user_from_request(api_key=api_key, x_role=x_role, tenant_id=tenant_id, allowed_api_keys=allowed_keys or None)
        set_current_user(user)

        # API key validation: when FRANKLINOPS_API_KEYS set, reject invalid
        if user.get("_api_key_invalid"):
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

        # API versioning: /api/v1/* -> /api/* (rewrite for backward compat)
        if path.startswith("/api/v1/"):
            request.scope["path"] = "/api/" + path[len("/api/v1/"):]
        elif path == "/api/v1":
            request.scope["path"] = "/api"

        # RBAC: when enabled, enforce role on /api/* routes
        rbac_enabled = os.getenv("FRANKLINOPS_RBAC_ENABLED", "false").lower() == "true"
        if rbac_enabled and path.startswith("/api"):
            check_path = request.scope.get("path", path)
            required = _path_prefix_match(check_path)
            if required is not None:
                user_role = user.get("role")
                if isinstance(user_role, str):
                    try:
                        user_role = Role(user_role)
                    except ValueError:
                        user_role = Role.OPS
                if user_role not in required and user_role != Role.ADMIN:
                    return JSONResponse(status_code=403, content={"detail": "Insufficient permissions"})

        response = await call_next(request)
        response.headers["X-Tenant-ID"] = tenant_id
        response.headers["X-API-Version"] = "v1"
        response.headers["X-API-Deprecation"] = "Use /api/v1/ for versioned API; /api/ remains supported"
        return response
