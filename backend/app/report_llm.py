import json
import re
from typing import Any

import httpx

from app.config import Settings
from app.models import ConversationTurn
from app.scenarios import Scenario


REPORT_SCORE_KEYS = {"overall", "fluency", "grammar", "vocabulary", "goal_completion"}


def compact_turns(turns: list[ConversationTurn]) -> list[dict[str, str]]:
    return [{"role": turn.role, "text": turn.text} for turn in turns]


def normalize_provider(provider: str) -> str:
    provider = provider.strip().lower()
    if provider in {"gemini", "deepseek"}:
        return provider
    return "rules"


def normalize_gemini_model_for_url(model: str) -> str:
    return model.removeprefix("models/")


def select_report_model(settings: Settings, provider: str, report_level: str) -> str | None:
    if provider == "gemini":
        return settings.gemini_report_model
    if provider == "deepseek" and report_level == "advanced":
        return settings.deepseek_advanced_report_model
    if provider == "deepseek":
        return settings.deepseek_report_model
    return None


def select_report_timeout(settings: Settings, report_level: str) -> float:
    if report_level == "advanced":
        return settings.advanced_report_llm_timeout_seconds
    return settings.report_llm_timeout_seconds


def select_report_max_tokens(settings: Settings, report_level: str) -> int:
    if report_level == "advanced":
        return settings.advanced_report_llm_max_tokens
    return settings.report_llm_max_tokens


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match is None:
            raise
        payload = json.loads(match.group(0))

    if not isinstance(payload, dict):
        raise ValueError("LLM response must be a JSON object")
    return payload


def build_report_prompt(
    scenario: Scenario,
    turns: list[ConversationTurn],
    rule_report: dict[str, Any],
) -> str:
    return json.dumps(
        {
            "task": (
                "Improve this English speaking practice report. Keep the JSON structure compact and actionable. "
                "Do not invent conversation facts. Keep corrections precise and useful for a learner."
            ),
            "scenario": {
                "id": scenario.id,
                "title": scenario.title,
                "role": scenario.role,
                "user_goal": scenario.user_goal,
                "target_expressions": scenario.target_expressions,
            },
            "transcript": compact_turns(turns),
            "rule_report": {
                "summary": rule_report["summary"],
                "scores": rule_report["scores"],
                "strengths": rule_report["strengths"],
                "corrections": rule_report["corrections"],
                "drills": rule_report["drills"],
                "metrics": rule_report["metrics"],
            },
            "output_schema": {
                "summary": "string, Chinese, one concise paragraph",
                "scores": {
                    "overall": "integer 0-100",
                    "fluency": "integer 0-100",
                    "grammar": "integer 0-100",
                    "vocabulary": "integer 0-100",
                    "goal_completion": "integer 0-100",
                },
                "strengths": ["1-3 Chinese strings"],
                "corrections": [
                    {
                        "original": "exact learner phrase",
                        "suggestion": "better English expression",
                        "reason": "short Chinese explanation",
                        "severity": "low|medium|high",
                    }
                ],
                "drills": [
                    {
                        "title": "Chinese title",
                        "prompt": "Chinese practice instruction",
                        "target_expression": "English target expression",
                    }
                ],
            },
        },
        ensure_ascii=False,
    )


