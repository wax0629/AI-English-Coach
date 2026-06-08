from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import LearnerProfile
from app.schemas import LearnerProfileResponse


LOW_SCORE_LABELS = {
    "fluency": "流利度",
    "grammar": "语法",
    "vocabulary": "词汇",
    "goal_completion": "目标完成",
}
MEMORY_RETENTION_PRACTICES = 4


def _now() -> datetime:
    return datetime.now(UTC)


def _merge_corrections(
    existing: list[dict[str, Any]],
    scenario_id: str,
    corrections: list[dict[str, str]],
    practice_index: int,
) -> list[dict[str, Any]]:
    by_suggestion = {item["suggestion"].lower(): dict(item) for item in existing}

    for correction in corrections:
        suggestion = correction["suggestion"]
        key = suggestion.lower()
        item = by_suggestion.get(key)
        if item is None:
            item = {
                "original": correction["original"],
                "suggestion": suggestion,
                "reason": correction["reason"],
                "severity": correction["severity"],
                "count": 0,
                "scenario_counts": {},
            }
        scenario_counts = dict(item.get("scenario_counts") or {})
        item["original"] = correction["original"]
        item["reason"] = correction["reason"]
        item["severity"] = correction["severity"]
        item["count"] = int(item.get("count", 0)) + 1
        item["last_seen_practice"] = practice_index
        scenario_counts[scenario_id] = int(scenario_counts.get(scenario_id, 0)) + 1
        item["scenario_counts"] = scenario_counts
        by_suggestion[key] = item

    return sorted(by_suggestion.values(), key=lambda item: (-int(item["count"]), item["suggestion"]))[:8]


def _merge_missed_expressions(
    existing: list[dict[str, Any]],
    scenario_id: str,
    missed_expressions: list[str],
    target_hits: list[str],
    practice_index: int,
) -> list[dict[str, Any]]:
    by_expression = {f"{item['scenario_id']}::{item['expression'].lower()}": dict(item) for item in existing}

    for expression in target_hits:
        by_expression.pop(f"{scenario_id}::{expression.lower()}", None)

    for expression in missed_expressions:
        key = f"{scenario_id}::{expression.lower()}"
        item = by_expression.get(key)
        if item is None:
            item = {"expression": expression, "scenario_id": scenario_id, "count": 0}
        item["count"] = int(item.get("count", 0)) + 1
        item["last_seen_practice"] = practice_index
        by_expression[key] = item

    return sorted(by_expression.values(), key=lambda item: (-int(item["count"]), item["expression"]))[:8]


def _prune_stale_items(items: list[dict[str, Any]], practice_index: int) -> list[dict[str, Any]]:
    pruned: list[dict[str, Any]] = []
    for item in items:
        last_seen = int(item.get("last_seen_practice", practice_index))
        if practice_index - last_seen <= MEMORY_RETENTION_PRACTICES:
            pruned.append(item)
    return pruned


def _score_focus_areas(scores: dict[str, int]) -> list[dict[str, Any]]:
    focus: list[dict[str, Any]] = []
    for key, label in LOW_SCORE_LABELS.items():
        score = scores.get(key, 100)
        if score >= 72:
            continue
        focus.append(
            {
                "category": "score",
                "label": f"{label}拉升",
                "detail": f"{label}得分 {score}，下次练习需要更明确地补强。",
                "count": 1,
            }
        )
    return focus


def _build_focus_areas(
    corrections: list[dict[str, Any]],
    missed_expressions: list[dict[str, Any]],
    scores: dict[str, int],
) -> list[dict[str, Any]]:
    focus: list[dict[str, Any]] = []

    for correction in corrections[:2]:
        focus.append(
            {
                "category": "correction",
                "label": correction["suggestion"],
                "detail": correction["reason"],
                "count": int(correction["count"]),
                "scenario_counts": dict(correction.get("scenario_counts") or {}),
            }
        )

    for expression in missed_expressions[:2]:
        focus.append(
            {
                "category": "target_expression",
                "label": expression["expression"],
                "detail": "这类目标表达还没有稳定迁移到真实回答里。",
                "count": int(expression["count"]),
                "scenario_id": expression["scenario_id"],
            }
        )

    focus.extend(_score_focus_areas(scores))
    return focus[:4] or [
        {
            "category": "score",
            "label": "回答长度升级",
            "detail": "下一次尝试用原因、例子或结果把回答拉长。",
            "count": 1,
        }
    ]


