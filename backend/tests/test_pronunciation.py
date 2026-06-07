import base64
import json

import httpx
import pytest

from app.config import Settings
from app.database import init_db
from app.dependencies import get_app_settings
from app.main import app
from app.pronunciation import build_pronunciation_assessment_header, parse_azure_pronunciation_response


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
        json={"scenario_id": "restaurant", "difficulty": "a2", "user_id": "demo"},
    )

    assert response.status_code == 201
    return str(response.json()["session_id"])


def test_build_pronunciation_assessment_header_contains_reference_text() -> None:
    header = build_pronunciation_assessment_header("Could I have some water?")
    decoded = json.loads(base64.b64decode(header).decode("utf-8"))

    assert decoded["ReferenceText"] == "Could I have some water?"
    assert decoded["GradingSystem"] == "HundredMark"
    assert decoded["Granularity"] == "Phoneme"
    assert decoded["EnableMiscue"] is True


def test_parse_azure_pronunciation_response_normalizes_scores_and_words() -> None:
    result = parse_azure_pronunciation_response(
        {
            "RecognitionStatus": "Success",
            "DisplayText": "Could I have some water?",
            "NBest": [
                {
                    "Display": "Could I have some water?",
                    "PronunciationAssessment": {
                        "PronScore": 86.4,
                        "AccuracyScore": 82.2,
                        "FluencyScore": 91.7,
                        "CompletenessScore": 88.1,
                        "ProsodyScore": 79.5,
                    },
                    "Words": [
                        {
                            "Word": "Could",
                            "PronunciationAssessment": {"AccuracyScore": 74.4, "ErrorType": "None"},
                        },
                        {
                            "Word": "water",
                            "PronunciationAssessment": {"AccuracyScore": 58.2, "ErrorType": "Mispronunciation"},
                        },
                    ],
                }
            ],
        },
        session_id="session-1",
        reference_text="Could I have some water?",
    )

    assert result["scores"] == {
        "pronunciation": 86,
        "accuracy": 82,
        "fluency": 92,
        "completeness": 88,
        "prosody": 80,
    }
    assert result["recognized_text"] == "Could I have some water?"
    assert result["words"][1] == {"word": "water", "accuracy": 58, "error_type": "Mispronunciation"}
    assert result["feedback"]["level"] == "good"


def test_parse_azure_pronunciation_response_reads_rest_flat_scores() -> None:
    result = parse_azure_pronunciation_response(
        {
            "RecognitionStatus": "Success",
            "DisplayText": "Good morning.",
            "NBest": [
                {
                    "Confidence": 0.98,
                    "Display": "Good morning.",
                    "AccuracyScore": 100.0,
                    "FluencyScore": 96.3,
                    "CompletenessScore": 100.0,
                    "ProsodyScore": 87.8,
                    "PronScore": 95.1,
                    "Words": [
                        {
                            "Word": "good",
                            "AccuracyScore": 100.0,
                            "ErrorType": "None",
                        },
                        {
                            "Word": "morning",
                            "AccuracyScore": 88.6,
                            "ErrorType": "None",
                        },
                    ],
                }
            ],
        },
        session_id="session-1",
        reference_text="Good morning.",
    )

    assert result["scores"] == {
        "pronunciation": 95,
        "accuracy": 100,
        "fluency": 96,
        "completeness": 100,
        "prosody": 88,
    }
    assert result["words"][1] == {"word": "morning", "accuracy": 89, "error_type": "None"}
    assert result["feedback"]["level"] == "excellent"


def test_parse_azure_pronunciation_response_marks_no_speech() -> None:
    result = parse_azure_pronunciation_response(
        {
            "RecognitionStatus": "Success",
            "NBest": [
                {
                    "Display": "",
                    "PronunciationAssessment": {
                        "PronScore": 0,
                        "AccuracyScore": 0,
                        "FluencyScore": 0,
                        "CompletenessScore": 0,
                        "ProsodyScore": 0,
                    },
                }
            ],
        },
        session_id="session-1",
        reference_text="Could I have a cappuccino, please?",
    )

    assert result["feedback"]["level"] == "no_speech"
    assert "未识别到有效英文语音" in result["feedback"]["message"]


def test_parse_azure_pronunciation_response_marks_assessment_unavailable() -> None:
    result = parse_azure_pronunciation_response(
        {
            "RecognitionStatus": "Success",
            "DisplayText": "Could I have a cappuccino please?",
            "NBest": [
                {
                    "Display": "Could I have a cappuccino please?",
                    "Words": [
                        {"Word": "Could"},
                        {"Word": "I"},
                        {"Word": "have"},
                        {"Word": "a"},
                        {"Word": "cappuccino"},
                        {"Word": "please"},
                    ],
                }
            ],
        },
        session_id="session-1",
        reference_text="Could I have a cappuccino, please?",
    )

    assert result["feedback"]["level"] == "assessment_unavailable"
    assert "没有返回发音评分" in result["feedback"]["message"]


