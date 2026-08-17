from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
