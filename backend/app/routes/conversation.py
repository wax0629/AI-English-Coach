from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import ConversationTurn, PracticeSession
from app.schemas import ConversationTurnResponse, CreateConversationTurnRequest


router = APIRouter(prefix="/api", tags=["conversation"])


def ensure_practice_session(db: Session, session_id: str) -> PracticeSession:
    practice_session = db.get(PracticeSession, session_id)
    if practice_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown session_id: {session_id}",
        )
    return practice_session


def to_turn_response(turn: ConversationTurn) -> ConversationTurnResponse:
    return ConversationTurnResponse(
        turn_id=turn.id,
        session_id=turn.session_id,
        role=turn.role,
        text=turn.text,
        started_at=turn.started_at,
        ended_at=turn.ended_at,
        created_at=turn.created_at,
    )


@router.post(
    "/conversation/turns",
    response_model=ConversationTurnResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation_turn(
    payload: CreateConversationTurnRequest,
    db: Session = Depends(get_db),
) -> ConversationTurnResponse:
    ensure_practice_session(db, payload.session_id)

    turn = ConversationTurn(
        id=str(uuid4()),
        session_id=payload.session_id,
        role=payload.role,
        text=payload.text,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        created_at=datetime.now(UTC),
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)
    return to_turn_response(turn)


@router.get("/sessions/{session_id}/turns", response_model=list[ConversationTurnResponse])
def list_conversation_turns(
    session_id: str,
    db: Session = Depends(get_db),
) -> list[ConversationTurnResponse]:
    ensure_practice_session(db, session_id)

    turns = db.scalars(
        select(ConversationTurn)
        .where(ConversationTurn.session_id == session_id)
        .order_by(ConversationTurn.created_at, ConversationTurn.id)
    ).all()
    return [to_turn_response(turn) for turn in turns]
