"""Lightweight tests for health and readiness endpoints."""

from fastapi.testclient import TestClient

from server.main import app

# Use base_url to simulate localhost access
client = TestClient(app, base_url="http://127.0.0.1")


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"


def test_readiness_returns_ready():
    response = client.get("/readiness")
    assert response.status_code == 200
    assert response.json().get("status") == "ready"
