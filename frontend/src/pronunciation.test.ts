import { describe, expect, it } from "vitest";
import { buildPronunciationDiagnostics, type PronunciationAssessment } from "./pronunciation";

function assessment(overrides: Partial<PronunciationAssessment> = {}): PronunciationAssessment {
  return {
    session_id: "session-1",
    reference_text: "Could I have a cappuccino, please?",
    recognized_text: "Could I have a cup of tea?",
    scores: {
      pronunciation: 58,
      accuracy: 55,
      fluency: 60,
      completeness: 50,
      prosody: 62,
    },
    words: [],
    feedback: {
      level: "retry",
      message: "先分段慢读，再重新录一次会更有效。",
    },
    ...overrides,
  };
}

describe("pronunciation diagnostics", () => {
  it("shows the scoring reference and recognized text", () => {
    expect(buildPronunciationDiagnostics(assessment())).toEqual({
      referenceLabel: "评分句：Could I have a cappuccino, please?",
      recognizedLabel: "Azure 听到：Could I have a cup of tea?",
    });
  });

  it("makes silent recordings obvious", () => {
    expect(buildPronunciationDiagnostics(assessment({ recognized_text: "", feedback: { level: "no_speech", message: "未识别到有效英文语音" } }))).toEqual({
      referenceLabel: "评分句：Could I have a cappuccino, please?",
      recognizedLabel: "Azure 听到：未识别到有效英文语音",
    });
  });
});
