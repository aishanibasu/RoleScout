import asyncio
import json
import stat
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import db
from app.sheets import API, TOKEN, GoogleSheets, changed
from app.tracking import router
from tests.test_tracking import seed


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / "roles.sqlite3"
    job = seed(path)
    config = tmp_path / ".env"
    config.write_text("GOOGLE_CLIENT_ID=test-client\nGOOGLE_CLIENT_SECRET=test-secret\n")
    calls = []

    def respond(request):
        calls.append(request)
        if str(request.url) == TOKEN:
            return httpx.Response(
                200, json={"access_token": "access-test", "refresh_token": "refresh-test"}
            )
        if str(request.url) == API:
            return httpx.Response(200, json={"spreadsheetId": "test-sheet"})
        return httpx.Response(200, json={})

    service = GoogleSheets(
        path, config, lambda: httpx.AsyncClient(transport=httpx.MockTransport(respond))
    )
    app = FastAPI()
    app.include_router(service.router())
    app.include_router(router(path))
    return service, TestClient(app), job, calls


def connect(service):
    state, _ = service.begin()
    asyncio.run(service.finish(state, state, "test-code"))


def test_oauth_and_single_sheet_updates(setup):
    service, client, job, calls = setup
    response = client.post("/sheets/connect")
    assert "HttpOnly" in response.headers["set-cookie"]
    params = parse_qs(urlparse(response.json()["authorization_url"]).query)
    assert params["scope"] == ["https://www.googleapis.com/auth/drive.file"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["access_type"] == ["offline"]
    state = params["state"][0]
    response = client.get(
        "/sheets/callback", params={"state": state, "code": "test-code"}, follow_redirects=False
    )
    assert response.headers["location"] == "/?sheets=connected"
    assert stat.S_IMODE(service.token_path.stat().st_mode) == 0o600
    assert "refresh-test" not in json.dumps(client.get("/sheets/status").json())
    for status in ["Saved", "Applied"]:
        assert (
            client.put(
                f"/tracked/{job}", json={"status": status, "notes": '=IMPORTXML("bad")'}
            ).status_code
            == 200
        )
        asyncio.run(service.sync())
        assert not service.status()["pending"]
    assert sum(str(r.url) == API for r in calls) == 1
    updates = [
        json.loads(r.content)["requests"][1]["updateCells"]
        for r in calls
        if ":batchUpdate" in str(r.url)
    ]
    assert len(updates[-1]["rows"]) == 2
    values = updates[-1]["rows"][1]["values"]
    assert values[6]["userEnteredValue"] == {"stringValue": "Applied"}
    assert values[7]["userEnteredValue"] == {"stringValue": '=IMPORTXML("bad")'}
    client.delete(f"/tracked/{job}")
    asyncio.run(service.sync())
    cleared = json.loads(calls[-1].content)["requests"][1]["updateCells"]
    assert cleared["range"]["endRowIndex"] == 2
    assert len(cleared["rows"]) == 1


@pytest.mark.parametrize("failure", ["state", "cookie", "expired", "replay"])
def test_invalid_oauth_never_calls_google(setup, failure):
    service, _, _, calls = setup
    state, _ = service.begin()
    cookie = state
    if failure == "state":
        state = "wrong"
    elif failure == "cookie":
        cookie = "wrong"
    elif failure == "expired":
        service.pending = (state, service.pending[1], 0)
    else:
        service.pending = None
    with pytest.raises(HTTPException):
        asyncio.run(service.finish(state, cookie, "code"))
    assert calls == []


def test_retry_restart_and_concurrent_save(setup):
    service, client, job, calls = setup
    connect(service)
    client.put(f"/tracked/{job}", json={"status": "Saved"})
    original = service.client_factory
    service.client_factory = lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(503, text="secret payload"))
    )
    asyncio.run(service.sync())
    assert service.status()["pending"]
    assert "secret payload" not in service.status()["error"]
    assert len(client.get("/tracked").json()) == 1
    attempts = service.state()["attempts"]
    asyncio.run(service.sync())
    assert service.state()["attempts"] == attempts
    client.post("/sheets/retry")
    restarted = GoogleSheets(service.path, service.config_path, original)
    asyncio.run(restarted.sync())
    assert not restarted.status()["pending"]
    with db.connect(service.path) as conn:
        changed(conn)

    async def racing(request):
        if ":batchUpdate" in str(request.url):
            with db.connect(service.path) as conn:
                changed(conn)
        return httpx.Response(200, json={"access_token": "test-access"})

    restarted.client_factory = lambda: httpx.AsyncClient(transport=httpx.MockTransport(racing))
    asyncio.run(restarted.sync())
    assert restarted.status()["pending"]


def test_disconnect_and_cross_site_protection(setup):
    service, client, job, calls = setup
    connect(service)
    client.put(f"/tracked/{job}", json={"status": "Saved"})
    for action in ["connect", "retry", "disconnect"]:
        assert (
            client.post("/sheets/" + action, headers={"origin": "https://evil.example"}).status_code
            == 403
        )
    assert client.post("/sheets/disconnect").status_code == 200
    assert not service.token_path.exists()
    assert not service.status()["connected"]
    count = len(calls)
    asyncio.run(service.sync())
    assert len(calls) == count
    assert len(client.get("/tracked").json()) == 1


def test_reconnect_reuses_sheet_and_config_required(setup):
    service, client, _, calls = setup
    connect(service)
    with db.connect(service.path) as conn:
        conn.execute("UPDATE sheets_sync SET error='Reconnect Google' WHERE id=1")
    connect(service)
    assert sum(str(r.url) == API for r in calls) == 1
    service.config_path.unlink()
    assert client.post("/sheets/connect").status_code == 409
