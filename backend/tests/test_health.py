"""Health endpoint contract tests."""


def test_health_returns_ok(client) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "GeneVerify AI API"
    assert body["environment"] in {"development", "staging", "production"}
    assert body["version"]


def test_unknown_route_returns_error_envelope(client) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
