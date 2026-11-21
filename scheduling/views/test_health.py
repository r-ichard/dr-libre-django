from django.test import Client


def returns_200_when_health_endpoint_is_requested() -> None:
    client = Client()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response["Content-Type"] == "application/json"


def returns_json_when_browser_accepts_html() -> None:
    client = Client()

    response = client.get("/api/v1/health", headers={"Accept": "text/html"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
