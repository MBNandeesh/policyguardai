"""Synthetic tests: officer login + end-to-end decision recording.

Covers:
- Login success/failure and token shape
- Token verification and expiry rejection
- /auth/me with and without bearer token
- Full officer decision loop: login -> record decision via /review/actions
  -> event present in audit chain -> chain verifies intact
"""

import pytest
from fastapi.testclient import TestClient

from app.audit import service as audit_service
from app.main import app

client = TestClient(app)

VALID_OFFICER = {"officer_id": "officer-001", "password": "officer123"}


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    import app.audit.service as audit_mod
    import app.auth.service as auth_mod

    monkeypatch.setattr(audit_mod, "STORAGE_ROOT", str(tmp_path / "audit"))
    monkeypatch.setattr(auth_mod, "STORAGE_ROOT", str(tmp_path / "auth"))
    yield


class TestOfficerLogin:
    def test_login_success_returns_signed_session(self):
        resp = client.post("/api/v1/auth/login", json=VALID_OFFICER)
        assert resp.status_code == 200
        body = resp.json()
        assert body["officer_id"] == "officer-001"
        assert body["name"]
        assert body["token"]
        assert body["token"].count(".") == 1  # payload.signature
        assert body["expires_at"]
        # 12h TTL: expiry must be in the future
        from datetime import datetime, timezone
        assert datetime.fromisoformat(body["expires_at"]) > datetime.now(timezone.utc)

    def test_login_wrong_password_is_401(self):
        resp = client.post(
            "/api/v1/auth/login",
            json={"officer_id": "officer-001", "password": "wrong"},
        )
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

    def test_login_unknown_officer_is_401(self):
        resp = client.post(
            "/api/v1/auth/login",
            json={"officer_id": "ghost-999", "password": "whatever"},
        )
        assert resp.status_code == 401

    def test_login_missing_fields_is_422(self):
        resp = client.post("/api/v1/auth/login", json={"officer_id": "officer-001"})
        assert resp.status_code == 422

    def test_officers_listing_hides_credentials(self):
        resp = client.get("/api/v1/auth/officers")
        assert resp.status_code == 200
        officers = resp.json()
        assert any(o["officer_id"] == "officer-001" for o in officers)
        for o in officers:
            assert "password" not in json_keys(o)
            assert "password_hash" not in json_keys(o)
            assert "token" not in json_keys(o)


def json_keys(obj):
    return set(obj.keys())


class TestSessionVerification:
    def _login(self):
        resp = client.post("/api/v1/auth/login", json=VALID_OFFICER)
        return resp.json()["token"]

    def test_me_with_valid_token(self):
        token = self._login()
        resp = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["officer_id"] == "officer-001"

    def test_me_without_token_is_401(self, anon_client):
        resp = anon_client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_with_garbage_token_is_401(self):
        resp = client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not.a.real.token"}
        )
        assert resp.status_code == 401

    def test_tampered_token_signature_rejected(self):
        token = self._login()
        payload, sig = token.rsplit(".", 1)
        tampered = f"{payload}{'0' if sig[0] != '0' else '1'}{sig[1:]}"
        resp = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"}
        )
        assert resp.status_code == 401

    def test_expired_token_rejected(self, monkeypatch):
        import app.auth.service as auth_service
        from datetime import datetime, timedelta, timezone

        token = self._login()
        # Verify directly that an expired token payload fails verify_token.
        import base64, json as jsonlib

        payload_b64, sig = token.rsplit(".", 1)
        payload = jsonlib.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))
        payload["exp"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        # Re-sign with the known demo key to isolate expiry (not signature) rejection.
        import hashlib, hmac

        raw = jsonlib.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload_b64 = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
        sig = hmac.new(
            auth_service._signing_key().encode(), payload_b64.encode(), hashlib.sha256
        ).hexdigest()
        assert auth_service.verify_token(f"{payload_b64}.{sig}") is None

    def test_logout_roundtrip(self):
        token = self._login()
        resp = client.post(
            "/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "logged_out"


class TestOfficerDecisionEndToEnd:
    """Login -> record decision -> verify audit chain."""

    def _login(self):
        resp = client.post("/api/v1/auth/login", json=VALID_OFFICER)
        return resp.json()["token"]

    def _record(self, token, action="ACCEPT", reason="Approved after evidence check"):
        return client.post(
            "/api/v1/review/actions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "actor": "officer-001",
                "action": action,
                "finding_id": "report-synthetic-1",
                "reason": reason,
                "metadata": {"decision": "APPROVE"},
            },
        )

    def test_decision_rejected_without_token(self, anon_client):
        """Protected operation: unauthenticated decision attempts are rejected."""
        resp = anon_client.post(
            "/api/v1/review/actions",
            json={
                "actor": "officer-001",
                "action": "ACCEPT",
                "finding_id": "report-nologin",
                "reason": "no session",
            },
        )
        assert resp.status_code == 401
        assert audit_service.read_chain(entity_id="report-nologin") == []

    def test_recorded_decision_lands_in_audit_chain(self):
        token = self._login()
        resp = self._record(token)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "RECORDED"
        assert body["audit_event_hash"]

        events = audit_service.read_chain(entity_id="report-synthetic-1")
        assert len(events) == 1
        assert events[0].action == "REVIEW_ACCEPT"
        assert events[0].actor == "officer-001"

    def test_full_decision_loop_chain_verifies(self):
        token = self._login()
        self._record(token, "ACCEPT", "All mandatory requirements met")
        self._record(token, "OVERRIDE", "Risk downgraded after portal verification")

        report = audit_service.verify_chain()
        assert report["valid"] is True
        assert report["events"] == 2
        assert report["broken_at"] is None

        actions = client.get(
            "/api/v1/review/actions", params={"finding_id": "report-synthetic-1"}
        ).json()
        assert len(actions) == 2
        assert {a["action"] for a in actions} == {"REVIEW_ACCEPT", "REVIEW_OVERRIDE"}

    def test_do_not_proceed_requires_reason(self):
        token = self._login()
        resp = client.post(
            "/api/v1/review/actions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "actor": "officer-001",
                "action": "OVERRIDE",
                "finding_id": "report-synthetic-2",
                "reason": "",
            },
        )
        assert resp.status_code == 422
        assert "reason" in resp.json()["detail"].lower()

    def test_decision_rejected_without_login(self, anon_client):
        """Negative control: the API must not accept unauthenticated decisions."""
        resp = anon_client.post(
            "/api/v1/review/actions",
            json={
                "actor": "anonymous",
                "action": "ACCEPT",
                "finding_id": "report-x",
                "reason": "no session",
            },
        )
        assert resp.status_code == 401
        assert audit_service.read_chain(entity_id="report-x") == []
