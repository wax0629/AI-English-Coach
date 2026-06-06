from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routes.conversation import router as conversation_router
from app.routes.gemini import router as gemini_router
from app.routes.realtime import router as realtime_router
from app.routes.sessions import router as sessions_router


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(
    title="AI English Coach API",
    version="0.1.0",
    description="Backend API for the AI English speaking coach MVP.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router)
app.include_router(realtime_router)
app.include_router(conversation_router)
app.include_router(gemini_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-english-coach"}
