from uuid import uuid4

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
    assert len(payload["skill_cards"]) == 3
    assert {card["scenario_id"] for card in payload["skill_cards"]} == {"interview"}
    assert all(card["expression"] for card in payload["skill_cards"])
    assert all(card["prompt"] for card in payload["skill_cards"])


@pytest.mark.anyio
async def test_create_session_returns_fresh_skill_cards_per_round() -> None:
    user_id = f"skill-cards-{uuid4()}"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.post(
            "/api/sessions",
            json={"scenario_id": "restaurant", "difficulty": "a2", "user_id": user_id},
        )
        second_response = await client.post(
            "/api/sessions",
            json={"scenario_id": "restaurant", "difficulty": "a2", "user_id": user_id},
        )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    first_cards = [card["expression"] for card in first_response.json()["skill_cards"]]
    second_cards = [card["expression"] for card in second_response.json()["skill_cards"]]
    assert len(first_cards) == 3
    assert len(second_cards) == 3
    assert first_cards != second_cards


@pytest.mark.anyio
async def test_create_session_rejects_unknown_scenario() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/sessions",
            json={"scenario_id": "unknown", "difficulty": "b1", "user_id": "demo"},
        )

    assert response.status_code == 404
