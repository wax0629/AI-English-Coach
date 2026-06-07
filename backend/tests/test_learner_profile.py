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
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        _env_file=None,
        REPORT_LLM_PROVIDER="rules",
    )
    yield
    app.dependency_overrides.clear()


async def create_session(
    client: httpx.AsyncClient,
    user_id: str,
    scenario_id: str = "restaurant",
    difficulty: str = "a2",
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
async def test_report_generation_updates_profile_and_next_session_returns_memory() -> None:
    user_id = f"profile-user-{uuid4()}"
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_session(client, user_id=user_id)
        await add_turn(client, session_id, "assistant", "Welcome. What would you like?")
        await add_turn(client, session_id, "user", "I want cappuccino. Can you recommend me dessert?")

        report_response = await client.post(f"/api/sessions/{session_id}/report")
        profile_response = await client.get(f"/api/learner-profiles/{user_id}")
        next_session_response = await client.post(
            "/api/sessions",
            json={"scenario_id": "restaurant", "difficulty": "a2", "user_id": user_id},
        )

    assert report_response.status_code == 201
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["user_id"] == user_id
    assert profile["practice_count"] == 1
    assert any(item["suggestion"] == "I'd like..." for item in profile["recurring_corrections"])
    assert any(item["expression"] == "Could I have..." for item in profile["missed_expressions"])
    assert any(item["category"] == "correction" for item in profile["focus_areas"])
    assert "I'd like" in profile["coach_note"]

    assert next_session_response.status_code == 201
    next_session = next_session_response.json()
    assert next_session["learner_profile"]["practice_count"] == 1
    assert "I'd like" in next_session["learner_profile"]["coach_note"]


@pytest.mark.anyio
async def test_profile_accumulates_recurring_correction_counts_across_reports() -> None:
    user_id = f"profile-user-{uuid4()}"
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first_session_id = await create_session(client, user_id=user_id, scenario_id="interview", difficulty="b1")
        await add_turn(client, first_session_id, "user", "I responsible for onboarding customers.")
        first_report_response = await client.post(f"/api/sessions/{first_session_id}/report")

        second_session_id = await create_session(client, user_id=user_id, scenario_id="interview", difficulty="b1")
        await add_turn(client, second_session_id, "user", "I responsible for weekly reports.")
        second_report_response = await client.post(f"/api/sessions/{second_session_id}/report")

        profile_response = await client.get(f"/api/learner-profiles/{user_id}")

    assert first_report_response.status_code == 201
    assert second_report_response.status_code == 201
    assert profile_response.status_code == 200
    profile = profile_response.json()
    correction = next(
        item for item in profile["recurring_corrections"] if item["suggestion"] == "I was responsible for..."
    )
    assert profile["practice_count"] == 2
    assert correction["count"] == 2
    assert "I was responsible for" in profile["coach_note"]
