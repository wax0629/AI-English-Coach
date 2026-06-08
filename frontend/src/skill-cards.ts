import type { PronunciationAssessment } from "./pronunciation";

export type SkillCardSource = "memory" | "scenario_pool";

export type SessionSkillCard = {
  id: string;
  scenario_id: string;
  expression: string;
  prompt: string;
  hint: string;
  source: SkillCardSource;
};

export type SkillCardStatus = "idle" | "used" | "mastered";

export type SkillCardState = SessionSkillCard & {
  status: SkillCardStatus;
  statusLabel: string;
};

type MinimalTurn = {
  role: "user" | "assistant";
  text: string;
};

function normalizeText(value: string) {
  return value
    .toLowerCase()
    .replace(/\.\.\./g, " ")
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .join(" ");
}

function expressionStem(expression: string) {
  return normalizeText(expression).trim();
}

export function isSkillCardHit(expression: string, text: string) {
  const stem = expressionStem(expression);
  const normalizedText = normalizeText(text);
  if (!stem || !normalizedText) {
    return false;
  }
  return normalizedText.includes(stem);
}

function isMasteredByPronunciation(
  expression: string,
  passingScore: number,
  pronunciationResults: Record<string, PronunciationAssessment>,
) {
  return Object.entries(pronunciationResults).some(([key, result]) => {
    if (result.feedback.level === "no_speech" || result.feedback.level === "assessment_unavailable") {
      return false;
    }
    const linkedToExpression =
      isSkillCardHit(expression, key) ||
      isSkillCardHit(expression, result.reference_text) ||
      isSkillCardHit(expression, result.recognized_text);
    return linkedToExpression && result.scores.pronunciation >= passingScore;
  });
}

export function buildSkillCardStates(options: {
  cards: SessionSkillCard[];
  passingScore: number;
  pronunciationResults: Record<string, PronunciationAssessment>;
  turns: MinimalTurn[];
}): SkillCardState[] {
  const userTurns = options.turns.filter((turn) => turn.role === "user");
  return options.cards.map((card) => {
    const used = userTurns.some((turn) => isSkillCardHit(card.expression, turn.text));
    const mastered = isMasteredByPronunciation(card.expression, options.passingScore, options.pronunciationResults);
    const status: SkillCardStatus = mastered ? "mastered" : used ? "used" : "idle";
    const statusLabel = status === "mastered" ? "复练达标" : status === "used" ? "对话命中" : "待使用";

    return {
      ...card,
      status,
      statusLabel,
    };
  });
}
