import json

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


async def create_practice_session(
    client: httpx.AsyncClient,
    scenario_id: str = "restaurant",
    difficulty: str = "a2",
) -> str:
    response = await client.post(
        "/api/sessions",
        json={"scenario_id": scenario_id, "difficulty": difficulty, "user_id": "demo"},
    )

    assert response.status_code == 201
    return str(response.json()["session_id"])


async def add_turn(client: httpx.AsyncClient, session_id: str, role: str, text: str) -> None:
    response = await client.post(
        "/api/conversation/turns",
        json={
            "session_id": session_id,
            "role": role,
            "text": text,
        },
    )
    assert response.status_code == 201


@pytest.mark.anyio
async def test_generate_and_get_practice_report() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        await add_turn(client, session_id, "assistant", "Welcome. What would you like today?")
        await add_turn(client, session_id, "user", "Could I have pasta? I want water. Can you recommend me dessert?")
        await add_turn(client, session_id, "assistant", "Of course. Would you like anything else?")
        await add_turn(client, session_id, "user", "Is it possible to make it less spicy?")

        create_response = await client.post(f"/api/sessions/{session_id}/report")
        get_response = await client.get(f"/api/sessions/{session_id}/report")

    assert create_response.status_code == 201
    report = create_response.json()
    assert report["session_id"] == session_id
    assert report["scenario_id"] == "restaurant"
    assert report["difficulty"] == "a2"
    assert report["scores"]["overall"] >= 60
    assert report["scores"]["goal_completion"] >= 70
    assert report["metrics"]["user_turns"] == 2
    assert report["metrics"]["assistant_turns"] == 2
    assert report["metrics"]["word_count"] > 0
    assert report["metrics"]["target_expression_hits"] == ["Could I have...", "Is it possible to..."]
    assert report["metrics"]["missed_target_expressions"] == ["Could you recommend..."]
    assert "目标表达捕手" in report["badges"]
    assert report["strengths"]
    correction_suggestions = {correction["suggestion"] for correction in report["corrections"]}
    assert {"Could you recommend...", "I'd like..."}.issubset(correction_suggestions)
    assert report["drills"][0]["target_expression"] == "Could you recommend..."

    assert get_response.status_code == 200
    assert get_response.json()["report_id"] == report["report_id"]


@pytest.mark.anyio
async def test_generate_report_requires_user_turn() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        await add_turn(client, session_id, "assistant", "How can I help you?")
        response = await client.post(f"/api/sessions/{session_id}/report")

    assert response.status_code == 422
    assert response.json()["detail"] == "At least one user turn is required to generate a report"


@pytest.mark.anyio
async def test_generate_report_updates_existing_report() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client, scenario_id="interview", difficulty="b1")
        await add_turn(client, session_id, "user", "I responsible for customer interviews.")
        first_response = await client.post(f"/api/sessions/{session_id}/report")

        await add_turn(client, session_id, "user", "I was responsible for user research.")
        second_response = await client.post(f"/api/sessions/{session_id}/report")

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    first_report = first_response.json()
    second_report = second_response.json()
    assert second_report["report_id"] == first_report["report_id"]
    assert second_report["metrics"]["user_turns"] == 2
    assert second_report["metrics"]["target_expression_hits"] == ["I was responsible for..."]


@pytest.mark.anyio
async def test_generate_report_can_use_gemini_llm_enhancement(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        REPORT_LLM_PROVIDER="gemini",
        GEMINI_API_KEY="gemini-test-key",
        GEMINI_REPORT_MODEL="gemini-3.5-flash",
    )

    async def fake_request_gemini_report(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "summary": "LLM 复盘：表达更自然，下一步重点练习礼貌请求。",
            "scores": {"overall": 88, "fluency": 82, "grammar": 91, "vocabulary": 86, "goal_completion": 90},
            "strengths": ["能围绕点餐目标推进对话。"],
            "corrections": [
                {
                    "original": "I want water",
                    "suggestion": "I'd like some water.",
                    "reason": "服务场景里更礼貌自然。",
                    "severity": "low",
                }
            ],
            "drills": [
                {
                    "title": "礼貌点餐复练",
                    "prompt": "用 I'd like... 完成一次点餐请求。",
                    "target_expression": "I'd like...",
                }
            ],
        }

    monkeypatch.setattr("app.report_llm.request_gemini_report", fake_request_gemini_report)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        await add_turn(client, session_id, "user", "Could I have pasta? I want water.")
        response = await client.post(f"/api/sessions/{session_id}/report")

    assert response.status_code == 201
    report = response.json()
    assert report["summary"] == "LLM 复盘：表达更自然，下一步重点练习礼貌请求。"
    assert report["scores"]["overall"] == 88
    assert report["metrics"]["generation_mode"] == "llm"
    assert report["metrics"]["llm_provider"] == "gemini"
    assert report["metrics"]["llm_model"] == "gemini-3.5-flash"
    assert report["metrics"]["llm_error"] is None
    assert report["corrections"][0]["suggestion"] == "I'd like some water."


