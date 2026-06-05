import httpx
import pytest

from app.database import init_db
from app.main import app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def ensure_database() -> None:
    init_db()


@pytest.mark.anyio
async def test_list_scenarios() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/scenarios")

    assert response.status_code == 200
    scenarios = response.json()
    assert {scenario["id"] for scenario in scenarios} == {"interview", "restaurant", "meeting"}


@pytest.mark.anyio
async def test_create_session() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/sessions",
            json={"scenario_id": "interview", "difficulty": "b1", "user_id": "demo"},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["session_id"]
    assert payload["scenario"]["id"] == "interview"
    assert payload["difficulty"] == "b1"
    assert payload["status"] == "active"


@pytest.mark.anyio
async def test_create_session_rejects_unknown_scenario() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/sessions",
            json={"scenario_id": "unknown", "difficulty": "b1", "user_id": "demo"},
        )

    assert response.status_code == 404
