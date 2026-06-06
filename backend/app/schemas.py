from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.scenarios import Difficulty


class ScenarioResponse(BaseModel):
    id: str
    title: str
    subtitle: str
    role: str
    user_goal: str
    default_difficulty: Difficulty
    target_expressions: list[str]
    accent_color: str


class CreateSessionRequest(BaseModel):
    scenario_id: str = Field(min_length=1)
    difficulty: Difficulty
    user_id: str = Field(default="demo", min_length=1, max_length=80)


class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    scenario: ScenarioResponse
    difficulty: Difficulty
    status: Literal["active", "finished"]
    created_at: datetime


class CreateRealtimeClientSecretRequest(BaseModel):
    session_id: str = Field(min_length=1)


class RealtimeClientSecretResponse(BaseModel):
    session_id: str
    realtime_session_id: str | None
    client_secret: str
    expires_at: int | None
    model: str
    voice: str


class CreateGeminiLiveTokenRequest(BaseModel):
    session_id: str = Field(min_length=1)


class GeminiLiveTokenResponse(BaseModel):
    session_id: str
    token: str
    expire_time: str | None
    new_session_expire_time: str | None
    model: str
    api_version: str


ConversationRole = Literal["user", "assistant"]


class CreateConversationTurnRequest(BaseModel):
    session_id: str = Field(min_length=1)
    role: ConversationRole
    text: str = Field(min_length=1)
    started_at: datetime | None = None
    ended_at: datetime | None = None


class ConversationTurnResponse(BaseModel):
    turn_id: str
    session_id: str
    role: ConversationRole
    text: str
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
