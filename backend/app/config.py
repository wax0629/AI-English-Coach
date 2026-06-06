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
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_live_model: str = Field(
        default="gemini-3.1-flash-live-preview",
        alias="GEMINI_LIVE_MODEL",
    )
    report_llm_provider: str = Field(default="deepseek", alias="REPORT_LLM_PROVIDER")
    gemini_report_model: str = Field(default="gemini-3.5-flash", alias="GEMINI_REPORT_MODEL")
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_report_model: str = Field(default="deepseek-v4-flash", alias="DEEPSEEK_REPORT_MODEL")
    deepseek_advanced_report_model: str = Field(
        default="deepseek-v4-pro",
        alias="DEEPSEEK_ADVANCED_REPORT_MODEL",
    )
    report_llm_timeout_seconds: float = Field(default=20.0, alias="REPORT_LLM_TIMEOUT_SECONDS")
    report_llm_max_tokens: int = Field(default=1600, alias="REPORT_LLM_MAX_TOKENS")
    advanced_report_llm_timeout_seconds: float = Field(
        default=90.0,
        alias="ADVANCED_REPORT_LLM_TIMEOUT_SECONDS",
    )
    advanced_report_llm_max_tokens: int = Field(default=2400, alias="ADVANCED_REPORT_LLM_MAX_TOKENS")
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
