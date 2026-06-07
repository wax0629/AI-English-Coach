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


async def create_practice_session(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/api/sessions",
        json={"scenario_id": "interview", "difficulty": "b1", "user_id": "demo"},
    )

    assert response.status_code == 201
    return str(response.json()["session_id"])


@pytest.mark.anyio
async def test_create_and_list_conversation_turns() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        create_response = await client.post(
            "/api/conversation/turns",
            json={
                "session_id": session_id,
                "role": "user",
                "text": "I was responsible for customer interviews.",
            },
        )
        list_response = await client.get(f"/api/sessions/{session_id}/turns")

    assert create_response.status_code == 201
    created_turn = create_response.json()
    assert created_turn["turn_id"]
    assert created_turn["session_id"] == session_id
    assert created_turn["role"] == "user"
    assert created_turn["text"] == "I was responsible for customer interviews."

    assert list_response.status_code == 200
    turns = list_response.json()
    assert [turn["turn_id"] for turn in turns] == [created_turn["turn_id"]]
    assert turns[0]["created_at"] is not None


@pytest.mark.anyio
async def test_create_turn_rejects_unknown_session() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/conversation/turns",
            json={
                "session_id": "missing-session",
                "role": "assistant",
                "text": "Tell me about your recent project.",
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown session_id: missing-session"


@pytest.mark.anyio
async def test_list_turns_rejects_unknown_session() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/sessions/missing-session/turns")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_demo_conversation_populates_a_session_once() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_response = await client.post(
            "/api/sessions",
            json={"scenario_id": "restaurant", "difficulty": "a2", "user_id": "demo"},
        )
        session_id = session_response.json()["session_id"]

        response = await client.post(f"/api/sessions/{session_id}/demo-turns")
        second_response = await client.post(f"/api/sessions/{session_id}/demo-turns")

    assert response.status_code == 201
    payload = response.json()
    assert payload["created"] is True
    assert len(payload["turns"]) >= 4
    assert {turn["role"] for turn in payload["turns"]} == {"user", "assistant"}
    assert "cappuccino" in " ".join(turn["text"].lower() for turn in payload["turns"])

    assert second_response.status_code == 201
    second_payload = second_response.json()
    assert second_payload["created"] is False
    assert [turn["turn_id"] for turn in second_payload["turns"]] == [turn["turn_id"] for turn in payload["turns"]]