@pytest.mark.anyio
async def test_pronunciation_assessment_requires_azure_config() -> None:
    app.dependency_overrides[get_app_settings] = lambda: Settings(AZURE_SPEECH_KEY="", AZURE_SPEECH_REGION="")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        response = await client.post(
            "/api/pronunciation/assess",
            json={
                "session_id": session_id,
                "reference_text": "Could I have some water?",
                "audio_base64": base64.b64encode(b"fake-wav").decode("ascii"),
            },
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "AZURE_SPEECH_KEY and AZURE_SPEECH_REGION are required"


@pytest.mark.anyio
async def test_pronunciation_assessment_rejects_unknown_session() -> None:
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        AZURE_SPEECH_KEY="azure-test-key",
        AZURE_SPEECH_REGION="eastus",
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/pronunciation/assess",
            json={
                "session_id": "missing-session",
                "reference_text": "Could I have some water?",
                "audio_base64": base64.b64encode(b"fake-wav").decode("ascii"),
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown session_id: missing-session"


@pytest.mark.anyio
async def test_pronunciation_assessment_rejects_invalid_audio_base64() -> None:
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        AZURE_SPEECH_KEY="azure-test-key",
        AZURE_SPEECH_REGION="eastus",
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        response = await client.post(
            "/api/pronunciation/assess",
            json={
                "session_id": session_id,
                "reference_text": "Could I have some water?",
                "audio_base64": "not-valid-base64",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "audio_base64 must be valid base64"


@pytest.mark.anyio
async def test_pronunciation_assessment_returns_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request: dict[str, object] = {}
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        AZURE_SPEECH_KEY="azure-test-key",
        AZURE_SPEECH_REGION="eastus",
    )

    async def fake_request_azure_pronunciation(
        settings: Settings,
        reference_text: str,
        audio_bytes: bytes,
        content_type: str,
        language: str,
    ) -> dict[str, object]:
        captured_request.update(
            {
                "reference_text": reference_text,
                "audio_bytes": audio_bytes,
                "content_type": content_type,
                "language": language,
                "region": settings.azure_speech_region,
            }
        )
        return {
            "RecognitionStatus": "Success",
            "DisplayText": "Could I have some water?",
            "NBest": [
                {
                    "PronunciationAssessment": {
                        "PronScore": 92.0,
                        "AccuracyScore": 90.0,
                        "FluencyScore": 95.0,
                        "CompletenessScore": 91.0,
                    },
                    "Words": [
                        {
                            "Word": "Could",
                            "PronunciationAssessment": {"AccuracyScore": 90.0, "ErrorType": "None"},
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr("app.routes.pronunciation.request_azure_pronunciation", fake_request_azure_pronunciation)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        response = await client.post(
            "/api/pronunciation/assess",
            json={
                "session_id": session_id,
                "reference_text": "Could I have some water?",
                "audio_base64": base64.b64encode(b"fake-wav").decode("ascii"),
                "content_type": "audio/wav",
                "language": "en-US",
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["reference_text"] == "Could I have some water?"
    assert payload["scores"]["pronunciation"] == 92
    assert payload["words"][0]["word"] == "Could"
    assert captured_request == {
        "reference_text": "Could I have some water?",
        "audio_bytes": b"fake-wav",
        "content_type": "audio/wav; codecs=audio/pcm; samplerate=16000",
        "language": "en-US",
        "region": "eastus",
    }


@pytest.mark.anyio
async def test_pronunciation_assessment_returns_no_speech_feedback(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        AZURE_SPEECH_KEY="azure-test-key",
        AZURE_SPEECH_REGION="eastus",
    )

    async def fake_request_azure_pronunciation(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "RecognitionStatus": "Success",
            "NBest": [
                {
                    "Display": "",
                    "PronunciationAssessment": {
                        "PronScore": 0,
                        "AccuracyScore": 0,
                        "FluencyScore": 0,
                        "CompletenessScore": 0,
                        "ProsodyScore": 0,
                    },
                }
            ],
        }

    monkeypatch.setattr("app.routes.pronunciation.request_azure_pronunciation", fake_request_azure_pronunciation)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        response = await client.post(
            "/api/pronunciation/assess",
            json={
                "session_id": session_id,
                "reference_text": "Could I have a cappuccino, please?",
                "audio_base64": base64.b64encode(b"fake-wav").decode("ascii"),
                "content_type": "audio/wav",
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["feedback"]["level"] == "no_speech"


@pytest.mark.anyio
async def test_pronunciation_assessment_returns_assessment_unavailable_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        AZURE_SPEECH_KEY="azure-test-key",
        AZURE_SPEECH_REGION="eastus",
    )

    async def fake_request_azure_pronunciation(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "RecognitionStatus": "Success",
            "DisplayText": "Could I have a cappuccino please?",
            "NBest": [
                {
                    "Display": "Could I have a cappuccino please?",
                    "Words": [
                        {"Word": "Could"},
                        {"Word": "I"},
                        {"Word": "have"},
                    ],
                }
            ],
        }

    monkeypatch.setattr("app.routes.pronunciation.request_azure_pronunciation", fake_request_azure_pronunciation)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = await create_practice_session(client)
        response = await client.post(
            "/api/pronunciation/assess",
            json={
                "session_id": session_id,
                "reference_text": "Could I have a cappuccino, please?",
                "audio_base64": base64.b64encode(b"fake-wav").decode("ascii"),
                "content_type": "audio/wav",
            },
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["feedback"]["level"] == "assessment_unavailable"
