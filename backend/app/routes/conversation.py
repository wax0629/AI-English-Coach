from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import ConversationTurn, PracticeSession
from app.schemas import ConversationTurnResponse, CreateConversationTurnRequest, DemoConversationResponse


router = APIRouter(prefix="/api", tags=["conversation"])

DEMO_TURNS: dict[str, list[tuple[str, str]]] = {
    "interview": [
        ("assistant", "Welcome. Could you tell me about a project where you solved a difficult problem?"),
        ("user", "I was responsible for customer interviews in a product research project."),
        ("assistant", "What challenge did you face, and how did you handle it?"),
        ("user", "One challenge I faced was that users gave mixed feedback, so I grouped their needs and shared clear priorities."),
        ("assistant", "What was the result?"),
        ("user", "The result was that our team redesigned the onboarding flow and reduced confusion for new users."),
    ],
    "restaurant": [
        ("assistant", "Hi, welcome in. What would you like to order today?"),
        ("user", "Could I have a cappuccino, please?"),
        ("assistant", "Of course. Would you like it with regular milk or oat milk?"),
        ("user", "Is it possible to make it with oat milk?"),
        ("assistant", "Sure. Would you like anything to eat with that?"),
        ("user", "Could you recommend a dessert, please?"),
    ],
    "meeting": [
        ("assistant", "We need to decide whether to launch the new feature this week. What do you think?"),
        ("user", "From my perspective, launching this week is possible if we keep the scope small."),
        ("assistant", "What is the main reason for your suggestion?"),
        ("user", "The main reason is that users are waiting for the core workflow, not every advanced option."),
        ("assistant", "How would you reduce the risk?"),
        ("user", "I would suggest a limited rollout with daily feedback checks."),
    ],
}


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


def _list_turns(db: Session, session_id: str) -> list[ConversationTurn]:
    return db.scalars(
        select(ConversationTurn)
        .where(ConversationTurn.session_id == session_id)
        .order_by(ConversationTurn.created_at, ConversationTurn.id)
    ).all()


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

    turns = _list_turns(db, session_id)
    return [to_turn_response(turn) for turn in turns]


@router.post(
    "/sessions/{session_id}/demo-turns",
    response_model=DemoConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_demo_conversation_turns(
    session_id: str,
    db: Session = Depends(get_db),
) -> DemoConversationResponse:
    practice_session = ensure_practice_session(db, session_id)
    existing_turns = _list_turns(db, session_id)
    if existing_turns:
        return DemoConversationResponse(
            session_id=session_id,
            created=False,
            turns=[to_turn_response(turn) for turn in existing_turns],
        )

    now = datetime.now(UTC)
    turns = [
        ConversationTurn(
            id=str(uuid4()),
            session_id=session_id,
            role=role,
            text=text,
            started_at=None,
            ended_at=None,
            created_at=now,
        )
        for role, text in DEMO_TURNS.get(practice_session.scenario_id, DEMO_TURNS["interview"])
    ]
    db.add_all(turns)
    db.commit()

    stored_turns = _list_turns(db, session_id)
    return DemoConversationResponse(
        session_id=session_id,
        created=True,
        turns=[to_turn_response(turn) for turn in stored_turns],
    )
