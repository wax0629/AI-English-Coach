import base64
import json
from typing import Any

import httpx

from app.config import Settings


AZURE_WAV_CONTENT_TYPE = "audio/wav; codecs=audio/pcm; samplerate=16000"
AZURE_OGG_CONTENT_TYPE = "audio/ogg; codecs=opus"
MAX_AUDIO_BYTES = 5 * 1024 * 1024


def normalize_audio_content_type(content_type: str) -> str:
    normalized = content_type.strip().lower()
    if normalized in {"audio/wav", "audio/wave", "audio/x-wav", AZURE_WAV_CONTENT_TYPE}:
        return AZURE_WAV_CONTENT_TYPE
    if normalized in {"audio/ogg", "audio/ogg; codecs=opus", "audio/ogg;codecs=opus"}:
        return AZURE_OGG_CONTENT_TYPE
    raise ValueError("Only WAV PCM or OGG OPUS audio is supported")


def decode_audio_base64(audio_base64: str) -> bytes:
    try:
        audio_bytes = base64.b64decode(audio_base64, validate=True)
    except ValueError as exc:
        raise ValueError("audio_base64 must be valid base64") from exc

    if not audio_bytes:
        raise ValueError("audio_base64 cannot be empty")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValueError("audio_base64 is too large")
    return audio_bytes


def build_pronunciation_assessment_header(reference_text: str) -> str:
    config = {
        "ReferenceText": reference_text,
        "GradingSystem": "HundredMark",
        "Granularity": "Phoneme",
        "Dimension": "Comprehensive",
        "EnableMiscue": True,
        "EnableProsodyAssessment": True,
    }
    payload = json.dumps(config, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(payload).decode("ascii")


def _score(value: object, default: int = 0) -> int:
    if isinstance(value, (int, float)):
        return max(0, min(100, round(value)))
    return default


def _feedback_level(pronunciation_score: int) -> str:
    if pronunciation_score >= 90:
        return "excellent"
    if pronunciation_score >= 75:
        return "good"
    if pronunciation_score >= 60:
        return "needs_focus"
    return "retry"


def _feedback_message(level: str) -> str:
    return {
        "excellent": "发音稳定自然，可以挑战更长句。",
        "good": "整体不错，重点打磨低分单词会更稳。",
        "needs_focus": "句子已完成，建议放慢语速并复练标记单词。",
        "no_speech": "未识别到有效英文语音，请确认麦克风权限并靠近麦克风重录。",
        "retry": "先分段慢读，再重新录一次会更有效。",
    }[level]


def _looks_like_no_speech(recognized_text: str, pronunciation_score: int) -> bool:
    cleaned = recognized_text.strip()
    return pronunciation_score == 0 and cleaned in {"", ".", "..."}


def parse_azure_pronunciation_response(
    azure_payload: dict[str, Any],
    session_id: str,
    reference_text: str,
) -> dict[str, Any]:
    nbest = azure_payload.get("NBest")
    best_result = nbest[0] if isinstance(nbest, list) and nbest else {}
    assessment = best_result.get("PronunciationAssessment") if isinstance(best_result, dict) else {}
    assessment = assessment if isinstance(assessment, dict) else {}

    pronunciation_score = _score(assessment.get("PronScore"))
    recognized_text = str(
        best_result.get("Display")
        or best_result.get("DisplayText")
        or azure_payload.get("DisplayText")
        or ""
    )
    scores = {
        "pronunciation": pronunciation_score,
        "accuracy": _score(assessment.get("AccuracyScore")),
        "fluency": _score(assessment.get("FluencyScore")),
        "completeness": _score(assessment.get("CompletenessScore")),
        "prosody": _score(assessment.get("ProsodyScore")),
    }
    words: list[dict[str, object]] = []
    for word in best_result.get("Words", []) if isinstance(best_result, dict) else []:
        if not isinstance(word, dict):
            continue
        word_assessment = word.get("PronunciationAssessment")
        word_assessment = word_assessment if isinstance(word_assessment, dict) else {}
        words.append(
            {
                "word": str(word.get("Word", "")),
                "accuracy": _score(word_assessment.get("AccuracyScore")),
                "error_type": str(word_assessment.get("ErrorType", "None")),
            }
        )

    level = "no_speech" if _looks_like_no_speech(recognized_text, pronunciation_score) else _feedback_level(pronunciation_score)
    return {
        "session_id": session_id,
        "reference_text": reference_text,
        "recognized_text": recognized_text,
        "scores": scores,
        "words": words,
        "feedback": {
            "level": level,
            "message": _feedback_message(level),
        },
    }


async def request_azure_pronunciation(
    settings: Settings,
    reference_text: str,
    audio_bytes: bytes,
    content_type: str,
    language: str,
) -> dict[str, Any]:
    endpoint = (
        f"https://{settings.azure_speech_region}.stt.speech.microsoft.com/"
        "speech/recognition/conversation/cognitiveservices/v1"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": settings.azure_speech_key,
        "Pronunciation-Assessment": build_pronunciation_assessment_header(reference_text),
        "Content-Type": content_type,
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            endpoint,
            params={"language": language, "format": "detailed"},
            headers=headers,
            content=audio_bytes,
        )
    response.raise_for_status()
    return response.json()
