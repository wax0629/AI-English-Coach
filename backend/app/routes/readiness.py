from fastapi import APIRouter, Depends

from app.config import Settings
from app.dependencies import get_app_settings
from app.schemas import ReadinessResponse


router = APIRouter(prefix="/api", tags=["readiness"])


def _service(configured: bool, label: str, ready_detail: str, missing_detail: str) -> dict[str, object]:
    return {
        "configured": configured,
        "label": label,
        "detail": ready_detail if configured else missing_detail,
    }


@router.get("/readiness", response_model=ReadinessResponse)
def get_readiness(settings: Settings = Depends(get_app_settings)) -> ReadinessResponse:
    report_provider = settings.report_llm_provider.strip().lower()
    report_ready = (
        (report_provider == "gemini" and bool(settings.gemini_api_key))
        or (report_provider == "deepseek" and bool(settings.deepseek_api_key))
        or report_provider == "rules"
    )
    report_label = {
        "gemini": "Gemini report",
        "deepseek": "DeepSeek report",
        "rules": "Rules fallback",
    }.get(report_provider, "Report LLM")

    return ReadinessResponse.model_validate(
        {
            "services": {
                "openai_realtime": _service(
                    bool(settings.openai_api_key),
                    "OpenAI Realtime",
                    "Realtime voice is configured.",
                    "OpenAI credential is missing; use Gemini Live or demo turns.",
                ),
                "gemini_live": _service(
                    bool(settings.gemini_api_key),
                    "Gemini Live",
                    "Gemini Live token flow is configured.",
                    "Gemini credential is missing; OpenAI voice and demo turns can still run.",
                ),
                "azure_pronunciation": _service(
                    bool(settings.azure_speech_key and settings.azure_speech_region),
                    "Azure pronunciation",
                    "Pronunciation assessment is configured.",
                    "Azure Speech credential or region is missing; drills will show setup guidance.",
                ),
                "report_llm": _service(
                    report_ready,
                    report_label,
                    "Report enhancement is configured.",
                    "Report LLM is not configured; rules fallback will generate reports.",
                ),
            }
        }
    )
