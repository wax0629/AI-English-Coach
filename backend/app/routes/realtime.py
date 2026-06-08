from hashlib import sha256
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_app_settings, get_db
from app.learner_profile import get_profile_context
from app.models import LearnerProfile, PracticeSession
from app.scenarios import Scenario, get_scenario
from app.schemas import CreateRealtimeClientSecretRequest, RealtimeClientSecretResponse
from app.skill_cards import build_session_skill_cards, skill_card_instruction


router = APIRouter(prefix="/api/realtime", tags=["realtime"])


def build_realtime_instructions(
    scenario: Scenario,
    difficulty: str,
    profile_context: str = "",
    skill_card_context: str = "",
) -> str:
    expressions = ", ".join(scenario.target_expressions)
    instructions = (
        "You are an AI English speaking coach running a realistic role-play. "
        f"The learner selected the scenario '{scenario.title}'. "
        f"You play the role of {scenario.role}. "
        f"The learner goal is: {scenario.user_goal} "
        f"Use CEFR difficulty {difficulty.upper()} and keep turns concise. "
        "Ask natural follow-up questions, correct only when the correction helps the next reply, "
        "and encourage the learner to reuse these target expressions: "
        f"{expressions}."
    )
    if profile_context:
        instructions += f" {profile_context}"
    if skill_card_context:
        instructions += f" {skill_card_context}"
    return instructions


def build_realtime_session_config(
    settings: Settings,
    scenario: Scenario,
    difficulty: str,
    profile_context: str = "",
    skill_card_context: str = "",
) -> dict[str, Any]:
    return {
        "session": {
            "type": "realtime",
            "model": settings.openai_realtime_model,
            "instructions": build_realtime_instructions(scenario, difficulty, profile_context, skill_card_context),
            "audio": {
                "input": {
                    "transcription": {
                        "model": settings.openai_realtime_transcription_model,
                        "language": "en",
                        "delay": "low",
                    },
                },
                "output": {
                    "voice": settings.openai_realtime_voice,
                },
            },
        },
    }


def build_safety_identifier(user_id: str) -> str:
    return sha256(user_id.encode("utf-8")).hexdigest()


async def request_openai_client_secret(
    settings: Settings,
    session_config: dict[str, Any],
    user_id: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/realtime/client_secrets",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
                "OpenAI-Safety-Identifier": build_safety_identifier(user_id),
            },
            json=session_config,
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI Realtime client secret request failed",
        )
    return response.json()


@router.post(
    "/client-secret",
    response_model=RealtimeClientSecretResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_realtime_client_secret(
    payload: CreateRealtimeClientSecretRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> RealtimeClientSecretResponse:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured",
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

    profile = db.get(LearnerProfile, practice_session.user_id)
    skill_cards = build_session_skill_cards(scenario, practice_session.difficulty, practice_session.id, profile)
    session_config = build_realtime_session_config(
        settings=settings,
        scenario=scenario,
        difficulty=practice_session.difficulty,
        profile_context=get_profile_context(profile, practice_session.scenario_id),
        skill_card_context=skill_card_instruction(skill_cards),
    )
    openai_response = await request_openai_client_secret(
        settings=settings,
        session_config=session_config,
        user_id=practice_session.user_id,
    )
    realtime_session = openai_response.get("session") or {}

    return RealtimeClientSecretResponse(
        session_id=practice_session.id,
        realtime_session_id=realtime_session.get("id"),
        client_secret=str(openai_response["value"]),
        expires_at=openai_response.get("expires_at"),
        model=settings.openai_realtime_model,
        voice=settings.openai_realtime_voice,
    )
