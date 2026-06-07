export type DrillReferenceTarget = {
  prompt: string;
  target_expression: string;
  title: string;
};

const templateReferences: Record<string, Record<string, string>> = {
  interview: {
    "I was responsible for...": "I was responsible for customer interviews.",
    "One challenge I faced was...": "One challenge I faced was a tight deadline.",
    "The result was...": "The result was a faster onboarding process.",
  },
  meeting: {
    "From my perspective...": "From my perspective, this plan is practical.",
    "The main reason is...": "The main reason is that it saves time.",
    "I would suggest...": "I would suggest testing it with one team first.",
  },
  restaurant: {
    "Could I have...": "Could I have a cappuccino, please?",
    "Could you recommend...": "Could you recommend a dessert, please?",
    "Is it possible to...": "Is it possible to make it less spicy?",
  },
};

function cleanTemplate(text: string) {
  return text.trim();
}

function isTemplateExpression(text: string) {
  return /\.\.\.$/.test(text.trim());
}

export function buildPronunciationReferenceText(drill: DrillReferenceTarget, scenarioId: string) {
  const target = cleanTemplate(drill.target_expression);
  if (!isTemplateExpression(target)) {
    return target;
  }

  return templateReferences[scenarioId]?.[target] ?? target.replace(/\.\.\.$/, "").trim();
}
