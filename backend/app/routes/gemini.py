from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_app_settings, get_db
from app.learner_profile import get_profile_context
from app.models import LearnerProfile, PracticeSession
from app.scenarios import Scenario, get_scenario
from app.schemas import CreateGeminiLiveTokenRequest, GeminiLiveTokenResponse


router = APIRouter(prefix="/api/gemini", tags=["gemini"])
GEMINI_API_VERSION = "v1alpha"
GEMINI_AUTH_TOKENS_PATH = "auth_tokens"


def build_gemini_live_instructions(scenario: Scenario, difficulty: str, profile_context: str = "") -> str:
    expressions = ", ".join(scenario.target_expressions)
    instructions = (
        "You are an AI English speaking coach running a realistic voice role-play. "
        f"The learner selected the scenario '{scenario.title}'. "
        f"You play the role of {scenario.role}. "
        f"The learner goal is: {scenario.user_goal} "
        f"Use CEFR difficulty {difficulty.upper()} and keep turns short enough for live speech. "
        "Coach with natural follow-up questions and encourage the learner to reuse these target expressions: "
        f"{expressions}."
    )
    if profile_context:
        instructions += f" {profile_context}"
    return instructions


def gemini_model_resource_name(model: str) -> str:
    if model.startswith("models/"):
        return model
    return f"models/{model}"


def build_gemini_live_token_config(
    settings: Settings,
    scenario: Scenario,
    difficulty: str,
    profile_context: str = "",
) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "uses": 1,
        "expireTime": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        "newSessionExpireTime": (now + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "bidiGenerateContentSetup": {
            "model": gemini_model_resource_name(settings.gemini_live_model),
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "temperature": 0.7,
            },
            "systemInstruction": {
                "parts": [
                    {
                        "text": build_gemini_live_instructions(scenario, difficulty, profile_context),
                    },
                ],
            },
            "inputAudioTranscription": {},
            "outputAudioTranscription": {},
        },
    }


async def request_gemini_live_token(
    settings: Settings,
    token_config: dict[str, Any],
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/{GEMINI_API_VERSION}/{GEMINI_AUTH_TOKENS_PATH}",
                params={"key": settings.gemini_api_key},
                json=token_config,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini Live token request failed: {exc.__class__.__name__}",
        ) from exc

    if response.status_code >= 400:
        error_message = "Gemini Live token request failed"
        try:
            error_payload = response.json()
            error_message = error_payload.get("error", {}).get("message", error_message)
        except ValueError:
            if response.text:
                error_message = response.text[:240]

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini Live token request failed ({response.status_code}): {error_message}",
        )
    return response.json()


@router.post(
    "/live-token",
    response_model=GeminiLiveTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_gemini_live_token(
    payload: CreateGeminiLiveTokenRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> GeminiLiveTokenResponse:
    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GEMINI_API_KEY is not configured",
        )

    practice_session = db.get(PracticeSession, payload.session_id)
    if practice_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown session_id: {payload.session_id}",
        )

    scenario = get_scenario(practice_session.scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown scenario_id: {practice_session.scenario_id}",
        )

    token_config = build_gemini_live_token_config(
        settings=settings,
        scenario=scenario,
        difficulty=practice_session.difficulty,
        profile_context=get_profile_context(db.get(LearnerProfile, practice_session.user_id), practice_session.scenario_id),
    )
    gemini_response = await request_gemini_live_token(settings=settings, token_config=token_config)

    return GeminiLiveTokenResponse(
        session_id=practice_session.id,
        token=str(gemini_response["name"]),
        expire_time=gemini_response.get("expireTime"),
        new_session_expire_time=gemini_response.get("newSessionExpireTime"),
        model=settings.gemini_live_model,
        api_version=GEMINI_API_VERSION,
    )
