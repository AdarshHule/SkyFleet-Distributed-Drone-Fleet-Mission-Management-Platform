import httpx
from fastapi.testclient import TestClient

from skyfleet_gateway.app import create_app

CID = "11111111-1111-1111-1111-111111111111"
LAND = {"drone_id": "SF-PN-001", "site_id": "PUNE-001", "type": "LAND"}


def fake_command_service(request: httpx.Request) -> httpx.Response:
    if request.method == "POST" and request.url.path == "/v1/commands":
        key = request.headers.get("Idempotency-Key")
        status = 200 if key == "already-used" else 201
        return httpx.Response(
            status, json={"command_id": CID, "state": "PENDING", "key": key}
        )
    if request.url.path == f"/v1/commands/{CID}":
        return httpx.Response(200, json={"command_id": CID, "state": "COMPLETED"})
    return httpx.Response(404, json={"detail": "command not found"})


def client_with(handler) -> TestClient:
    return TestClient(
        create_app(transport=httpx.MockTransport(handler), start_mqtt=False)
    )


def test_create_passes_201_through():
    with client_with(fake_command_service) as c:
        r = c.post("/api/v1/commands", json=LAND)
    assert r.status_code == 201


def test_replay_passes_200_through():
    with client_with(fake_command_service) as c:
        r = c.post(
            "/api/v1/commands", json=LAND, headers={"Idempotency-Key": "already-used"}
        )
    assert r.status_code == 200


def test_idempotency_key_is_forwarded():
    with client_with(fake_command_service) as c:
        r = c.post(
            "/api/v1/commands", json=LAND, headers={"Idempotency-Key": "click-42"}
        )
    assert r.json()["key"] == "click-42"


def test_upstream_validation_error_is_passed_through_as_422():
    def rejects(request):
        return httpx.Response(422, json={"detail": "GOTO needs a target"})

    with client_with(rejects) as c:
        r = c.post("/api/v1/commands", json={**LAND, "type": "GOTO"})
    assert r.status_code == 422
    assert r.json()["detail"] == "GOTO needs a target"


def test_bad_command_id_never_reaches_the_service():
    calls = []

    def spy(request):
        calls.append(request)
        return fake_command_service(request)

    with client_with(spy) as c:
        assert c.get("/api/v1/commands/not-a-uuid").status_code == 422
    assert calls == []


def test_get_command():
    with client_with(fake_command_service) as c:
        assert c.get(f"/api/v1/commands/{CID}").json()["state"] == "COMPLETED"


def test_command_service_down_is_503():
    def down(request):
        raise httpx.ConnectError("connection refused", request=request)

    with client_with(down) as c:
        r = c.post("/api/v1/commands", json=LAND)
    assert r.status_code == 503
    assert r.json()["detail"] == "command service unavailable"
