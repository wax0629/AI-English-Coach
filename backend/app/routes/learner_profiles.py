from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.learner_profile import to_learner_profile_response
from app.models import LearnerProfile
from app.schemas import LearnerProfileResponse


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
