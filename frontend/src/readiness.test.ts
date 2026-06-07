import { describe, expect, it } from "vitest";
import { buildReadinessSummary, orderedReadinessServices, type ReadinessResponse } from "./readiness";

const readiness: ReadinessResponse = {
  services: {
    report_llm: {
      configured: false,
      label: "DeepSeek report",
      detail: "Rules fallback will generate reports.",
    },
    openai_realtime: {
      configured: true,
      label: "OpenAI Realtime",
      detail: "Realtime voice is configured.",
    },
    azure_pronunciation: {
      configured: true,
      label: "Azure pronunciation",
      detail: "Pronunciation assessment is configured.",
    },
    gemini_live: {
      configured: false,
      label: "Gemini Live",
      detail: "GEMINI_API_KEY is missing.",
    },
  },
};

describe("readiness summary", () => {
  it("describes an unknown readiness check as pending", () => {
    expect(buildReadinessSummary(null)).toEqual({
      configuredCount: 0,
      totalCount: 0,
      tone: "empty",
      headline: "正在检查演示链路",
    });
  });

  it("counts configured services and marks partial fallback", () => {
    expect(buildReadinessSummary(readiness)).toEqual({
      configuredCount: 2,
      totalCount: 4,
      tone: "partial",
      headline: "部分链路使用兜底",
    });
  });

  it("keeps the service display order stable", () => {
    expect(orderedReadinessServices(readiness).map((service) => service.label)).toEqual([
      "OpenAI Realtime",
      "Gemini Live",
      "Azure pronunciation",
      "DeepSeek report",
    ]);
  });
});
