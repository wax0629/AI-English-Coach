import { describe, expect, it } from "vitest";

import { buildSkillCardStates, type SessionSkillCard } from "./skill-cards";

const cards: SessionSkillCard[] = [
  {
    id: "restaurant-1",
    expression: "Could I have...",
    hint: "Ask for an item politely.",
    prompt: "Use it when ordering.",
    scenario_id: "restaurant",
    source: "scenario_pool",
  },
  {
    id: "restaurant-2",
    expression: "Is it possible to...",
    hint: "Ask about a change.",
    prompt: "Use it for special requests.",
    scenario_id: "restaurant",
    source: "scenario_pool",
  },
  {
    id: "restaurant-3",
    expression: "Could we get the check?",
    hint: "Ask to pay.",
    prompt: "Use it at the end.",
    scenario_id: "restaurant",
    source: "scenario_pool",
  },
];

describe("skill card states", () => {
  it("marks a card as used when the learner says the expression naturally", () => {
    const states = buildSkillCardStates({
      cards,
      passingScore: 75,
      pronunciationResults: {},
      turns: [
        { role: "assistant", text: "What would you like?" },
        { role: "user", text: "Could I have a cappuccino, please?" },
      ],
    });

    expect(states[0]).toMatchObject({
      expression: "Could I have...",
      status: "used",
      statusLabel: "对话命中",
    });
    expect(states[1].status).toBe("idle");
  });

  it("upgrades a used card when a linked drill reaches the passing score", () => {
    const states = buildSkillCardStates({
      cards,
      passingScore: 75,
      pronunciationResults: {
        "0:复练表达:Could I have...": {
          feedback: { level: "good", message: "Nice." },
          recognized_text: "Could I have a cappuccino please?",
          reference_text: "Could I have a cappuccino, please?",
          scores: {
            accuracy: 88,
            completeness: 91,
            fluency: 82,
            pronunciation: 86,
            prosody: 80,
          },
          session_id: "session",
          words: [],
        },
      },
      turns: [{ role: "user", text: "Could I have a cappuccino, please?" }],
    });

    expect(states[0]).toMatchObject({
      status: "mastered",
      statusLabel: "复练达标",
    });
  });
});
