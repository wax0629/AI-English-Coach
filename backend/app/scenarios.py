from typing import Literal

from pydantic import BaseModel


Difficulty = Literal["a2", "b1", "b2"]


class Scenario(BaseModel):
    id: str
    title: str
    subtitle: str
    role: str
    user_goal: str
    default_difficulty: Difficulty
    target_expressions: list[str]
    accent_color: str


SCENARIOS: dict[str, Scenario] = {
    "interview": Scenario(
        id="interview",
        title="求职面试",
        subtitle="讲清楚你的经历和优势",
        role="Hiring Manager",
        user_goal="Answer behavioral interview questions clearly and confidently.",
        default_difficulty="b1",
        target_expressions=[
            "I was responsible for...",
            "One challenge I faced was...",
            "The result was...",
        ],
        accent_color="#18A999",
    ),
    "restaurant": Scenario(
        id="restaurant",
        title="餐厅点餐",
        subtitle="自然完成点餐、改需求和结账",
        role="Restaurant Server",
        user_goal="Order food, clarify preferences, and ask polite follow-up questions.",
        default_difficulty="a2",
        target_expressions=[
            "Could I have...",
            "Is it possible to...",
            "Could you recommend...",
        ],
        accent_color="#FF6B5A",
    ),
    "meeting": Scenario(
        id="meeting",
        title="商务会议",
        subtitle="表达观点并回应追问",
        role="Project Lead",
        user_goal="Share opinions, support ideas, and respond to challenges in a meeting.",
        default_difficulty="b2",
        target_expressions=[
            "From my perspective...",
            "The main reason is...",
            "I would suggest...",
        ],
        accent_color="#4D8DFF",
    ),
}


def list_scenarios() -> list[Scenario]:
    return list(SCENARIOS.values())


def get_scenario(scenario_id: str) -> Scenario | None:
    return SCENARIOS.get(scenario_id)
