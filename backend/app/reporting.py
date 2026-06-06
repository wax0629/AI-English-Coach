import re
from dataclasses import dataclass
from typing import Any

from app.models import ConversationTurn, PracticeSession
from app.scenarios import Scenario


WORD_PATTERN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
FILLER_WORDS = {"um", "uh", "er", "like"}


@dataclass(frozen=True)
class CorrectionRule:
    pattern: re.Pattern[str]
    suggestion: str
    reason: str
    severity: str = "medium"


CORRECTION_RULES = [
    CorrectionRule(
        pattern=re.compile(r"\bi am agree\b", re.IGNORECASE),
        suggestion="I agree.",
        reason="'Agree' is already a verb, so it does not need 'am'.",
    ),
    CorrectionRule(
        pattern=re.compile(r"\bi responsible for\b", re.IGNORECASE),
        suggestion="I was responsible for...",
        reason="Use 'was responsible for' when describing a past responsibility.",
    ),
    CorrectionRule(
        pattern=re.compile(r"\bi have a experience\b", re.IGNORECASE),
        suggestion="I have experience...",
        reason="'Experience' is usually uncountable in this context.",
    ),
    CorrectionRule(
        pattern=re.compile(r"\bcan you recommend me\b", re.IGNORECASE),
        suggestion="Could you recommend...",
        reason="Use 'recommend something to me' or simply 'recommend something'.",
    ),
    CorrectionRule(
        pattern=re.compile(r"\bi want\b", re.IGNORECASE),
        suggestion="I'd like...",
        reason="'I'd like' sounds more polite in service conversations.",
        severity="low",
    ),
]


def normalize_text(text: str) -> str:
    words = WORD_PATTERN.findall(text.lower())
    return " ".join(words)


def count_words(text: str) -> int:
    return len(WORD_PATTERN.findall(text))


def clamp_score(value: float) -> int:
    return max(0, min(100, round(value)))


def find_target_expression_hits(transcript: str, scenario: Scenario) -> list[str]:
    normalized_transcript = normalize_text(transcript)
    hits: list[str] = []
    for expression in scenario.target_expressions:
        if normalize_text(expression) in normalized_transcript:
            hits.append(expression)
    return hits


def build_corrections(user_turns: list[ConversationTurn]) -> list[dict[str, str]]:
    corrections: list[dict[str, str]] = []
    seen_originals: set[str] = set()
    for turn in user_turns:
        for rule in CORRECTION_RULES:
            match = rule.pattern.search(turn.text)
            if match is None:
                continue

            original = match.group(0)
            if original.lower() in seen_originals:
                continue

            seen_originals.add(original.lower())
            corrections.append(
                {
                    "original": original,
                    "suggestion": rule.suggestion,
                    "reason": rule.reason,
                    "severity": rule.severity,
                }
            )
    return corrections[:5]


def build_scores(
    user_turns: list[ConversationTurn],
    target_hits: list[str],
    target_total: int,
    corrections: list[dict[str, str]],
) -> dict[str, int]:
    word_counts = [count_words(turn.text) for turn in user_turns]
    word_count = sum(word_counts)
    average_words = word_count / max(len(user_turns), 1)
    filler_count = sum(1 for turn in user_turns for word in WORD_PATTERN.findall(turn.text.lower()) if word in FILLER_WORDS)
    target_ratio = len(target_hits) / max(target_total, 1)

    fluency = clamp_score(62 + min(22, average_words * 1.8) - min(16, filler_count * 3))
    grammar = clamp_score(90 - len(corrections) * 8)
    vocabulary = clamp_score(58 + target_ratio * 28 + min(14, len(set(normalize_text(" ".join(turn.text for turn in user_turns)).split())) * 0.45))
    goal_completion = clamp_score(50 + target_ratio * 36 + min(14, len(user_turns) * 4))
    overall = clamp_score(fluency * 0.28 + grammar * 0.28 + vocabulary * 0.22 + goal_completion * 0.22)

    return {
        "overall": overall,
        "fluency": fluency,
        "grammar": grammar,
        "vocabulary": vocabulary,
        "goal_completion": goal_completion,
    }


