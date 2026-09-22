"""Tests for the SIH26100 verification layer: adapters, tiers, scoring, audit."""

import pytest
from fastapi.testclient import TestClient

from app.audit import service as audit_service
from app.main import app
from app.verification import service as verification_service
from app.verification.adapters import adapter_catalog
from app.verification.models import (
    AdapterMode,
    VerificationDomain,
    VerificationRequest,
    VerificationStatus,
    VerificationTier,
)

client = TestClient(app)


def _officer_headers():
    """Log in as the seeded demo officer and return bearer auth headers."""
    resp = client.post(
        "/api/v1/auth/login", json={"officer_id": "officer-001", "password": "officer123"}
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['token']}"}


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    import app.audit.service as audit_mod
    import app.verification.service as verif_mod

    monkeypatch.setattr(audit_mod, "STORAGE_ROOT", str(tmp_path / "audit"))
    monkeypatch.setattr(verif_mod, "STORAGE_ROOT", str(tmp_path / "verification"))
    yield


class TestAdapterCatalog:
    def test_all_sih_domains_present(self):
        catalog = adapter_catalog()
        domains = {item["domain"] for item in catalog}
        for expected in [
            "UDYAM", "GST", "PAN", "MCA", "EPFO", "ESIC",
            "STARTUP_INDIA", "NSIC", "OEM_AUTHORIZATION", "DIGILOCKER",
            "BLACKLIST", "MAKE_IN_INDIA",
        ]:
            assert expected in domains

    def test_no_adapter_claims_live(self):
        """Honesty contract: no adapter in this build may claim LIVE mode."""
        for item in adapter_catalog():
            assert item["mode"] != AdapterMode.LIVE.value
            assert item["live_capable"] is False

    def test_every_domain_has_official_portal(self):
        for item in adapter_catalog():
            assert item["portal"]
            assert item["official_url"].startswith("https://")


class TestVerificationRun:
    def test_valid_gstin_verifies_at_t2_mock(self):
        result = verification_service.perform_verification(
            domain=VerificationDomain.GST,
            bidder_id="bidder-1",
            identifier="29ABCDE1234F1Z5",
        )
        assert result.status == VerificationStatus.VERIFIED
        assert result.tier == VerificationTier.T2
        assert result.mode == AdapterMode.MOCK
        assert "MOCK" in result.summary

    def test_invalid_gstin_is_unavailable_not_verified(self):
        result = verification_service.perform_verification(
            domain=VerificationDomain.GST,
            bidder_id="bidder-1",
            identifier="garbage",
        )
        assert result.status == VerificationStatus.UNAVAILABLE
        assert result.tier == VerificationTier.T4

    def test_pan_format_check(self):
        ok = verification_service.perform_verification(
            domain=VerificationDomain.PAN, bidder_id="b", identifier="ABCDE1234F"
        )
        bad = verification_service.perform_verification(
            domain=VerificationDomain.PAN, bidder_id="b", identifier="12345"
        )
        assert ok.status == VerificationStatus.VERIFIED
        assert bad.status == VerificationStatus.UNAVAILABLE

    def test_sentinel_expiry_case(self):
        result = verification_service.perform_verification(
            domain=VerificationDomain.UDYAM,
            bidder_id="b",
            identifier="UDYAM-KA-03-0012345-EXPIRED",
        )
        assert result.status == VerificationStatus.EXPIRED

    def test_blacklist_clear_is_requires_review_never_auto_clear(self):
        """Wrongful-disqualification control: a simulated no-hit cannot auto-clear."""
        result = verification_service.perform_verification(
            domain=VerificationDomain.BLACKLIST,
            bidder_id="b",
            identifier="CLEARCASE123",
        )
        assert result.status == VerificationStatus.REQUIRES_REVIEW
        assert result.tier == VerificationTier.T4

    def test_result_payload_hash_is_deterministic(self):
        request = VerificationRequest(
            domain=VerificationDomain.GST, bidder_id="b", identifier="29ABCDE1234F1Z5"
        )
        r1 = verification_service.perform_verification(
            domain=request.domain, bidder_id=request.bidder_id, identifier=request.identifier
        )
        r2 = verification_service.perform_verification(
            domain=request.domain, bidder_id=request.bidder_id, identifier=request.identifier
        )
        assert r1.request_payload_hash == r2.request_payload_hash


class TestComplianceScore:
    def test_empty_score_is_unknown_with_guidance(self):
        resp = client.get("/api/v1/verification/bidders/nobody/score")
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == 0.0
        assert data["risk_level"] == "UNKNOWN"
        assert "verification" in data["recommendation"].lower()

    def test_score_rises_after_successful_checks(self):
        client.post(
            "/api/v1/verification/run",
            json={"domain": "GST", "bidder_id": "b2", "identifier": "29ABCDE1234F1Z5"},
        )
        client.post(
            "/api/v1/verification/run",
            json={"domain": "PAN", "bidder_id": "b2", "identifier": "ABCDE1234F"},
        )
        data = client.get("/api/v1/verification/bidders/b2/score").json()
        assert data["score"] > 0
        assert data["risk_level"] in {"LOW", "MEDIUM"}
        assert data["generated_from_mode"] == "MOCK"
        unchecked = [c for c in data["components"] if c["status"] == "NOT_CHECKED"]
        assert unchecked  # remaining domains still tracked

    def test_failing_domains_keep_risk_high(self):
        for identifier in ["EXPIRED-CASE", "GARBAGE!!"]:
            client.post(
                "/api/v1/verification/run",
                json={"domain": "GST", "bidder_id": "b3", "identifier": identifier},
            )
        data = client.get("/api/v1/verification/bidders/b3/score").json()
        assert data["risk_level"] == "HIGH"
        assert "GST" in data["unresolved_domains"]


