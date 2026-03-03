from __future__ import annotations

import base64
import os
import time
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Optional

import httpx


@dataclass(frozen=True)
class OutboundEmailConfig:
    provider: str  # manual | gmail | sendgrid | console
    from_email: str
    from_name: str
    recipient_override_email: str

    gmail_client_id: str
    gmail_client_secret: str
    gmail_refresh_token: str

    sendgrid_api_key: str
    sendgrid_api_base_url: str = "https://api.sendgrid.com/v3"

    @classmethod
    def from_env(cls) -> "OutboundEmailConfig":
        provider = (os.getenv("FRANKLINOPS_EMAIL_PROVIDER") or os.getenv("EMAIL_PROVIDER") or "manual").strip().lower()

        from_email = (os.getenv("FRANKLINOPS_FROM_EMAIL") or os.getenv("FROM_EMAIL") or "").strip()
        from_name = (os.getenv("FRANKLINOPS_FROM_NAME") or os.getenv("FROM_NAME") or "FranklinOps").strip()
        recipient_override = (os.getenv("FRANKLINOPS_RECIPIENT_OVERRIDE_EMAIL") or os.getenv("RECIPIENT_EMAIL") or "").strip()

        return cls(
            provider=provider or "manual",
            from_email=from_email,
            from_name=from_name or "FranklinOps",
            recipient_override_email=recipient_override,
            gmail_client_id=(os.getenv("GMAIL_CLIENT_ID") or "").strip(),
            gmail_client_secret=(os.getenv("GMAIL_CLIENT_SECRET") or "").strip(),
            gmail_refresh_token=(os.getenv("GMAIL_REFRESH_TOKEN") or "").strip(),
            sendgrid_api_key=(os.getenv("SENDGRID_API_KEY") or "").strip(),
        )


@dataclass(frozen=True)
class OutboundEmailResult:
    ok: bool
    provider: str
    provider_message_id: str
    to_email: str
    subject: str
    error: str = ""
    meta: Optional[dict[str, Any]] = None


