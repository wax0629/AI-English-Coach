import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_app_settings, get_db
from app.models import PracticeSession
from app.pronunciation import (
    decode_audio_base64,
    normalize_audio_content_type,
    parse_azure_pronunciation_response,
    request_azure_pronunciation,
)
from app.schemas import PronunciationAssessmentResponse, PronunciationAssessRequest


router = APIRouter(prefix="/api/pronunciation", tags=["pronunciation"])


@router.post(
    "/assess",
    response_model=PronunciationAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assess_pronunciation(
    payload: PronunciationAssessRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> PronunciationAssessmentResponse:
    if not settings.azure_speech_key or not settings.azure_speech_region:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AZURE_SPEECH_KEY and AZURE_SPEECH_REGION are required",
        )

    practice_session = db.get(PracticeSession, payload.session_id)
    if practice_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown session_id: {payload.session_id}",
        )

    try:
        audio_bytes = decode_audio_base64(payload.audio_base64)
        content_type = normalize_audio_content_type(payload.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        azure_payload = await request_azure_pronunciation(
            settings=settings,
            reference_text=payload.reference_text,
            audio_bytes=audio_bytes,
            content_type=content_type,
            language=payload.language,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Azure pronunciation request failed ({exc.response.status_code})",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Azure pronunciation request failed: {exc.__class__.__name__}",
        ) from exc

    return PronunciationAssessmentResponse.model_validate(
        parse_azure_pronunciation_response(
            azure_payload,
            session_id=practice_session.id,
            reference_text=payload.reference_text,
        )
    )
