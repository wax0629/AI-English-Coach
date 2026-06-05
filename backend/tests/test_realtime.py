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
async def test_realtime_client_secret_requires_openai_api_key() -> None:
    app.dependency_overrides[get_app_settings] = lambda: Settings(OPENAI_API_KEY="")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        response = await client.post("/api/realtime/client-secret", json={"session_id": session_id})

    assert response.status_code == 503
    assert response.json()["detail"] == "OPENAI_API_KEY is not configured"


@pytest.mark.anyio
async def test_realtime_client_secret_uses_session_scenario(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_config: dict[str, object] = {}
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        OPENAI_API_KEY="sk-test",
        OPENAI_REALTIME_MODEL="gpt-realtime",
        OPENAI_REALTIME_VOICE="marin",
    )

    async def fake_request_openai_client_secret(
        settings: Settings,
        session_config: dict[str, object],
        user_id: str,
    ) -> dict[str, object]:
        captured_config.update(session_config)
        assert settings.openai_api_key == "sk-test"
        assert user_id == "demo"
        return {
            "value": "ek_test_secret",
            "expires_at": 1_800_000_000,
            "session": {"id": "sess_realtime_123"},
        }

    monkeypatch.setattr(
        "app.routes.realtime.request_openai_client_secret",
        fake_request_openai_client_secret,
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        response = await client.post("/api/realtime/client-secret", json={"session_id": session_id})

    assert response.status_code == 201
    payload = response.json()
    assert payload == {
        "session_id": session_id,
        "realtime_session_id": "sess_realtime_123",
        "client_secret": "ek_test_secret",
        "expires_at": 1_800_000_000,
        "model": "gpt-realtime",
        "voice": "marin",
    }
    assert captured_config["session"]["type"] == "realtime"
    assert captured_config["session"]["model"] == "gpt-realtime"
    assert captured_config["session"]["audio"]["output"]["voice"] == "marin"
    assert "Hiring Manager" in captured_config["session"]["instructions"]
    assert "求职面试" in captured_config["session"]["instructions"]
