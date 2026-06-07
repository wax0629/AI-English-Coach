export type LearnerFocusArea = {
  category: "correction" | "target_expression" | "score";
  label: string;
  detail: string;
  count: number;
  scenario_id?: string;
  scenario_counts?: Record<string, number>;
};

export type LearnerCorrectionMemory = {
  original: string;
  suggestion: string;
  reason: string;
  severity: "low" | "medium" | "high";
  count: number;
  scenario_counts?: Record<string, number>;
};

export type LearnerExpressionMemory = {
  expression: string;
  scenario_id: string;
  count: number;
};

export type LearnerProfile = {
  user_id: string;
  practice_count: number;
  updated_at: string;
  focus_areas: LearnerFocusArea[];
  recurring_corrections: LearnerCorrectionMemory[];
  missed_expressions: LearnerExpressionMemory[];
  coach_note: string;
};

export type LearnerProfileSummary = {
  title: string;
  note: string;
  chips: string[];
};

type MemoryChip = {
  count: number;
  label: string;
};

function dedupeChips(chips: MemoryChip[]) {
  return chips.filter((chip, index, allChips) => allChips.findIndex((item) => item.label === chip.label) === index);
}

function formatChips(chips: MemoryChip[]) {
  return dedupeChips(chips)
    .slice(0, 3)
    .map((chip) => `${chip.label} x${chip.count}`);
}

function labelsForNote(chips: MemoryChip[]) {
  return dedupeChips(chips)
    .slice(0, 3)
    .map((chip) => chip.label)
    .join("；");
}

function hasMultipleScenarioCounts(scenarioCounts?: Record<string, number>) {
  return Object.values(scenarioCounts ?? {}).filter((count) => count > 0).length > 1;
}

function sceneSpecificChips(profile: LearnerProfile, scenarioId: string) {
  const correctionChips = profile.recurring_corrections
    .map((correction) => ({
      count: correction.scenario_counts?.[scenarioId] ?? 0,
      label: correction.suggestion,
    }))
    .filter((chip) => chip.count > 0);
  const missedExpressionChips = profile.missed_expressions
    .filter((expression) => expression.scenario_id === scenarioId)
    .map((expression) => ({
      count: expression.count,
      label: expression.expression,
    }));
  const focusChips = profile.focus_areas
    .map((area) => {
      if (area.category === "target_expression" && area.scenario_id === scenarioId) {
        return { count: area.count, label: area.label };
      }
      if (area.category === "correction") {
        return { count: area.scenario_counts?.[scenarioId] ?? 0, label: area.label };
      }
      return { count: 0, label: area.label };
    })
    .filter((chip) => chip.count > 0);

  return dedupeChips([...correctionChips, ...missedExpressionChips, ...focusChips]);
}

function crossScenarioChips(profile: LearnerProfile) {
  const correctionChips = profile.recurring_corrections
    .filter((correction) => hasMultipleScenarioCounts(correction.scenario_counts))
    .map((correction) => ({ count: correction.count, label: correction.suggestion }));
  const focusChips = profile.focus_areas
    .filter((area) => area.category === "correction" && hasMultipleScenarioCounts(area.scenario_counts))
    .map((area) => ({ count: area.count, label: area.label }));
  const scoreChips = profile.focus_areas
    .filter((area) => area.category === "score")
    .map((area) => ({ count: area.count, label: area.label }));

  return dedupeChips([...correctionChips, ...focusChips, ...scoreChips]);
}

export function buildLearnerProfileSummary(
  profile: LearnerProfile | null,
  scenarioId?: string,
): LearnerProfileSummary | null {
  if (!profile || profile.practice_count <= 0) {
    return null;
  }

  if (scenarioId) {
    const sceneChips = sceneSpecificChips(profile, scenarioId);
    if (sceneChips.length > 0) {
      return {
        title: `${profile.practice_count} 次练习记忆`,
        note: `当前路线优先关注：${labelsForNote(sceneChips)}。`,
        chips: formatChips(sceneChips),
      };
    }

    const globalChips = crossScenarioChips(profile);
    if (globalChips.length > 0) {
      return {
        title: "通用弱点记忆",
        note: `当前路线暂无专属记录，先复用通用弱点：${labelsForNote(globalChips)}。`,
        chips: formatChips(globalChips),
      };
    }

    return null;
  }

  const visibleFocusAreas = profile.focus_areas.map((area) => ({ count: area.count, label: area.label }));
  if (visibleFocusAreas.length === 0) {
    return null;
  }

  return {
    title: `${profile.practice_count} 次练习记忆`,
    note: profile.coach_note,
    chips: formatChips(visibleFocusAreas),
  };
}
