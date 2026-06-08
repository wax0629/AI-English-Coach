from hashlib import sha256
from typing import Any

from app.models import LearnerProfile
from app.scenarios import Scenario


SKILL_CARD_POOLS: dict[str, list[dict[str, str]]] = {
    "interview": [
        {
            "expression": "I was responsible for...",
            "prompt": "用它说明你承担过的具体职责。",
            "hint": "适合回答经历、职责和项目范围。",
        },
        {
            "expression": "One challenge I faced was...",
            "prompt": "用它自然引出一次挑战和解决方式。",
            "hint": "适合行为面试里的 STAR 回答。",
        },
        {
            "expression": "The result was...",
            "prompt": "用它把你的行动落到结果和影响上。",
            "hint": "适合展示成果和量化影响。",
        },
        {
            "expression": "I learned how to...",
            "prompt": "用它补充你从经历中获得的成长。",
            "hint": "适合让回答更有反思感。",
        },
        {
            "expression": "I collaborated with...",
            "prompt": "用它说明你和谁合作以及如何推进。",
            "hint": "适合强调沟通和团队协作。",
        },
        {
            "expression": "I would handle it by...",
            "prompt": "用它回答假设型问题并给出行动方案。",
            "hint": "适合回答冲突、压力和突发问题。",
        },
    ],
    "restaurant": [
        {
            "expression": "Could I have...",
            "prompt": "用它礼貌地点一道菜或饮品。",
            "hint": "适合开口点单。",
        },
        {
            "expression": "Is it possible to...",
            "prompt": "用它提出换配料、去冰或少辣等要求。",
            "hint": "适合表达特殊需求。",
        },
        {
            "expression": "Could you recommend...",
            "prompt": "用它请服务员推荐菜品或饮品。",
            "hint": "适合不知道点什么的时候。",
        },
        {
            "expression": "Could we get the check?",
            "prompt": "用它自然地提出结账。",
            "hint": "适合对话收尾。",
        },
        {
            "expression": "Can I make that decaf?",
            "prompt": "用它修改饮品细节。",
            "hint": "适合咖啡、茶和饮料点单。",
        },
        {
            "expression": "Does this come with...",
            "prompt": "用它询问套餐或配菜内容。",
            "hint": "适合确认菜品包含什么。",
        },
    ],
    "meeting": [
        {
            "expression": "From my perspective...",
            "prompt": "用它清晰表达你的观点。",
            "hint": "适合开启观点陈述。",
        },
        {
            "expression": "The main reason is...",
            "prompt": "用它解释判断背后的核心理由。",
            "hint": "适合让观点更有逻辑。",
        },
        {
            "expression": "I would suggest...",
            "prompt": "用它提出可执行建议。",
            "hint": "适合推进会议结论。",
        },
        {
            "expression": "Could we align on...",
            "prompt": "用它推动团队确认一个共识。",
            "hint": "适合会议中控节奏。",
        },
        {
            "expression": "One possible risk is...",
            "prompt": "用它补充风险意识。",
            "hint": "适合讨论方案和优先级。",
        },
        {
            "expression": "The next step could be...",
            "prompt": "用它把讨论落到下一步行动。",
            "hint": "适合会议结束前总结。",
        },
    ],
}


def _normalized(value: str) -> str:
    return " ".join(value.lower().replace("...", "").strip().split())


def _ranked_pool(pool: list[dict[str, str]], seed: str) -> list[dict[str, str]]:
    return sorted(pool, key=lambda item: sha256(f"{seed}:{item['expression']}".encode("utf-8")).hexdigest())


def _memory_candidates(profile: LearnerProfile | None, scenario_id: str) -> list[dict[str, str]]:
    if profile is None:
        return []

    candidates: list[dict[str, str]] = []
    for expression in sorted(
        list(profile.missed_expressions or []),
        key=lambda item: (-int(item.get("count", 0)), item.get("expression", "")),
    ):
        if expression.get("scenario_id") != scenario_id:
            continue
        candidates.append(
            {
                "expression": str(expression["expression"]),
                "prompt": "本轮优先补回这张上次没命中的表达卡。",
                "hint": "来自 Coach Memory。",
            }
        )

    for correction in sorted(
        list(profile.recurring_corrections or []),
        key=lambda item: (-int((item.get("scenario_counts") or {}).get(scenario_id, 0)), item.get("suggestion", "")),
    ):
        scenario_count = int((correction.get("scenario_counts") or {}).get(scenario_id, 0))
        if scenario_count <= 0:
            continue
        candidates.append(
            {
                "expression": str(correction["suggestion"]),
                "prompt": "本轮把这条高频修正真正说出来。",
                "hint": "来自 Coach Memory。",
            }
        )
    return candidates


def build_session_skill_cards(
    scenario: Scenario,
    difficulty: str,
    session_id: str,
    profile: LearnerProfile | None = None,
) -> list[dict[str, Any]]:
    pool = SKILL_CARD_POOLS.get(scenario.id, [])
    # Keep one memory-driven card, then fill with fresh scenario phrases so the round still feels newly drawn.
    memory_candidates = _memory_candidates(profile, scenario.id)[:1]
    candidates = [
        *memory_candidates,
        *_ranked_pool(pool, f"{session_id}:{difficulty}"),
        *[
            {
                "expression": expression,
                "prompt": "用这张卡完成一次当前场景里的自然回应。",
                "hint": "场景核心表达。",
            }
            for expression in scenario.target_expressions
        ],
    ]

    cards: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        expression = candidate["expression"].strip()
        key = _normalized(expression)
        if not expression or key in seen:
            continue
        seen.add(key)
        source = "memory" if candidate in memory_candidates else "scenario_pool"
        cards.append(
            {
                "id": f"{scenario.id}-{len(cards) + 1}-{sha256(f'{session_id}:{expression}'.encode('utf-8')).hexdigest()[:8]}",
                "scenario_id": scenario.id,
                "expression": expression,
                "prompt": candidate["prompt"],
                "hint": candidate["hint"],
                "source": source,
            }
        )
        if len(cards) == 3:
            break

    return cards


def skill_card_instruction(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return ""
    expressions = "; ".join(str(card["expression"]) for card in cards[:3])
    return (
        "This session has three dynamic skill cards. "
        f"Create natural chances for the learner to use: {expressions}. "
        "Do not force all cards in one reply; weave them into the role-play."
    )