class OutboundEmailSender:
    """
    Minimal email delivery adapter (reused from the legacy superagents emailer patterns).

    Notes:
    - Supports Gmail API (OAuth refresh token) and SendGrid HTTP API.
    - Supports recipient override for safe testing.
    - "manual"/"console" providers never actually send.
    """

    def __init__(self, cfg: Optional[OutboundEmailConfig] = None):
        self._cfg = cfg or OutboundEmailConfig.from_env()
        self._gmail_access_token: Optional[str] = None
        self._gmail_access_token_expiry_epoch: float = 0.0

    @property
    def provider(self) -> str:
        return (self._cfg.provider or "manual").strip().lower()

    def send_email(
        self,
        *,
        to_email: str,
        to_name: str = "",
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        timeout_sec: float = 30.0,
    ) -> OutboundEmailResult:
        provider = self.provider

        actual_to = (to_email or "").strip()
        if not actual_to:
            return OutboundEmailResult(ok=False, provider=provider, provider_message_id="", to_email=actual_to, subject=subject, error="to_email is empty")

        override = (self._cfg.recipient_override_email or "").strip()
        original_to = actual_to
        if override:
            actual_to = override

        use_from_email = (from_email or self._cfg.from_email or "").strip()
        use_from_name = (from_name or self._cfg.from_name or "").strip()

        if provider in {"manual", "disabled"}:
            return OutboundEmailResult(
                ok=False,
                provider=provider,
                provider_message_id="",
                to_email=actual_to,
                subject=subject,
                error="email provider is manual/disabled (not sending)",
                meta={"recipient_override": override, "original_to_email": original_to} if override else None,
            )

        if provider in {"console", "dry_run"}:
            return OutboundEmailResult(
                ok=True,
                provider=provider,
                provider_message_id=f"console_{uuid.uuid4().hex[:12]}",
                to_email=actual_to,
                subject=subject,
                meta={"recipient_override": override, "original_to_email": original_to} if override else None,
            )

        if provider == "gmail":
            return self._send_via_gmail(
                to_email=actual_to,
                to_name=to_name,
                subject=subject,
                body=body,
                from_email=use_from_email,
                from_name=use_from_name,
                timeout_sec=timeout_sec,
                original_to_email=original_to,
                recipient_override=override,
            )

        if provider == "sendgrid":
            return self._send_via_sendgrid(
                to_email=actual_to,
                to_name=to_name,
                subject=subject,
                body=body,
                from_email=use_from_email,
                from_name=use_from_name,
                timeout_sec=timeout_sec,
                original_to_email=original_to,
                recipient_override=override,
            )

        return OutboundEmailResult(ok=False, provider=provider, provider_message_id="", to_email=actual_to, subject=subject, error=f"unknown provider: {provider}")

    def _get_gmail_access_token(self, *, timeout_sec: float) -> Optional[str]:
        now = time.time()
        if self._gmail_access_token and now < (self._gmail_access_token_expiry_epoch - 60):
            return self._gmail_access_token

        if not self._cfg.gmail_client_id or not self._cfg.gmail_client_secret or not self._cfg.gmail_refresh_token:
            return None

        try:
            with httpx.Client(timeout=timeout_sec) as client:
                resp = client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": self._cfg.gmail_client_id,
                        "client_secret": self._cfg.gmail_client_secret,
                        "refresh_token": self._cfg.gmail_refresh_token,
                        "grant_type": "refresh_token",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            if resp.status_code != 200:
                return None

            data = resp.json() or {}
            token = (data.get("access_token") or "").strip()
            expires_in = float(data.get("expires_in") or 0.0)
            if not token:
                return None

            self._gmail_access_token = token
            self._gmail_access_token_expiry_epoch = now + max(expires_in, 0.0)
            return token
        except Exception:
            return None

    def _send_via_gmail(
        self,
        *,
        to_email: str,
        to_name: str,
        subject: str,
        body: str,
        from_email: str,
        from_name: str,
        timeout_sec: float,
        original_to_email: str,
        recipient_override: str,
    ) -> OutboundEmailResult:
        token = self._get_gmail_access_token(timeout_sec=timeout_sec)
        if not token:
            return OutboundEmailResult(
                ok=False,
                provider="gmail",
                provider_message_id="",
                to_email=to_email,
                subject=subject,
                error="Gmail credentials not configured (need GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN)",
            )

        msg = EmailMessage()
        msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email
        if from_email:
            msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
        elif from_name:
            msg["From"] = from_name
        msg["Subject"] = subject
        msg.set_content(body)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8").rstrip("=")

        try:
            with httpx.Client(timeout=timeout_sec) as client:
                resp = client.post(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                    json={"raw": raw},
                    headers={"Authorization": f"Bearer {token}"},
                )
            if resp.status_code not in (200, 202):
                return OutboundEmailResult(
                    ok=False,
                    provider="gmail",
                    provider_message_id="",
                    to_email=to_email,
                    subject=subject,
                    error=f"Gmail send failed: {resp.status_code}",
                    meta={"details": (resp.text or "")[:500]},
                )

            data = resp.json() or {}
            mid = (data.get("id") or "").strip() or f"gmail_{uuid.uuid4().hex[:12]}"
            meta: dict[str, Any] = {}
            if recipient_override:
                meta["recipient_override"] = recipient_override
                meta["original_to_email"] = original_to_email
            return OutboundEmailResult(ok=True, provider="gmail", provider_message_id=mid, to_email=to_email, subject=subject, meta=meta or None)
        except Exception as e:
            return OutboundEmailResult(ok=False, provider="gmail", provider_message_id="", to_email=to_email, subject=subject, error=str(e))

    def _send_via_sendgrid(
        self,
        *,
        to_email: str,
        to_name: str,
        subject: str,
        body: str,
        from_email: str,
        from_name: str,
        timeout_sec: float,
        original_to_email: str,
        recipient_override: str,
    ) -> OutboundEmailResult:
        if not self._cfg.sendgrid_api_key:
            return OutboundEmailResult(ok=False, provider="sendgrid", provider_message_id="", to_email=to_email, subject=subject, error="SENDGRID_API_KEY not set")
        if not from_email:
            return OutboundEmailResult(ok=False, provider="sendgrid", provider_message_id="", to_email=to_email, subject=subject, error="from_email not set (set FRANKLINOPS_FROM_EMAIL or FROM_EMAIL)")

        payload: dict[str, Any] = {
            "personalizations": [{"to": [{"email": to_email, "name": to_name} if to_name else {"email": to_email}], "subject": subject}],
            "from": {"email": from_email, "name": from_name} if from_name else {"email": from_email},
            "content": [{"type": "text/plain", "value": body}],
        }

        try:
            with httpx.Client(timeout=timeout_sec) as client:
                resp = client.post(
                    f"{self._cfg.sendgrid_api_base_url.rstrip('/')}/mail/send",
                    headers={"Authorization": f"Bearer {self._cfg.sendgrid_api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
            if resp.status_code not in (200, 202):
                return OutboundEmailResult(
                    ok=False,
                    provider="sendgrid",
                    provider_message_id="",
                    to_email=to_email,
                    subject=subject,
                    error=f"SendGrid send failed: {resp.status_code}",
                    meta={"details": (resp.text or "")[:500]},
                )

            mid = f"sendgrid_{uuid.uuid4().hex[:12]}"
            meta: dict[str, Any] = {}
            if recipient_override:
                meta["recipient_override"] = recipient_override
                meta["original_to_email"] = original_to_email
            return OutboundEmailResult(ok=True, provider="sendgrid", provider_message_id=mid, to_email=to_email, subject=subject, meta=meta or None)
        except Exception as e:
            return OutboundEmailResult(ok=False, provider="sendgrid", provider_message_id="", to_email=to_email, subject=subject, error=str(e))

