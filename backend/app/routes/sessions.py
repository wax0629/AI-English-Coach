from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.learner_profile import to_learner_profile_response
from app.models import LearnerProfile, PracticeSession
from app.scenarios import get_scenario, list_scenarios
from app.schemas import CreateSessionRequest, ScenarioResponse, SessionResponse
from app.skill_cards import build_session_skill_cards


router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/scenarios", response_model=list[ScenarioResponse])
def get_scenarios() -> list[ScenarioResponse]:
    return [ScenarioResponse.model_validate(scenario.model_dump()) for scenario in list_scenarios()]


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(payload: CreateSessionRequest, db: Session = Depends(get_db)) -> SessionResponse:
    scenario = get_scenario(payload.scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown scenario_id: {payload.scenario_id}",
        )

    session = PracticeSession(
        id=str(uuid4()),
        user_id=payload.user_id,
        scenario_id=scenario.id,
        difficulty=payload.difficulty,
        status="active",
        created_at=datetime.now(UTC),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    profile = db.get(LearnerProfile, session.user_id)
    return SessionResponse(
        session_id=session.id,
        user_id=session.user_id,
        scenario=ScenarioResponse.model_validate(scenario.model_dump()),
        difficulty=payload.difficulty,
        status="active",
        created_at=session.created_at,
        learner_profile=to_learner_profile_response(profile) if profile else None,
        skill_cards=build_session_skill_cards(scenario, payload.difficulty, session.id, profile),
    )
