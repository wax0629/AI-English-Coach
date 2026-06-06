from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.dependencies import get_app_settings, get_db
from app.models import ConversationTurn, PracticeReport, PracticeSession
from app.report_llm import enhance_report_payload
from app.reporting import build_report_payload
from app.scenarios import get_scenario
from app.schemas import CreatePracticeReportRequest, PracticeReportResponse


router = APIRouter(prefix="/api", tags=["reports"])


def ensure_practice_session(db: Session, session_id: str) -> PracticeSession:
    practice_session = db.get(PracticeSession, session_id)
    if practice_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown session_id: {session_id}",
        )
    return practice_session


def list_session_turns(db: Session, session_id: str) -> list[ConversationTurn]:
    return list(
        db.scalars(
            select(ConversationTurn)
            .where(ConversationTurn.session_id == session_id)
            .order_by(ConversationTurn.created_at, ConversationTurn.id)
        ).all()
    )


def to_report_response(report: PracticeReport) -> PracticeReportResponse:
    return PracticeReportResponse(
        report_id=report.id,
        session_id=report.session_id,
        scenario_id=report.scenario_id,
        difficulty=report.difficulty,
        generated_at=report.generated_at,
        summary=report.summary,
        scores=report.scores,
        metrics=report.metrics,
        badges=report.badges,
        strengths=report.strengths,
        corrections=report.corrections,
        drills=report.drills,
    )


@router.post(
    "/sessions/{session_id}/report",
    response_model=PracticeReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_practice_report(
    session_id: str,
    request: CreatePracticeReportRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> PracticeReportResponse:
    practice_session = ensure_practice_session(db, session_id)
    scenario = get_scenario(practice_session.scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown scenario_id: {practice_session.scenario_id}",
        )

    turns = list_session_turns(db, session_id)
    if not any(turn.role == "user" for turn in turns):
        raise HTTPException(
            status_code=422,
            detail="At least one user turn is required to generate a report",
        )

    generated_at = datetime.now(UTC)
    report_level = request.report_level if request is not None else "standard"
    payload = build_report_payload(practice_session, scenario, turns, report_level=report_level)
    payload = await enhance_report_payload(settings, scenario, turns, payload, report_level=report_level)
    existing_report = db.scalar(select(PracticeReport).where(PracticeReport.session_id == session_id))

    if existing_report is None:
        report = PracticeReport(id=str(uuid4()), generated_at=generated_at, **payload)
        db.add(report)
    else:
        report = existing_report
        report.generated_at = generated_at
        for key, value in payload.items():
            setattr(report, key, value)

    practice_session.status = "finished"
    practice_session.finished_at = generated_at
    db.commit()
    db.refresh(report)
    return to_report_response(report)


@router.get("/sessions/{session_id}/report", response_model=PracticeReportResponse)
def get_practice_report(
    session_id: str,
    db: Session = Depends(get_db),
) -> PracticeReportResponse:
    ensure_practice_session(db, session_id)
    report = db.scalar(select(PracticeReport).where(PracticeReport.session_id == session_id))
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report has not been generated for session_id: {session_id}",
        )
    return to_report_response(report)
