import { describe, expect, it } from "vitest";
import { buildPronunciationReferenceText } from "./drill-reference";

describe("drill pronunciation reference", () => {
  it("turns restaurant expression templates into complete speakable sentences", () => {
    expect(
      buildPronunciationReferenceText(
        {
          title: "复练表达：Could I have...",
          prompt: "用 'Could I have...' 回答一次 Restaurant Server 的追问。",
          target_expression: "Could I have...",
        },
        "restaurant",
      ),
    ).toBe("Could I have a cappuccino, please?");
  });

  it("keeps already complete correction sentences as the scoring reference", () => {
    expect(
      buildPronunciationReferenceText(
        {
          title: "纠错句复练",
          prompt: "把 'I want water' 改成更自然的说法。",
          target_expression: "I'd like some water.",
        },
        "restaurant",
      ),
    ).toBe("I'd like some water.");
  });

  it("expands interview and meeting templates with scenario-specific content", () => {
    expect(
      buildPronunciationReferenceText(
        {
          title: "复练表达：I was responsible for...",
          prompt: "用 'I was responsible for...' 回答一次 Hiring Manager 的追问。",
          target_expression: "I was responsible for...",
        },
        "interview",
      ),
    ).toBe("I was responsible for customer interviews.");

    expect(
      buildPronunciationReferenceText(
        {
          title: "复练表达：From my perspective...",
          prompt: "用 'From my perspective...' 回答一次 Project Lead 的追问。",
          target_expression: "From my perspective...",
        },
        "meeting",
      ),
    ).toBe("From my perspective, this plan is practical.");
  });
});
