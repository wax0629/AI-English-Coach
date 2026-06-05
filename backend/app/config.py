from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_realtime_model: str = Field(default="gpt-realtime-mini", alias="OPENAI_REALTIME_MODEL")
    openai_realtime_voice: str = Field(default="marin", alias="OPENAI_REALTIME_VOICE")
    openai_realtime_transcription_model: str = Field(
        default="gpt-realtime-whisper",
        alias="OPENAI_REALTIME_TRANSCRIPTION_MODEL",
    )
    azure_speech_key: str = Field(default="", alias="AZURE_SPEECH_KEY")
    azure_speech_region: str = Field(default="", alias="AZURE_SPEECH_REGION")
    database_url: str = Field(default="sqlite:///./data/coach.db", alias="DATABASE_URL")
    backend_cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="BACKEND_CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
