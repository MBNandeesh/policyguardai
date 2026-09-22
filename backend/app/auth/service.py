"""Officer authentication: demo-grade login for the compliance officer console.

Provides:
- File-backed officer accounts (seeded with a default officer on first use)
- HMAC-SHA256 signed session tokens (not JWT, no external dependency)
- Token verification + expiry, and last-logged-in tracking

This is deliberately simple and honest: it protects the demo UI from casual
use and stamps every officer decision with a real officer identity for the
hash-chained audit trail. It is not a production SSO.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel

from app.config import is_production, settings

STORAGE_ROOT = os.path.join(settings.storage_path, "auth")
TOKEN_TTL_HOURS = 12

# Default demo officer, seeded on first run. The demo password is only used
# when POLICYGUARD_DEMO_PASSWORD is not configured, and ONLY in non-production
# environments. Production deployments must set both variables explicitly.
DEFAULT_OFFICER_ID = "officer-001"
DEFAULT_OFFICER_NAME = "Compliance Officer"
_DEVELOPMENT_FALLBACK_PASSWORD = "officer123"
_DEVELOPMENT_FALLBACK_SECRET = "policyguard-demo-signing-key"


def _resolve_demo_password() -> str:
    """Demo password: env-configurable, dev fallback only, never in production."""
    configured = os.getenv("POLICYGUARD_DEMO_PASSWORD")
    if configured:
        return configured
    if is_production():
        raise RuntimeError(
            "POLICYGUARD_DEMO_PASSWORD must be set in production deployments."
        )
    return _DEVELOPMENT_FALLBACK_PASSWORD


def _signing_key() -> str:
    """Token signing key: POLICYGUARD_AUTH_SECRET is required in production."""
    configured = os.getenv("POLICYGUARD_AUTH_SECRET")
    if configured:
        return configured
    if is_production():
        raise RuntimeError(
            "POLICYGUARD_AUTH_SECRET must be set in production deployments."
        )
    return _DEVELOPMENT_FALLBACK_SECRET


class OfficerAccount(BaseModel):
    officer_id: str
    name: str
    role: str = "COMPLIANCE_OFFICER"
    password_hash: str
    created_at: str
    last_login: Optional[str] = None


class SessionToken(BaseModel):
    token: str
    officer_id: str
    name: str
    role: str
    issued_at: str
    expires_at: str


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()


def _officers_path() -> str:
    return os.path.join(STORAGE_ROOT, "officers.json")


def _load_officers() -> Dict[str, Dict[str, Any]]:
    path = _officers_path()
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_officers(officers: Dict[str, Dict[str, Any]]) -> None:
    os.makedirs(STORAGE_ROOT, exist_ok=True)
    with open(_officers_path(), "w", encoding="utf-8") as handle:
        json.dump(officers, handle, ensure_ascii=False, indent=2)


def ensure_default_officer() -> None:
    officers = _load_officers()
    if DEFAULT_OFFICER_ID not in officers:
        salt = secrets.token_hex(16)
        officers[DEFAULT_OFFICER_ID] = {
            "officer_id": DEFAULT_OFFICER_ID,
            "name": DEFAULT_OFFICER_NAME,
            "role": "COMPLIANCE_OFFICER",
            "salt": salt,
            "password_hash": _hash_password(_resolve_demo_password(), salt),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": None,
        }
        _save_officers(officers)


def _sign(payload_b64: str) -> str:
    return hmac.new(_signing_key().encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()


def _encode_token(officer: OfficerAccount, issued_at: datetime, expires_at: datetime) -> str:
    payload = json.dumps(
        {
            "officer_id": officer.officer_id,
            "name": officer.name,
            "role": officer.role,
            "iat": issued_at.isoformat(),
            "exp": expires_at.isoformat(),
            "nonce": secrets.token_hex(8),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    import base64

    payload_b64 = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    signature = _sign(payload_b64)
    return f"{payload_b64}.{signature}"


def _decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        import base64

        payload_b64, signature = token.rsplit(".", 1)
        if not hmac.compare_digest(signature, _sign(payload_b64)):
            return None
        padding = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8"))
        expires_at = datetime.fromisoformat(payload["exp"])
        if datetime.now(timezone.utc) >= expires_at:
            return None
        return payload
    except Exception:
        return None


def authenticate(officer_id: str, password: str) -> Optional[SessionToken]:
    """Verify credentials and mint a signed session token."""
    ensure_default_officer()
    officers = _load_officers()
    record = officers.get(officer_id.strip())
    if not record:
        return None
    candidate = _hash_password(password, record.get("salt", ""))
    if not hmac.compare_digest(candidate, record.get("password_hash", "")):
        return None

    now = datetime.now(timezone.utc)
    officer = OfficerAccount(
        officer_id=record["officer_id"],
        name=record.get("name", record["officer_id"]),
        role=record.get("role", "COMPLIANCE_OFFICER"),
        password_hash=record["password_hash"],
        created_at=record.get("created_at", now.isoformat()),
        last_login=now.isoformat(),
    )
    record["last_login"] = now.isoformat()
    _save_officers(officers)

    expires = now + timedelta(hours=TOKEN_TTL_HOURS)
    return SessionToken(
        token=_encode_token(officer, now, expires),
        officer_id=officer.officer_id,
        name=officer.name,
        role=officer.role,
        issued_at=now.isoformat(),
        expires_at=expires.isoformat(),
    )


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Return the token payload if valid and unexpired, else None."""
    if not token or not token.strip():
        return None
    return _decode_token(token.strip())


def list_officers() -> list[Dict[str, Any]]:
    ensure_default_officer()
    officers = _load_officers()
    return [
        {
            "officer_id": o["officer_id"],
            "name": o.get("name", ""),
            "role": o.get("role", "COMPLIANCE_OFFICER"),
            "last_login": o.get("last_login"),
        }
        for o in officers.values()
    ]
