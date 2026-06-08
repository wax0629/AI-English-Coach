from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.learner_profile import clear_learner_memory, forget_learner_memory, to_learner_profile_response
from app.models import LearnerProfile
from app.schemas import ClearLearnerMemoryRequest, ForgetLearnerMemoryRequest, LearnerProfileResponse


router = APIRouter(prefix="/api/learner-profiles", tags=["learner-profiles"])


@router.get("/{user_id}", response_model=LearnerProfileResponse)
def get_learner_profile(user_id: str, db: Session = Depends(get_db)) -> LearnerProfileResponse:
    profile = db.get(LearnerProfile, user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Learner profile has not been generated for user_id: {user_id}",
        )
    return to_learner_profile_response(profile)


def _get_profile_or_404(user_id: str, db: Session) -> LearnerProfile:
    profile = db.get(LearnerProfile, user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Learner profile has not been generated for user_id: {user_id}",
        )
    return profile


@router.post("/{user_id}/memory/forget", response_model=LearnerProfileResponse)
def forget_memory_item(
    user_id: str,
    payload: ForgetLearnerMemoryRequest,
    db: Session = Depends(get_db),
) -> LearnerProfileResponse:
    profile = _get_profile_or_404(user_id, db)
    forget_learner_memory(
        profile,
        memory_type=payload.memory_type,
        label=payload.label,
        scenario_id=payload.scenario_id,
    )
    db.commit()
    db.refresh(profile)
    return to_learner_profile_response(profile)


@router.post("/{user_id}/memory/clear", response_model=LearnerProfileResponse)
def clear_memory(
    user_id: str,
    payload: ClearLearnerMemoryRequest,
    db: Session = Depends(get_db),
) -> LearnerProfileResponse:
    profile = _get_profile_or_404(user_id, db)
    clear_learner_memory(profile, scenario_id=payload.scenario_id)
    db.commit()
    db.refresh(profile)
    return to_learner_profile_response(profile)
