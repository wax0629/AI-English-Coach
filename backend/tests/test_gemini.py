from uuid import uuid4

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


async def create_practice_session(
    client: httpx.AsyncClient,
    scenario_id: str = "interview",
    difficulty: str = "b1",
    user_id: str = "demo",
) -> str:
    response = await client.post(
        "/api/sessions",
        json={"scenario_id": scenario_id, "difficulty": difficulty, "user_id": user_id},
    )

    assert response.status_code == 201
    return str(response.json()["session_id"])


async def add_turn(client: httpx.AsyncClient, session_id: str, role: str, text: str) -> None:
    response = await client.post(
        "/api/conversation/turns",
        json={"session_id": session_id, "role": role, "text": text},
    )
    assert response.status_code == 201


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
    assert setup["inputAudioTranscription"] == {}
    assert setup["outputAudioTranscription"] == {}

    instruction_text = setup["systemInstruction"]["parts"][0]["text"]
    assert "Hiring Manager" in instruction_text
    assert "求职面试" in instruction_text


@pytest.mark.anyio
async def test_gemini_live_token_includes_learner_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = f"gemini-memory-{uuid4()}"
    captured_config: dict[str, object] = {}
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        _env_file=None,
        GEMINI_API_KEY="gemini-test-key",
        REPORT_LLM_PROVIDER="rules",
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
        old_session_id = await create_practice_session(
            client,
            scenario_id="restaurant",
            difficulty="a2",
            user_id=user_id,
        )
        await add_turn(client, old_session_id, "user", "I want cappuccino. Can you recommend me dessert?")
        report_response = await client.post(f"/api/sessions/{old_session_id}/report")

        next_session_id = await create_practice_session(
            client,
            scenario_id="restaurant",
            difficulty="a2",
            user_id=user_id,
        )
        response = await client.post("/api/gemini/live-token", json={"session_id": next_session_id})

    assert report_response.status_code == 201
    assert response.status_code == 201
    setup = captured_config["bidiGenerateContentSetup"]
    instruction_text = setup["systemInstruction"]["parts"][0]["text"]
    assert "Learner memory:" in instruction_text
    assert "I'd like" in instruction_text
    assert "Could I have" in instruction_text


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