def build_coach_note(focus_areas: list[dict[str, Any]]) -> str:
    if not focus_areas:
        return "当前没有需要持续提醒的弱点，下一轮会重新观察你的表达。"
    primary = focus_areas[0]
    labels = "；".join(item["label"] for item in focus_areas[:2])
    if primary["category"] == "correction":
        return f"下次练习优先提醒学习者使用：{labels}。"
    if primary["category"] == "target_expression":
        return f"下次练习优先引导学习者说出目标表达：{labels}。"
    return f"下次练习优先关注：{labels}。"


def _focus_areas_from_memory(
    corrections: list[dict[str, Any]],
    missed_expressions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    focus: list[dict[str, Any]] = []
    for correction in corrections[:2]:
        focus.append(
            {
                "category": "correction",
                "label": correction["suggestion"],
                "detail": correction["reason"],
                "count": int(correction["count"]),
                "scenario_counts": dict(correction.get("scenario_counts") or {}),
            }
        )
    for expression in missed_expressions[:2]:
        focus.append(
            {
                "category": "target_expression",
                "label": expression["expression"],
                "detail": "这类目标表达还没有稳定迁移到真实回答里。",
                "count": int(expression["count"]),
                "scenario_id": expression["scenario_id"],
            }
        )
    return focus[:4]


def _has_multiple_scenarios(scenario_counts: dict[str, int]) -> bool:
    return sum(1 for count in scenario_counts.values() if int(count) > 0) > 1


def _scenario_memory_items(profile: LearnerProfile, scenario_id: str) -> list[dict[str, Any]]:
    corrections = [
        {
            "count": int((correction.get("scenario_counts") or {}).get(scenario_id, 0)),
            "label": correction["suggestion"],
        }
        for correction in list(profile.recurring_corrections or [])
    ]
    missed_expressions = [
        {
            "count": int(expression["count"]),
            "label": expression["expression"],
        }
        for expression in list(profile.missed_expressions or [])
        if expression.get("scenario_id") == scenario_id
    ]
    items = [item for item in [*corrections, *missed_expressions] if item["count"] > 0]
    return _dedupe_memory_items(items)


def _cross_scenario_memory_items(profile: LearnerProfile) -> list[dict[str, Any]]:
    items = [
        {
            "count": int(correction["count"]),
            "label": correction["suggestion"],
        }
        for correction in list(profile.recurring_corrections or [])
        if _has_multiple_scenarios(dict(correction.get("scenario_counts") or {}))
    ]
    return _dedupe_memory_items(items)


def _dedupe_memory_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda value: (-int(value["count"]), value["label"])):
        key = item["label"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _memory_labels(items: list[dict[str, Any]]) -> str:
    return "; ".join(item["label"] for item in items[:3])


def to_learner_profile_response(profile: LearnerProfile) -> LearnerProfileResponse:
    return LearnerProfileResponse(
        user_id=profile.user_id,
        practice_count=profile.practice_count,
        updated_at=profile.updated_at,
        focus_areas=profile.focus_areas,
        recurring_corrections=profile.recurring_corrections,
        missed_expressions=profile.missed_expressions,
        coach_note=profile.coach_note,
    )


def get_profile_context(profile: LearnerProfile | None, scenario_id: str | None = None) -> str:
    if profile is None or not profile.focus_areas:
        return ""

    if scenario_id:
        scene_items = _scenario_memory_items(profile, scenario_id)
        if scene_items:
            return (
                "Learner memory: "
                f"Prioritize current-scenario focus areas: {_memory_labels(scene_items)}. "
                "Weave these into natural follow-up questions without interrupting every answer."
            )

        global_items = _cross_scenario_memory_items(profile)
        if global_items:
            return (
                "Learner memory: "
                f"No scenario-specific memory yet; reuse cross-scenario weaknesses: {_memory_labels(global_items)}. "
                "Weave these into natural follow-up questions without interrupting every answer."
            )

        return ""

    focus = "; ".join(item["label"] for item in profile.focus_areas[:3])
    return (
        "Learner memory: "
        f"{profile.coach_note} "
        f"Known focus areas: {focus}. "
        "Weave these into natural follow-up questions without interrupting every answer."
    )


def update_learner_profile_from_report(
    db: Session,
    user_id: str,
    report_payload: dict[str, Any],
    updated_at: datetime | None = None,
) -> LearnerProfile:
    profile = db.get(LearnerProfile, user_id)
    updated_at = updated_at or _now()

    if profile is None:
        profile = LearnerProfile(
            user_id=user_id,
            practice_count=0,
            focus_areas=[],
            recurring_corrections=[],
            missed_expressions=[],
            processed_session_ids=[],
            coach_note="完成一次练习后会生成个性化弱点记忆。",
            updated_at=updated_at,
        )
        db.add(profile)

    session_id = str(report_payload["session_id"])
    processed_session_ids = list(profile.processed_session_ids or [])
    if session_id in processed_session_ids:
        profile.updated_at = updated_at
        return profile

    practice_index = profile.practice_count + 1
    recurring_corrections = _merge_corrections(
        list(profile.recurring_corrections or []),
        str(report_payload["scenario_id"]),
        list(report_payload.get("corrections", [])),
        practice_index,
    )
    missed_expressions = _merge_missed_expressions(
        list(profile.missed_expressions or []),
        str(report_payload["scenario_id"]),
        list(report_payload.get("metrics", {}).get("missed_target_expressions", [])),
        list(report_payload.get("metrics", {}).get("target_expression_hits", [])),
        practice_index,
    )
    recurring_corrections = _prune_stale_items(recurring_corrections, practice_index)
    missed_expressions = _prune_stale_items(missed_expressions, practice_index)
    focus_areas = _build_focus_areas(
        recurring_corrections,
        missed_expressions,
        dict(report_payload.get("scores", {})),
    )

    processed_session_ids.append(session_id)
    profile.practice_count += 1
    profile.recurring_corrections = recurring_corrections
    profile.missed_expressions = missed_expressions
    profile.focus_areas = focus_areas
    profile.processed_session_ids = processed_session_ids[-20:]
    profile.coach_note = build_coach_note(focus_areas)
    profile.updated_at = updated_at
    return profile


def _remove_scenario_count(item: dict[str, Any], scenario_id: str) -> dict[str, Any] | None:
    scenario_counts = dict(item.get("scenario_counts") or {})
    if scenario_id not in scenario_counts:
        return item
    scenario_counts.pop(scenario_id, None)
    if not scenario_counts:
        return None
    next_item = dict(item)
    next_item["scenario_counts"] = scenario_counts
    next_item["count"] = sum(int(count) for count in scenario_counts.values())
    return next_item


def _refresh_profile_memory(profile: LearnerProfile, updated_at: datetime | None = None) -> LearnerProfile:
    profile.recurring_corrections = sorted(
        list(profile.recurring_corrections or []),
        key=lambda item: (-int(item.get("count", 0)), item.get("suggestion", "")),
    )[:8]
    profile.missed_expressions = sorted(
        list(profile.missed_expressions or []),
        key=lambda item: (-int(item.get("count", 0)), item.get("expression", "")),
    )[:8]
    profile.focus_areas = _focus_areas_from_memory(profile.recurring_corrections, profile.missed_expressions)
    profile.coach_note = build_coach_note(profile.focus_areas)
    profile.updated_at = updated_at or _now()
    return profile


def forget_learner_memory(
    profile: LearnerProfile,
    memory_type: str,
    label: str,
    scenario_id: str | None = None,
    updated_at: datetime | None = None,
) -> LearnerProfile:
    label_key = label.strip().lower()
    if memory_type in {"any", "correction"}:
        corrections: list[dict[str, Any]] = []
        for item in list(profile.recurring_corrections or []):
            if str(item.get("suggestion", "")).strip().lower() != label_key:
                corrections.append(item)
                continue
            if scenario_id:
                next_item = _remove_scenario_count(item, scenario_id)
                if next_item is not None:
                    corrections.append(next_item)
            # No scenario means the user wants the whole memory item gone.
        profile.recurring_corrections = corrections
    if memory_type in {"any", "target_expression"}:
        profile.missed_expressions = [
            item
            for item in list(profile.missed_expressions or [])
            if not (
                str(item.get("expression", "")).strip().lower() == label_key
                and (scenario_id is None or str(item.get("scenario_id")) == scenario_id)
            )
        ]

    return _refresh_profile_memory(profile, updated_at)


def clear_learner_memory(
    profile: LearnerProfile,
    scenario_id: str | None = None,
    updated_at: datetime | None = None,
) -> LearnerProfile:
    if scenario_id is None:
        profile.recurring_corrections = []
        profile.missed_expressions = []
        return _refresh_profile_memory(profile, updated_at)

    corrections: list[dict[str, Any]] = []
    for item in list(profile.recurring_corrections or []):
        next_item = _remove_scenario_count(item, scenario_id)
        if next_item is not None:
            corrections.append(next_item)
    profile.recurring_corrections = corrections
    profile.missed_expressions = [
        item for item in list(profile.missed_expressions or []) if str(item.get("scenario_id")) != scenario_id
    ]
    return _refresh_profile_memory(profile, updated_at)
