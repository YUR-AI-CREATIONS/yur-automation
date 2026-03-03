from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests


@dataclass(frozen=True)
class ProcoreOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    company_id: str
    env: str  # prod | sandbox | monthly
    login_base_url: str
    api_base_url: str

    @staticmethod
    def from_env() -> "ProcoreOAuthConfig":
        env = (os.getenv("PROCORE_ENV") or "prod").strip().lower()
        client_id = (os.getenv("PROCORE_CLIENT_ID") or "").strip()
        client_secret = (os.getenv("PROCORE_CLIENT_SECRET") or "").strip()
        redirect_uri = (os.getenv("PROCORE_REDIRECT_URI") or "").strip()
        company_id = (os.getenv("PROCORE_COMPANY_ID") or "").strip()

        if env == "sandbox":
            login_base_url = os.getenv("PROCORE_LOGIN_BASE_URL", "https://login-sandbox.procore.com").strip()
            api_base_url = os.getenv("PROCORE_API_BASE_URL", "https://sandbox.procore.com").strip()
        elif env == "monthly":
            login_base_url = os.getenv("PROCORE_LOGIN_BASE_URL", "https://login-sandbox-monthly.procore.com").strip()
            api_base_url = os.getenv("PROCORE_API_BASE_URL", "https://api-monthly.procore.com").strip()
        else:
            env = "prod"
            login_base_url = os.getenv("PROCORE_LOGIN_BASE_URL", "https://login.procore.com").strip()
            api_base_url = os.getenv("PROCORE_API_BASE_URL", "https://api.procore.com").strip()

        return ProcoreOAuthConfig(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            company_id=company_id,
            env=env,
            login_base_url=login_base_url,
            api_base_url=api_base_url,
        )

    @property
    def authorize_url(self) -> str:
        return f"{self.login_base_url.rstrip('/')}/oauth/authorize"

    @property
    def token_url(self) -> str:
        return f"{self.login_base_url.rstrip('/')}/oauth/token"


def _keyring() -> Any:
    try:
        import keyring  # type: ignore

        return keyring
    except Exception:
        return None


class ProcoreTokenStore:
    """
    Refresh token storage:
    - env var `PROCORE_REFRESH_TOKEN` (works everywhere)
    - optional OS keychain via `keyring` (recommended)
    """

    def __init__(self, service_name: str = "FranklinOpsHub.Procore", username: str = "default"):
        self._service_name = service_name
        self._username = username

    def get_refresh_token(self) -> str:
        env = (os.getenv("PROCORE_REFRESH_TOKEN") or "").strip()
        if env:
            return env
        kr = _keyring()
        if kr is None:
            return ""
        try:
            return (kr.get_password(self._service_name, self._username) or "").strip()
        except Exception:
            return ""

    def set_refresh_token(self, refresh_token: str) -> bool:
        kr = _keyring()
        if kr is None:
            return False
        try:
            kr.set_password(self._service_name, self._username, refresh_token)
            return True
        except Exception:
            return False


@dataclass
class ProcoreTokens:
    access_token: str
    refresh_token: str
    token_type: str
    expires_at_epoch: float

    @property
    def is_expired(self) -> bool:
        return time.time() >= (self.expires_at_epoch - 30)


class ProcoreOAuth:
    def __init__(self, config: ProcoreOAuthConfig, token_store: Optional[ProcoreTokenStore] = None):
        self._config = config
        self._store = token_store or ProcoreTokenStore()

    def build_state(self) -> str:
        return secrets.token_urlsafe(16)

    def authorization_url(self, *, state: str) -> str:
        if not self._config.client_id or not self._config.redirect_uri:
            raise ValueError("Missing PROCORE_CLIENT_ID / PROCORE_REDIRECT_URI")
        return (
            f"{self._config.authorize_url}"
            f"?response_type=code&client_id={self._config.client_id}"
            f"&redirect_uri={requests.utils.quote(self._config.redirect_uri, safe='')}"
            f"&state={state}"
        )

    def exchange_code(self, *, code: str) -> ProcoreTokens:
        if not (self._config.client_id and self._config.client_secret and self._config.redirect_uri):
            raise ValueError("Missing PROCORE_CLIENT_ID / PROCORE_CLIENT_SECRET / PROCORE_REDIRECT_URI")

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret,
            "redirect_uri": self._config.redirect_uri,
        }
        resp = requests.post(self._config.token_url, data=data, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        access = (payload.get("access_token") or "").strip()
        refresh = (payload.get("refresh_token") or "").strip()
        token_type = (payload.get("token_type") or "bearer").strip()
        expires_in = float(payload.get("expires_in") or 5400)

        if not access or not refresh:
            raise ValueError("Token response missing access_token/refresh_token")

        self._store.set_refresh_token(refresh)
        return ProcoreTokens(
            access_token=access,
            refresh_token=refresh,
            token_type=token_type,
            expires_at_epoch=time.time() + expires_in,
        )

    def refresh_access_token(self, *, refresh_token: Optional[str] = None) -> ProcoreTokens:
        rt = (refresh_token or "").strip() or self._store.get_refresh_token()
        if not rt:
            raise ValueError("Missing refresh token (set PROCORE_REFRESH_TOKEN or install keyring)")
        if not (self._config.client_id and self._config.client_secret):
            raise ValueError("Missing PROCORE_CLIENT_ID / PROCORE_CLIENT_SECRET")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": rt,
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret,
        }
        resp = requests.post(self._config.token_url, data=data, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        access = (payload.get("access_token") or "").strip()
        refresh = (payload.get("refresh_token") or rt).strip()
        token_type = (payload.get("token_type") or "bearer").strip()
        expires_in = float(payload.get("expires_in") or 5400)
        if not access:
            raise ValueError("Token refresh response missing access_token")

        self._store.set_refresh_token(refresh)
        return ProcoreTokens(
            access_token=access,
            refresh_token=refresh,
            token_type=token_type,
            expires_at_epoch=time.time() + expires_in,
        )


class ProcoreClient:
    def __init__(self, *, api_base_url: str, access_token: str, company_id: str):
        self._api_base_url = api_base_url.rstrip("/")
        self._access_token = access_token
        self._company_id = company_id

    def _headers(self) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self._access_token}"}
        if self._company_id:
            h["Procore-Company-Id"] = self._company_id
        return h

    def get(self, path: str, *, params: Optional[dict[str, Any]] = None) -> Any:
        url = f"{self._api_base_url}{path}"
        resp = requests.get(url, headers=self._headers(), params=params or {}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def list_company_projects(self) -> Any:
        if not self._company_id:
            raise ValueError("Missing PROCORE_COMPANY_ID")
        return self.get(f"/rest/v1.0/companies/{self._company_id}/projects")