@pytest.mark.anyio
async def test_generate_report_falls_back_when_deepseek_key_missing() -> None:
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        REPORT_LLM_PROVIDER="deepseek",
        DEEPSEEK_API_KEY="",
        DEEPSEEK_REPORT_MODEL="deepseek-v4-flash",
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        await add_turn(client, session_id, "user", "Could I have pasta?")
        response = await client.post(f"/api/sessions/{session_id}/report")

    assert response.status_code == 201
    report = response.json()
    assert report["metrics"]["generation_mode"] == "rules"
    assert report["metrics"]["llm_provider"] == "deepseek"
    assert report["metrics"]["llm_model"] == "deepseek-v4-flash"
    assert report["metrics"]["llm_error"] == "DEEPSEEK_API_KEY is not configured"


@pytest.mark.anyio
async def test_advanced_report_uses_deepseek_pro_model(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        REPORT_LLM_PROVIDER="deepseek",
        DEEPSEEK_API_KEY="deepseek-test-key",
        DEEPSEEK_REPORT_MODEL="deepseek-v4-flash",
        DEEPSEEK_ADVANCED_REPORT_MODEL="deepseek-v4-pro",
    )

    async def fake_request_deepseek_report(*args: object, **kwargs: object) -> dict[str, object]:
        assert kwargs["model"] == "deepseek-v4-pro"
        assert kwargs["timeout_seconds"] == 90.0
        assert kwargs["max_tokens"] == 2400
        return {
            "summary": "进阶报告：表达礼貌度不错，建议继续优化请求句式。",
            "scores": {"overall": 89, "fluency": 84, "grammar": 90, "vocabulary": 88, "goal_completion": 92},
            "strengths": ["能够围绕点餐目标推进对话。"],
            "corrections": [
                {
                    "original": "I want water",
                    "suggestion": "I'd like some water.",
                    "reason": "服务场景里更礼貌自然。",
                    "severity": "low",
                }
            ],
            "drills": [
                {
                    "title": "进阶礼貌请求复练",
                    "prompt": "用 I'd like... 和 Could you recommend... 完成一次完整点餐。",
                    "target_expression": "Could you recommend...",
                }
            ],
        }

    monkeypatch.setattr("app.report_llm.request_deepseek_report", fake_request_deepseek_report)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        await add_turn(client, session_id, "user", "Could I have pasta? I want water.")
        response = await client.post(f"/api/sessions/{session_id}/report", json={"report_level": "advanced"})

    assert response.status_code == 201
    report = response.json()
    assert report["summary"] == "进阶报告：表达礼貌度不错，建议继续优化请求句式。"
    assert report["metrics"]["report_level"] == "advanced"
    assert report["metrics"]["generation_mode"] == "llm"
    assert report["metrics"]["llm_provider"] == "deepseek"
    assert report["metrics"]["llm_model"] == "deepseek-v4-pro"


@pytest.mark.anyio
async def test_deepseek_report_retries_once_after_json_decode_error(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        REPORT_LLM_PROVIDER="deepseek",
        DEEPSEEK_API_KEY="deepseek-test-key",
        DEEPSEEK_REPORT_MODEL="deepseek-v4-flash",
    )
    calls = 0

    async def flaky_request_deepseek_report(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise json.JSONDecodeError("unterminated string", "{", 0)
        return {
            "summary": "重试后生成成功。",
            "scores": {"overall": 86, "fluency": 82, "grammar": 88, "vocabulary": 84, "goal_completion": 90},
            "strengths": ["能够完成点餐请求。"],
            "corrections": [
                {
                    "original": "I want water",
                    "suggestion": "I'd like some water.",
                    "reason": "更礼貌自然。",
                    "severity": "low",
                }
            ],
            "drills": [
                {
                    "title": "礼貌请求复练",
                    "prompt": "用 I'd like... 完成一次点餐。",
                    "target_expression": "I'd like...",
                }
            ],
        }

    monkeypatch.setattr("app.report_llm.request_deepseek_report", flaky_request_deepseek_report)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        await add_turn(client, session_id, "user", "Could I have pasta? I want water.")
        response = await client.post(f"/api/sessions/{session_id}/report")

    assert response.status_code == 201
    report = response.json()
    assert calls == 2
    assert report["summary"] == "重试后生成成功。"
    assert report["metrics"]["generation_mode"] == "llm"
    assert report["metrics"]["llm_error"] is None


@pytest.mark.anyio
async def test_default_report_provider_is_deepseek_with_rules_fallback() -> None:
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        _env_file=None,
        DEEPSEEK_API_KEY="",
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        await add_turn(client, session_id, "user", "Could I have pasta?")
        response = await client.post(f"/api/sessions/{session_id}/report")

    assert response.status_code == 201
    report = response.json()
    assert report["metrics"]["generation_mode"] == "rules"
    assert report["metrics"]["llm_provider"] == "deepseek"
    assert report["metrics"]["llm_model"] == "deepseek-v4-flash"
    assert report["metrics"]["llm_error"] == "DEEPSEEK_API_KEY is not configured"


@pytest.mark.anyio
async def test_get_report_rejects_missing_report() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        response = await client.get(f"/api/sessions/{session_id}/report")

    assert response.status_code == 404
    assert response.json()["detail"] == f"Report has not been generated for session_id: {session_id}"
