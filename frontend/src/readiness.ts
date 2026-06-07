export type ServiceReadiness = {
  configured: boolean;
  label: string;
  detail: string;
};

export type ReadinessResponse = {
  services: Record<string, ServiceReadiness>;
};

export type ReadinessSummary = {
  configuredCount: number;
  totalCount: number;
  tone: "ready" | "partial" | "empty";
  headline: string;
};

export function buildReadinessSummary(readiness: ReadinessResponse | null): ReadinessSummary {
  const services = Object.values(readiness?.services ?? {});
  const totalCount = services.length;
  const configuredCount = services.filter((service) => service.configured).length;

  if (totalCount === 0) {
    return {
      configuredCount: 0,
      totalCount: 0,
      tone: "empty",
      headline: "正在检查演示链路",
    };
  }

  if (configuredCount === totalCount) {
    return {
      configuredCount,
      totalCount,
      tone: "ready",
      headline: "演示链路已就绪",
    };
  }

  return {
    configuredCount,
    totalCount,
    tone: "partial",
    headline: "部分链路使用兜底",
  };
}

export function orderedReadinessServices(readiness: ReadinessResponse | null) {
  const services = readiness?.services ?? {};
  return [
    services.openai_realtime,
    services.gemini_live,
    services.azure_pronunciation,
    services.report_llm,
  ].filter((service): service is ServiceReadiness => Boolean(service));
}
