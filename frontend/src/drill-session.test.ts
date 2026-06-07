import { describe, expect, it } from "vitest";
import { buildDrillSessionState, createDrillKey, getDrillOutcome } from "./drill-session";
import type { PronunciationAssessment } from "./pronunciation";

const drills = [
  {
    title: "Polite opener",
    prompt: "Repeat the opening line.",
    target_expression: "Could you recommend a table for two?",
  },
  {
    title: "Clarify needs",
    prompt: "Ask for a clear option.",
    target_expression: "I would prefer something less spicy.",
  },
  {
    title: "Close naturally",
    prompt: "End with a clear request.",
    target_expression: "Could we have the bill, please?",
  },
];

function assessment(score: number, words: Array<{ word: string; accuracy: number }> = []): PronunciationAssessment {
  return {
    session_id: "session-1",
    reference_text: "Could you recommend a table for two?",
    recognized_text: "Could you recommend a table for two",
    scores: {
      pronunciation: score,
      accuracy: score - 2,
      fluency: score - 4,
      completeness: 100,
      prosody: score - 5,
    },
    words: words.map((word) => ({ ...word, error_type: word.accuracy < 70 ? "Mispronunciation" : "None" })),
    feedback: {
      level: score >= 75 ? "good" : "needs_focus",
      message: score >= 75 ? "节奏稳定，可以进入下一句。" : "先把重音和连读放慢一点。",
    },
  };
}

describe("drill session state", () => {
  it("counts cleared drills, keeps the next unfinished drill active, and surfaces the best score", () => {
    const firstKey = createDrillKey(drills[0], 0);
    const secondKey = createDrillKey(drills[1], 1);
    const state = buildDrillSessionState({
      drills,
      activeKey: firstKey,
      passingScore: 75,
      results: {
        [firstKey]: assessment(82),
        [secondKey]: assessment(58),
      },
      statuses: {
        [firstKey]: "done",
        [secondKey]: "done",
      },
    });

    expect(state.completedCount).toBe(1);
    expect(state.totalCount).toBe(3);
    expect(state.progressPercent).toBe(33);
    expect(state.bestScore).toBe(82);
    expect(state.activeKey).toBe(secondKey);
    expect(state.cards.map((card) => ({ key: card.key, cleared: card.cleared, active: card.active }))).toEqual([
      { key: firstKey, cleared: true, active: false },
      { key: secondKey, cleared: false, active: true },
      { key: createDrillKey(drills[2], 2), cleared: false, active: false },
    ]);
  });

  it("describes the next action for idle, recording, assessing, and cleared cards", () => {
    const key = createDrillKey(drills[0], 0);
    const state = buildDrillSessionState({
      drills: drills.slice(0, 1),
      activeKey: key,
      passingScore: 75,
      results: { [key]: assessment(92) },
      statuses: { [key]: "done" },
    });

    expect(state.cards[0].actionLabel).toBe("再刷一次");
    expect(getDrillOutcome(assessment(92))).toMatchObject({
      label: "已通关",
      tone: "cleared",
      focusWords: [],
    });

    expect(getDrillOutcome(assessment(61, [{ word: "recommend", accuracy: 48 }]))).toMatchObject({
      label: "继续打磨",
      tone: "focus",
      focusWords: ["recommend"],
    });
  });

  it("uses live status labels while recording, assessing, and recovering from errors", () => {
    const state = buildDrillSessionState({
      drills,
      activeKey: createDrillKey(drills[0], 0),
      passingScore: 75,
      results: {},
      statuses: {
        [createDrillKey(drills[0], 0)]: "recording",
        [createDrillKey(drills[1], 1)]: "assessing",
        [createDrillKey(drills[2], 2)]: "error",
      },
    });

    expect(state.cards.map((card) => ({ action: card.actionLabel, label: card.statusLabel }))).toEqual([
      { action: "停止录音", label: "录音中" },
      { action: "评测中", label: "评测中" },
      { action: "开始复练", label: "需要重试" },
    ]);
  });
});
