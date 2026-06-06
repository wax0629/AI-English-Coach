import httpx
import pytest

from app.config import Settings
from app.database import init_db
from app.dependencies import get_app_settings
from app.main import app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def ensure_database() -> None:
    init_db()
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


async def create_practice_session(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/api/sessions",
        json={"scenario_id": "interview", "difficulty": "b1", "user_id": "demo"},
    )

    assert response.status_code == 201
    return str(response.json()["session_id"])


@pytest.mark.anyio
async def test_gemini_live_token_requires_api_key() -> None:
    app.dependency_overrides[get_app_settings] = lambda: Settings(GEMINI_API_KEY="")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        response = await client.post("/api/gemini/live-token", json={"session_id": session_id})

    assert response.status_code == 503
    assert response.json()["detail"] == "GEMINI_API_KEY is not configured"


@pytest.mark.anyio
async def test_gemini_live_token_uses_session_constraints(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_config: dict[str, object] = {}
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        GEMINI_API_KEY="gemini-test-key",
        GEMINI_LIVE_MODEL="gemini-3.1-flash-live-preview",
    )

    async def fake_request_gemini_live_token(
        settings: Settings,
        token_config: dict[str, object],
    ) -> dict[str, object]:
        captured_config.update(token_config)
        assert settings.gemini_api_key == "gemini-test-key"
        return {
            "name": "auth_tokens/gemini_ephemeral",
            "expireTime": "2026-06-06T02:30:00Z",
            "newSessionExpireTime": "2026-06-06T02:01:00Z",
        }

    monkeypatch.setattr(
        "app.routes.gemini.request_gemini_live_token",
        fake_request_gemini_live_token,
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        response = await client.post("/api/gemini/live-token", json={"session_id": session_id})

    assert response.status_code == 201
    assert response.json() == {
        "session_id": session_id,
        "token": "auth_tokens/gemini_ephemeral",
        "expire_time": "2026-06-06T02:30:00Z",
        "new_session_expire_time": "2026-06-06T02:01:00Z",
        "model": "gemini-3.1-flash-live-preview",
        "api_version": "v1alpha",
    }

    assert captured_config["uses"] == 1
    assert "expireTime" in captured_config
    assert "newSessionExpireTime" in captured_config

    setup = captured_config["bidiGenerateContentSetup"]
    assert setup["model"] == "models/gemini-3.1-flash-live-preview"
    assert setup["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert setup["generationConfig"]["temperature"] == 0.7

    instruction_text = setup["systemInstruction"]["parts"][0]["text"]
    assert "Hiring Manager" in instruction_text
    assert "求职面试" in instruction_text


@pytest.mark.anyio
async def test_gemini_live_token_accepts_model_resource_name(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_config: dict[str, object] = {}
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        GEMINI_API_KEY="gemini-test-key",
        GEMINI_LIVE_MODEL="models/gemini-3.1-flash-live-preview",
    )

    async def fake_request_gemini_live_token(
        settings: Settings,
        token_config: dict[str, object],
    ) -> dict[str, object]:
        captured_config.update(token_config)
        return {"name": "auth_tokens/gemini_ephemeral"}

    monkeypatch.setattr(
        "app.routes.gemini.request_gemini_live_token",
        fake_request_gemini_live_token,
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        response = await client.post("/api/gemini/live-token", json={"session_id": session_id})

    assert response.status_code == 201
    setup = captured_config["bidiGenerateContentSetup"]
    assert setup["model"] == "models/gemini-3.1-flash-live-preview"


@pytest.mark.anyio
async def test_gemini_live_token_rejects_unknown_session() -> None:
    app.dependency_overrides[get_app_settings] = lambda: Settings(GEMINI_API_KEY="gemini-test-key")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/gemini/live-token", json={"session_id": "missing-session"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown session_id: missing-session"
