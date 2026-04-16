from fastapi.testclient import TestClient

from app.main import create_app


def test_create_app_exposes_health_and_static_mount() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
