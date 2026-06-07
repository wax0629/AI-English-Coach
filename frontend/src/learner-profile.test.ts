import { describe, expect, it } from "vitest";
import { buildLearnerProfileSummary, type LearnerProfile } from "./learner-profile";

const profile: LearnerProfile = {
  user_id: "demo",
  practice_count: 2,
  updated_at: "2026-06-07T12:00:00Z",
  coach_note: "下次练习优先提醒学习者使用：I'd like...；Could you recommend...。",
  focus_areas: [
    {
      category: "correction",
      label: "I'd like...",
      detail: "点餐时更礼貌自然。",
      count: 2,
      scenario_counts: { restaurant: 2 },
    },
    {
      category: "target_expression",
      label: "Could you recommend...",
      detail: "还没有稳定迁移到真实回答里。",
      count: 1,
      scenario_id: "restaurant",
    },
  ],
  recurring_corrections: [
    {
      original: "I want",
      suggestion: "I'd like...",
      reason: "点餐时更礼貌自然。",
      severity: "low",
      count: 2,
      scenario_counts: { restaurant: 2 },
    },
  ],
  missed_expressions: [
    {
      expression: "Could you recommend...",
      scenario_id: "restaurant",
      count: 1,
    },
  ],
};

describe("learner profile summary", () => {
  it("builds a compact visible memory for returning learners", () => {
    expect(buildLearnerProfileSummary(profile, "restaurant")).toEqual({
      title: "2 次练习记忆",
      note: "当前路线优先关注：I'd like...；Could you recommend...。",
      chips: ["I'd like... x2", "Could you recommend... x1"],
    });
  });

  it("does not render an empty memory block before the first report", () => {
    expect(buildLearnerProfileSummary(null)).toBeNull();
    expect(buildLearnerProfileSummary({ ...profile, practice_count: 0, focus_areas: [] }, "restaurant")).toBeNull();
  });

  it("deduplicates repeated focus labels in the visible chips", () => {
    const summary = buildLearnerProfileSummary(
      {
        ...profile,
        focus_areas: [
          profile.focus_areas[0],
          profile.focus_areas[1],
          { ...profile.focus_areas[1], count: 7 },
        ],
      },
      "restaurant",
    );

    expect(summary?.chips).toEqual(["I'd like... x2", "Could you recommend... x1"]);
  });

  it("keeps scene-specific memory out of unrelated routes", () => {
    const summary = buildLearnerProfileSummary(
      {
        ...profile,
        focus_areas: [
          ...profile.focus_areas,
          {
            category: "correction",
            label: "I was responsible for...",
            detail: "面试经历表达更准确。",
            count: 1,
            scenario_counts: { interview: 1 },
          },
        ],
      },
      "interview",
    );

    expect(summary?.note).toBe("当前路线优先关注：I was responsible for...。");
    expect(summary?.chips).toEqual(["I was responsible for... x1"]);
  });

  it("falls back to truly cross-scenario weaknesses when the route has no own memory", () => {
    const summary = buildLearnerProfileSummary(
      {
        ...profile,
        focus_areas: [
          ...profile.focus_areas,
          {
            category: "correction",
            label: "Complete answers",
            detail: "多个场景都需要把回答补完整。",
            count: 3,
            scenario_counts: { restaurant: 1, interview: 2 },
          },
        ],
      },
      "meeting",
    );

    expect(summary?.title).toBe("通用弱点记忆");
    expect(summary?.note).toBe("当前路线暂无专属记录，先复用通用弱点：Complete answers。");
    expect(summary?.chips).toEqual(["Complete answers x3"]);
  });
});
