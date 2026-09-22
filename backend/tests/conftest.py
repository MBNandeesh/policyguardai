"""Shared pytest fixtures for the PolicyGuard AI backend test suite.

The API now requires officer authentication for sensitive operations
(upload, compliance analysis/decisions, review actions, audit writes). To
keep the existing test suite meaningful, this conftest attaches the demo
officer bearer token to every TestClient request automatically.

Tests that must assert unauthenticated (401) behavior use the ``anon_client``
fixture, whose client never sends the Authorization header.
"""

import pytest
from fastapi.testclient import TestClient

from app.auth import service as auth_service
from app.main import app

_cached_token = None
_original_request = TestClient.request


def _officer_token() -> str:
    global _cached_token
    if _cached_token is None:
        session = auth_service.authenticate("officer-001", "officer123")
        assert session is not None, "demo officer login failed in conftest"
        _cached_token = session.token
    return _cached_token


def _patched_request(self, *args, **kwargs):
    headers = kwargs.get("headers") or {}
    url = args[1] if len(args) > 1 else str(kwargs.get("url", ""))
    skip = (
        getattr(self, "_no_auth", False)
        or "/auth/login" in str(url)
    )
    if not skip and "Authorization" not in headers:
        kwargs["headers"] = {"Authorization": f"Bearer {_officer_token()}", **headers}
    return _original_request(self, *args, **kwargs)


class NoAuthTestClient(TestClient):
    """TestClient that never injects the officer token (for 401 assertions)."""

    _no_auth = True


@pytest.fixture(autouse=True)
def officer_auth(monkeypatch):
    monkeypatch.setattr(TestClient, "request", _patched_request)
    yield


@pytest.fixture
def anon_client():
    """TestClient without automatic auth - use to assert 401 behavior."""
    return NoAuthTestClient(app)
