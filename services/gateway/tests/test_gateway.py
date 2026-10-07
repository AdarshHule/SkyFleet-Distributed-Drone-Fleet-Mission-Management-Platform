import httpx
from fastapi.testclient import TestClient

from skyfleet_gateway.app import create_app

DRONE = {"drone_id": "SF-PN-001", "battery_pct": 97}


def fake_telemetry(request: httpx.Request) -> httpx.Response:
    """Pretends to be the telemetry API."""
    path = request.url.path
    if path == "/v1/drones":
        return httpx.Response(200, json=[DRONE])
    if path == "/v1/drones/SF-PN-001":
        return httpx.Response(200, json=DRONE)
    if path == "/v1/drones/SF-PN-001/history":
        return httpx.Response(200, json=[DRONE] * int(request.url.params["limit"]))
    return httpx.Response(404, json={"detail": "drone not found"})


def client_with(handler) -> TestClient:
    return TestClient(create_app(transport=httpx.MockTransport(handler)))


def test_list_drones_passes_through():
    with client_with(fake_telemetry) as c:
        assert c.get("/api/v1/drones").json() == [DRONE]


def test_history_forwards_limit():
    with client_with(fake_telemetry) as c:
        assert len(c.get("/api/v1/drones/SF-PN-001/history?limit=3").json()) == 3


def test_unknown_drone_is_404():
    with client_with(fake_telemetry) as c:
        assert c.get("/api/v1/drones/SF-XX-999").status_code == 404


def test_invalid_drone_id_never_reaches_telemetry():
    calls = []

    def spy(request):
        calls.append(request)
        return fake_telemetry(request)

    with client_with(spy) as c:
        assert c.get("/api/v1/drones/not-a-drone").status_code == 422
    assert calls == []  # the gateway rejected it before making any call


def test_telemetry_down_is_503():
    def down(request):
        raise httpx.ConnectError("connection refused", request=request)

    with client_with(down) as c:
        assert c.get("/api/v1/drones").status_code == 503


def test_telemetry_timeout_is_504():
    def slow(request):
        raise httpx.ReadTimeout("too slow", request=request)

    with client_with(slow) as c:
        assert c.get("/api/v1/drones").status_code == 504


def test_telemetry_crash_is_502():
    def broken(request):
        return httpx.Response(500)

    with client_with(broken) as c:
        assert c.get("/api/v1/drones").status_code == 502