def build_badges(scores: dict[str, int], target_hits: list[str], user_turn_count: int) -> list[str]:
    badges: list[str] = []
    if target_hits:
        badges.append("目标表达捕手")
    if scores["grammar"] >= 82:
        badges.append("语法稳定输出")
    if scores["fluency"] >= 78:
        badges.append("连续表达达人")
    if user_turn_count >= 3:
        badges.append("三轮对话完成")
    if scores["overall"] >= 85:
        badges.append("高能通关")
    return badges[:4] or ["完成首次复盘"]


def build_strengths(scores: dict[str, int], target_hits: list[str], average_words: float) -> list[str]:
    strengths: list[str] = []
    if target_hits:
        strengths.append(f"你主动使用了 {len(target_hits)} 个目标表达，场景迁移能力开始建立。")
    if scores["grammar"] >= 82:
        strengths.append("整体语法稳定，句子主干清楚，适合继续提高表达自然度。")
    if average_words >= 8:
        strengths.append("单轮回答长度足够，已经能支撑真实对话里的追问。")
    if scores["goal_completion"] >= 75:
        strengths.append("对话目标完成度较高，能围绕场景任务推进交流。")
    return strengths[:3] or ["你已经完成一次有效开口，下一步重点是把回答拉长并加入目标表达。"]


def build_drills(
    scenario: Scenario,
    missed_targets: list[str],
    corrections: list[dict[str, str]],
) -> list[dict[str, str]]:
    drills: list[dict[str, str]] = []
    for expression in missed_targets[:2]:
        drills.append(
            {
                "title": f"复练表达：{expression}",
                "prompt": f"用 '{expression}' 回答一次 {scenario.role} 的追问。",
                "target_expression": expression,
            }
        )

    for correction in corrections[:2]:
        drills.append(
            {
                "title": "纠错句复练",
                "prompt": f"把 '{correction['original']}' 改成更自然的说法，并补充一个完整句子。",
                "target_expression": correction["suggestion"],
            }
        )

    if not drills:
        drills.append(
            {
                "title": "升级回答长度",
                "prompt": f"用 2-3 句话完成一次 {scenario.role} 场景回应，包含原因或细节。",
                "target_expression": scenario.target_expressions[0],
            }
        )
    return drills[:3]


def build_report_payload(
    practice_session: PracticeSession,
    scenario: Scenario,
    turns: list[ConversationTurn],
    report_level: str = "standard",
) -> dict[str, Any]:
    user_turns = [turn for turn in turns if turn.role == "user"]
    assistant_turns = [turn for turn in turns if turn.role == "assistant"]
    transcript = " ".join(turn.text for turn in user_turns)
    target_hits = find_target_expression_hits(transcript, scenario)
    missed_targets = [expression for expression in scenario.target_expressions if expression not in target_hits]
    corrections = build_corrections(user_turns)
    scores = build_scores(user_turns, target_hits, len(scenario.target_expressions), corrections)

    word_count = sum(count_words(turn.text) for turn in user_turns)
    average_words = round(word_count / max(len(user_turns), 1), 1)
    metrics = {
        "report_level": report_level,
        "total_turns": len(turns),
        "user_turns": len(user_turns),
        "assistant_turns": len(assistant_turns),
        "word_count": word_count,
        "average_words_per_user_turn": average_words,
        "target_expression_hits": target_hits,
        "missed_target_expressions": missed_targets,
        "generation_mode": "rules",
        "llm_provider": "rules",
        "llm_model": None,
        "llm_error": None,
    }

    summary = (
        f"本次 {scenario.title} 练习完成了 {len(user_turns)} 轮英文输出，"
        f"综合得分 {scores['overall']}。"
        f"你已命中 {len(target_hits)}/{len(scenario.target_expressions)} 个目标表达，"
        "下一步建议优先复练未命中的关键句，并把回答扩展到包含原因或细节。"
    )

    return {
        "session_id": practice_session.id,
        "scenario_id": scenario.id,
        "difficulty": practice_session.difficulty,
        "summary": summary,
        "scores": scores,
        "metrics": metrics,
        "badges": build_badges(scores, target_hits, len(user_turns)),
        "strengths": build_strengths(scores, target_hits, average_words),
        "corrections": corrections,
        "drills": build_drills(scenario, missed_targets, corrections),
    }