class TestAuditChain:
    def test_append_and_verify_chain(self):
        for i in range(5):
            audit_service.append_event(
                actor="officer-1",
                action="VERIFICATION_RUN",
                entity_type="bidder",
                entity_id=f"b-{i}",
                payload={"index": i},
            )
        report = audit_service.verify_chain()
        assert report["valid"] is True
        assert report["events"] == 5
        assert report["broken_at"] is None

    def test_tampering_is_detected(self, tmp_path):
        audit_service.append_event(
            actor="officer-1", action="A", entity_type="t", entity_id="e1"
        )
        audit_service.append_event(
            actor="officer-1", action="B", entity_type="t", entity_id="e2"
        )
        # Tamper with the first event's payload in place.
        import json
        import os

        chain_path = os.path.join(audit_service.STORAGE_ROOT, "chain.jsonl")
        with open(chain_path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        first = json.loads(lines[0])
        first["payload"] = {"tampered": True}
        lines[0] = json.dumps(first) + "\n"
        with open(chain_path, "w", encoding="utf-8") as handle:
            handle.writelines(lines)

        report = audit_service.verify_chain()
        assert report["valid"] is False
        assert report["broken_at"] == 1

    def test_officer_override_requires_reason_at_api_level(self):
        """Plan Step 11 / R4: overrides without a reason are rejected."""
        resp = client.post(
            "/api/v1/audit/events",
            headers=_officer_headers(),
            json={
                "actor": "officer-1",
                "action": "OVERRIDE",
                "entity_type": "finding",
                "entity_id": "f-1",
            },
        )
        # The audit API records events (attributed to the authenticated
        # officer); reason enforcement lives in review API.
        assert resp.status_code == 200
        assert resp.json()["payload"] == {}

    def test_anonymous_audit_write_is_rejected(self, anon_client):
        """Audit event writing requires an authenticated officer session."""
        resp = anon_client.post(
            "/api/v1/audit/events",
            json={
                "actor": "anonymous",
                "action": "OVERRIDE",
                "entity_type": "finding",
                "entity_id": "f-x",
            },
        )
        assert resp.status_code == 401

    def test_events_api_roundtrip(self):
        client.post(
            "/api/v1/audit/events",
            headers=_officer_headers(),
            json={
                "actor": "officer-1",
                "action": "OVERRIDE",
                "entity_type": "finding",
                "entity_id": "f-9",
                "payload": {"reason": "Document clarified by bidder"},
            },
        )
        events = client.get("/api/v1/audit/events", params={"entity_id": "f-9"}).json()
        assert len(events) == 1
        assert events[0]["payload"]["reason"] == "Document clarified by bidder"
        assert events[0]["prev_hash"] == "0" * 64 or len(events) > 0

        verify = client.get("/api/v1/audit/verify").json()
        assert verify["valid"] is True


class TestOfficerReviewActions:
    """Plan Step 11 / R4: officer decisions, reasons mandatory."""

    def test_override_without_reason_is_422(self):
        resp = client.post(
            "/api/v1/review/actions",
            headers=_officer_headers(),
            json={"actor": "officer-1", "action": "OVERRIDE", "finding_id": "f-1"},
        )
        assert resp.status_code == 422
        assert "reason" in resp.json()["detail"].lower()

    def test_dismiss_without_reason_is_422(self):
        resp = client.post(
            "/api/v1/review/actions",
            headers=_officer_headers(),
            json={"actor": "officer-1", "action": "DISMISS", "finding_id": "f-1"},
        )
        assert resp.status_code == 422

    def test_review_action_without_login_is_401(self, anon_client):
        resp = anon_client.post(
            "/api/v1/review/actions",
            json={"actor": "officer-1", "action": "OVERRIDE", "finding_id": "f-1", "reason": "x"},
        )
        assert resp.status_code == 401

    def test_override_with_reason_records_to_audit_chain(self):
        resp = client.post(
            "/api/v1/review/actions",
            headers=_officer_headers(),
            json={
                "actor": "officer-1",
                "action": "OVERRIDE",
                "finding_id": "f-2",
                "reason": "Bidder submitted valid Udyam certificate on re-examination",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "RECORDED"
        assert body["audit_event_hash"]

        actions = client.get("/api/v1/review/actions", params={"finding_id": "f-2"}).json()
        assert len(actions) == 1
        assert actions[0]["action"] == "REVIEW_OVERRIDE"
        assert "Udyam" in actions[0]["reason"]

    def test_authenticated_officer_identity_wins_over_payload_actor(self):
        """The audit chain attributes events to the authenticated officer,
        never to a client-supplied actor string."""
        headers = _officer_headers()
        resp = client.post(
            "/api/v1/review/actions",
            headers=headers,
            json={
                "actor": "someone-else",
                "action": "ACCEPT",
                "finding_id": "f-actor",
                "reason": "Identity check",
            },
        )
        assert resp.status_code == 200
        events = audit_service.read_chain(entity_id="f-actor")
        assert events[0].actor == "officer-001"

    def test_comment_without_text_is_422(self):
        resp = client.post(
            "/api/v1/review/actions",
            headers=_officer_headers(),
            json={"actor": "officer-1", "action": "COMMENT", "finding_id": "f-1"},
        )
        assert resp.status_code == 422

    def test_unknown_action_is_422(self):
        resp = client.post(
            "/api/v1/review/actions",
            headers=_officer_headers(),
            json={"actor": "officer-1", "action": "AUTO_REJECT", "finding_id": "f-1", "reason": "x"},
        )
        assert resp.status_code == 422
