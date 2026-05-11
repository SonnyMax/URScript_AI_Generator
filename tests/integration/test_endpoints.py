import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock


@pytest.fixture
def app():
    from urscript_app.main import create_app
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# --- /api/validate ---

@pytest.mark.asyncio
async def test_validate_valid_code(client):
    code = "def program():\n  movej([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], a=0.5, v=0.5)\nend"
    r = await client.post("/api/validate", json={"code": code})
    assert r.status_code == 200
    body = r.json()
    assert body["success"]
    assert body["data"]["valid"]


@pytest.mark.asyncio
async def test_validate_missing_end(client):
    code = "def program():\n  movej([0.0]*6, a=0.5, v=0.5)"
    r = await client.post("/api/validate", json={"code": code})
    assert r.status_code == 200
    body = r.json()
    assert body["success"]
    assert not body["data"]["valid"]


# --- /api/generate (mocked LLM) ---

@pytest.mark.asyncio
async def test_generate_returns_code(client):
    mock_response = """```urscript
def program():
  movej([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], a=0.5, v=0.5)
end
```"""
    with patch("urscript_app.llm.client.get_client") as mock_get:
        mock_oai = MagicMock()
        mock_oai.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=mock_response))
        ]
        mock_get.return_value = mock_oai
        r = await client.post("/api/generate", json={"prompt": "move to home"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"]
    assert "movej" in body["data"]["code"]


# --- /api/stop ---

@pytest.mark.asyncio
async def test_stop_always_200(client):
    with patch("urscript_app.robot.safety.get_rtde_client") as mock_rtde:
        mock_rtde.return_value.stop_motion = MagicMock()
        with patch("urscript_app.robot.script_sender.send_script"):
            r = await client.post("/api/stop")
    assert r.status_code == 200
    body = r.json()
    assert body["success"]
    assert body["data"]["stop_requested"]


@pytest.mark.asyncio
async def test_stop_is_idempotent(client):
    with patch("urscript_app.robot.safety.get_rtde_client") as mock_rtde:
        mock_rtde.return_value.stop_motion = MagicMock()
        with patch("urscript_app.robot.script_sender.send_script"):
            r1 = await client.post("/api/stop")
            r2 = await client.post("/api/stop")
    assert r1.status_code == 200
    assert r2.status_code == 200


# --- /api/execute rejects invalid code server-side ---

@pytest.mark.asyncio
async def test_execute_rejects_invalid_code(client):
    bad_code = "def program():\n  socket_open('evil', 80)\nend"
    r = await client.post("/api/execute", json={"code": bad_code})
    assert r.status_code == 200
    body = r.json()
    assert not body["success"]
    assert body["error"]["code"] == "VALIDATION_FAILED"


# --- /healthz ---

@pytest.mark.asyncio
async def test_healthz(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