def bounded_string(value: Any, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    return value[:max_length]


def bounded_string_list(value: Any, limit: int, max_length: int) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = [bounded_string(item, max_length) for item in value]
    cleaned = [item for item in items if item]
    return cleaned[:limit] or None


def merge_scores(rule_scores: dict[str, int], value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return rule_scores

    scores = dict(rule_scores)
    for key in REPORT_SCORE_KEYS:
        raw_score = value.get(key)
        if isinstance(raw_score, int | float):
            scores[key] = max(0, min(100, round(raw_score)))
    return scores


def merge_corrections(rule_corrections: list[dict[str, str]], value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return rule_corrections

    corrections: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        original = bounded_string(item.get("original"), 180)
        suggestion = bounded_string(item.get("suggestion"), 180)
        reason = bounded_string(item.get("reason"), 220)
        severity = item.get("severity")
        if severity not in {"low", "medium", "high"}:
            severity = "medium"
        if original and suggestion and reason:
            corrections.append(
                {
                    "original": original,
                    "suggestion": suggestion,
                    "reason": reason,
                    "severity": severity,
                }
            )
    return corrections[:5] or rule_corrections


def merge_drills(rule_drills: list[dict[str, str]], value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return rule_drills

    drills: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = bounded_string(item.get("title"), 80)
        prompt = bounded_string(item.get("prompt"), 240)
        target_expression = bounded_string(item.get("target_expression"), 120)
        if title and prompt and target_expression:
            drills.append(
                {
                    "title": title,
                    "prompt": prompt,
                    "target_expression": target_expression,
                }
            )
    return drills[:3] or rule_drills


def apply_llm_enhancement(
    rule_report: dict[str, Any],
    enhancement: dict[str, Any],
    provider: str,
    model: str,
) -> dict[str, Any]:
    report = dict(rule_report)
    metrics = dict(rule_report["metrics"])

    summary = bounded_string(enhancement.get("summary"), 520)
    if summary:
        report["summary"] = summary

    report["scores"] = merge_scores(rule_report["scores"], enhancement.get("scores"))
    strengths = bounded_string_list(enhancement.get("strengths"), limit=3, max_length=180)
    if strengths:
        report["strengths"] = strengths

    report["corrections"] = merge_corrections(rule_report["corrections"], enhancement.get("corrections"))
    report["drills"] = merge_drills(rule_report["drills"], enhancement.get("drills"))
    metrics.update(
        {
            "generation_mode": "llm",
            "llm_provider": provider,
            "llm_model": model,
            "llm_error": None,
        }
    )
    report["metrics"] = metrics
    return report


def mark_llm_fallback(rule_report: dict[str, Any], provider: str, model: str | None, error: str) -> dict[str, Any]:
    report = dict(rule_report)
    metrics = dict(rule_report["metrics"])
    metrics.update(
        {
            "generation_mode": "rules",
            "llm_provider": provider,
            "llm_model": model,
            "llm_error": error[:240],
        }
    )
    report["metrics"] = metrics
    return report


async def request_gemini_report(
    settings: Settings,
    scenario: Scenario,
    turns: list[ConversationTurn],
    rule_report: dict[str, Any],
    model: str,
    timeout_seconds: float,
    max_tokens: int,
) -> dict[str, Any]:
    prompt = build_report_prompt(scenario, turns, rule_report)
    normalized_model = normalize_gemini_model_for_url(model)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{normalized_model}:generateContent"
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.25,
            "responseMimeType": "application/json",
            "maxOutputTokens": max_tokens,
        },
    }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, params={"key": settings.gemini_api_key}, json=body)
    response.raise_for_status()
    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return extract_json_object(text)


async def request_deepseek_report(
    settings: Settings,
    scenario: Scenario,
    turns: list[ConversationTurn],
    rule_report: dict[str, Any],
    model: str,
    timeout_seconds: float,
    max_tokens: int,
) -> dict[str, Any]:
    prompt = build_report_prompt(scenario, turns, rule_report)
    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are an English speaking coach. Return only valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.25,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {settings.deepseek_api_key}"}

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, headers=headers, json=body)
    response.raise_for_status()
    data = response.json()
    text = data["choices"][0]["message"]["content"]
    return extract_json_object(text)


async def enhance_report_payload(
    settings: Settings,
    scenario: Scenario,
    turns: list[ConversationTurn],
    rule_report: dict[str, Any],
    report_level: str = "standard",
) -> dict[str, Any]:
    provider = normalize_provider(settings.report_llm_provider)
    if provider == "rules":
        return rule_report

    model = select_report_model(settings, provider, report_level)
    timeout_seconds = select_report_timeout(settings, report_level)
    max_tokens = select_report_max_tokens(settings, report_level)
    if provider == "gemini" and not settings.gemini_api_key:
        return mark_llm_fallback(rule_report, provider, model, "GEMINI_API_KEY is not configured")
    if provider == "deepseek" and not settings.deepseek_api_key:
        return mark_llm_fallback(rule_report, provider, model, "DEEPSEEK_API_KEY is not configured")

    async def request_provider_enhancement() -> dict[str, Any]:
        if provider == "gemini":
            return await request_gemini_report(
                settings,
                scenario,
                turns,
                rule_report,
                model=model or "",
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
            )
        return await request_deepseek_report(
            settings,
            scenario,
            turns,
            rule_report,
            model=model or "",
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
        )

    try:
        try:
            enhancement = await request_provider_enhancement()
        except (json.JSONDecodeError, ValueError):
            enhancement = await request_provider_enhancement()
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return mark_llm_fallback(rule_report, provider, model, exc.__class__.__name__)

    return apply_llm_enhancement(rule_report, enhancement, provider, model)
