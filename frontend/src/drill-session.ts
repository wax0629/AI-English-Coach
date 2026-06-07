import type { PronunciationAssessment } from "./pronunciation";

export type DrillPracticeStatus = "idle" | "recording" | "assessing" | "done" | "error";
export type DrillOutcomeTone = "idle" | "recording" | "assessing" | "cleared" | "focus" | "error";

export type DrillTarget = {
  title: string;
  prompt: string;
  target_expression: string;
};

export type DrillCardState = DrillTarget & {
  actionLabel: string;
  active: boolean;
  cleared: boolean;
  focusWords: string[];
  index: number;
  key: string;
  score: number | null;
  status: DrillPracticeStatus;
  statusLabel: string;
  tone: DrillOutcomeTone;
};

export type DrillSessionState = {
  activeKey: string | null;
  bestScore: number;
  cards: DrillCardState[];
  completedCount: number;
  progressPercent: number;
  totalCount: number;
};

export function createDrillKey(drill: DrillTarget, index: number) {
  return `${index}:${drill.title}:${drill.target_expression}`;
}

function getPronunciationScore(assessment?: PronunciationAssessment) {
  if (assessment?.feedback.level === "no_speech" || assessment?.feedback.level === "assessment_unavailable") {
    return null;
  }
  return assessment?.scores.pronunciation ?? null;
}

function getFocusWords(assessment?: PronunciationAssessment) {
  if (!assessment) {
    return [];
  }

  return assessment.words
    .filter((word) => word.accuracy < 70)
    .map((word) => word.word)
    .slice(0, 3);
}

function actionLabel(status: DrillPracticeStatus, score: number | null, cleared: boolean) {
  if (status === "recording") {
    return "停止录音";
  }
  if (status === "assessing") {
    return "评测中";
  }
  if (cleared) {
    return "再刷一次";
  }
  if (score !== null) {
    return "重练冲分";
  }
  return "开始复练";
}

function statusLabel(status: DrillPracticeStatus, outcomeLabel: string) {
  if (status === "recording") {
    return "录音中";
  }
  if (status === "assessing") {
    return "评测中";
  }
  if (status === "error") {
    return "需要重试";
  }
  return outcomeLabel;
}

export function getDrillOutcome(assessment?: PronunciationAssessment): {
  focusWords: string[];
  label: string;
  tone: DrillOutcomeTone;
} {
  if (!assessment) {
    return {
      focusWords: [],
      label: "未开始",
      tone: "idle",
    };
  }

  const score = getPronunciationScore(assessment) ?? 0;
  const focusWords = getFocusWords(assessment);

  if (score >= 75) {
    return {
      focusWords,
      label: "已通关",
      tone: "cleared",
    };
  }

  return {
    focusWords,
    label: "继续打磨",
    tone: "focus",
  };
}

export function buildDrillSessionState(options: {
  drills: DrillTarget[];
  activeKey: string | null;
  passingScore: number;
  results: Record<string, PronunciationAssessment>;
  statuses: Record<string, DrillPracticeStatus>;
}): DrillSessionState {
  const cards = options.drills.map((drill, index) => {
    const key = createDrillKey(drill, index);
    const status = options.statuses[key] ?? "idle";
    const result = options.results[key];
    const score = getPronunciationScore(result);
    const cleared = score !== null && score >= options.passingScore;
    const outcome = getDrillOutcome(result);
    const tone = status === "recording" || status === "assessing" || status === "error" ? status : outcome.tone;

    return {
      ...drill,
      actionLabel: actionLabel(status, score, cleared),
      active: false,
      cleared,
      focusWords: outcome.focusWords,
      index,
      key,
      score,
      status,
      statusLabel: statusLabel(status, outcome.label),
      tone,
    };
  });
  const completedCount = cards.filter((card) => card.cleared).length;
  const totalCount = cards.length;
  const bestScore = Math.max(0, ...cards.map((card) => card.score ?? 0));
  const requestedActive = cards.find((card) => card.key === options.activeKey && !card.cleared);
  const activeCard = requestedActive ?? cards.find((card) => !card.cleared) ?? cards[0] ?? null;

  const activeCards = cards.map((card) => ({
    ...card,
    active: activeCard?.key === card.key,
  }));

  return {
    activeKey: activeCard?.key ?? null,
    bestScore,
    cards: activeCards,
    completedCount,
    progressPercent: totalCount === 0 ? 0 : Math.round((completedCount / totalCount) * 100),
    totalCount,
  };
}
