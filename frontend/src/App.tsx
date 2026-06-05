import {
  AlertCircle,
  BriefcaseBusiness,
  Check,
  CheckCircle2,
  Coffee,
  Flame,
  Loader2,
  Mic2,
  Play,
  Presentation,
  Radio,
  Route,
  ShieldCheck,
  Sparkles,
  Star,
  Target,
  Trophy,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";
import "./styles.css";

type Difficulty = "a2" | "b1" | "b2";

type Scenario = {
  id: string;
  title: string;
  subtitle: string;
  role: string;
  user_goal: string;
  default_difficulty: Difficulty;
  target_expressions: string[];
  accent_color: string;
};

type CreatedSession = {
  session_id: string;
  scenario: Scenario;
  difficulty: Difficulty;
  status: "active" | "finished";
};

type ScenarioMeta = {
  chapter: string;
  district: string;
  xp: number;
  reward: string;
  time: string;
  checkpoint: string;
  signal: string;
};

type AccentStyle = CSSProperties & { "--accent": string };

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const difficultyOptions: Array<{ id: Difficulty; label: string; description: string }> = [
  { id: "a2", label: "轻松开口", description: "短句应答" },
  { id: "b1", label: "稳定表达", description: "完整回答" },
  { id: "b2", label: "进阶追问", description: "观点展开" },
];

const scenarioIcons: Record<string, LucideIcon> = {
  interview: BriefcaseBusiness,
  restaurant: Coffee,
  meeting: Presentation,
};

const scenarioMeta: Record<string, ScenarioMeta> = {
  interview: {
    chapter: "Level 01",
    district: "Career Gate",
    xp: 120,
    reward: "面试表达徽章",
    time: "6 min",
    checkpoint: "讲出 1 个 STAR 故事",
    signal: "STAR 追问",
  },
  restaurant: {
    chapter: "Level 02",
    district: "Street Counter",
    xp: 80,
    reward: "自然点餐徽章",
    time: "4 min",
    checkpoint: "完成点餐和改需求",
    signal: "礼貌改口",
  },
  meeting: {
    chapter: "Level 03",
    district: "Board Room",
    xp: 150,
    reward: "会议发言徽章",
    time: "7 min",
    checkpoint: "表达观点并回应追问",
    signal: "观点防守",
  },
};

function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>("");
  const [difficulty, setDifficulty] = useState<Difficulty>("b1");
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string>("");
  const [createdSession, setCreatedSession] = useState<CreatedSession | null>(null);

  useEffect(() => {
    let ignore = false;

    async function loadScenarios() {
      try {
        setIsLoading(true);
        setError("");
        const response = await fetch(`${apiBaseUrl}/api/scenarios`);
        if (!response.ok) {
          throw new Error("场景加载失败");
        }
        const data = (await response.json()) as Scenario[];
        if (ignore) {
          return;
        }
        setScenarios(data);
        const first = data[0];
        if (first) {
          setSelectedScenarioId(first.id);
          setDifficulty(first.default_difficulty);
        }
      } catch (loadError) {
        if (!ignore) {
          setError(loadError instanceof Error ? loadError.message : "场景加载失败");
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    }

    loadScenarios();
    return () => {
      ignore = true;
    };
  }, []);

  const selectedScenario = useMemo(
    () => scenarios.find((scenario) => scenario.id === selectedScenarioId) ?? null,
    [scenarios, selectedScenarioId],
  );
  const selectedMeta = selectedScenario ? scenarioMeta[selectedScenario.id] : null;

  function selectScenario(scenario: Scenario) {
    setSelectedScenarioId(scenario.id);
    setDifficulty(scenario.default_difficulty);
    setCreatedSession(null);
  }

  async function createSession() {
    if (!selectedScenario) {
      return;
    }

    try {
      setIsCreating(true);
      setError("");
      const response = await fetch(`${apiBaseUrl}/api/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario_id: selectedScenario.id,
          difficulty,
          user_id: "demo",
        }),
      });
      if (!response.ok) {
        throw new Error("Session 创建失败");
      }
      const data = (await response.json()) as CreatedSession;
      setCreatedSession(data);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Session 创建失败");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <main className="quest-shell">
      <header className="hero-brief">
        <div className="hero-copy">
          <div className="brand-lockup">
            <span className="brand-mark">
              <Sparkles aria-hidden="true" />
            </span>
            <span>SpeakQuest</span>
          </div>
          <h1>选择今天的口语冒险路线</h1>
          <p>每条路线都是一段真实对话，完成后解锁反馈、徽章和关键句复练。</p>
        </div>

        <div className="status-rail" aria-label="practice progress">
          <div className="status-chip">
            <Flame aria-hidden="true" />
            <span>Day 1</span>
          </div>
          <div className="status-chip">
            <Zap aria-hidden="true" />
            <span>0 / 120 XP</span>
          </div>
          <div className="status-chip">
            <Radio aria-hidden="true" />
            <span>Coach Link</span>
          </div>
        </div>
      </header>

      <section className="quest-layout" aria-label="scenario workspace">
        <section className="map-panel" aria-label="adventure map">
          <div className="panel-title">
            <div>
              <span>Adventure Map</span>
              <strong>{scenarios.length || 3} 条路线</strong>
            </div>
            <Route aria-hidden="true" />
          </div>

          {isLoading ? (
            <div className="state-panel">
              <Loader2 className="spin" aria-hidden="true" />
              <span>加载场景中</span>
            </div>
          ) : (
            <div className="route-board">
              <span className="route-line" aria-hidden="true" />
              {scenarios.map((scenario) => {
                const Icon = scenarioIcons[scenario.id] ?? Sparkles;
                const isSelected = scenario.id === selectedScenarioId;
                const meta = scenarioMeta[scenario.id];

                return (
                  <button
                    className={`map-node ${isSelected ? "is-selected" : ""}`}
                    key={scenario.id}
                    onClick={() => selectScenario(scenario)}
                    style={{ "--accent": scenario.accent_color } as AccentStyle}
                    type="button"
                  >
                    <span className="node-pin">
                      <Icon aria-hidden="true" />
                    </span>
                    <span className="node-body">
                      <span className="node-kicker">
                        <span>{meta?.chapter ?? "Level"}</span>
                        <span>{meta?.district ?? "Practice Zone"}</span>
                      </span>
                      <strong>{scenario.title}</strong>
                      <small>{scenario.subtitle}</small>
                      <span className="node-stats">
                        <span>{scenario.default_difficulty.toUpperCase()}</span>
                        <span>{meta?.time ?? "5 min"}</span>
                        <span>{meta?.xp ?? 100} XP</span>
                      </span>
                    </span>
                    <span className="node-signal">{meta?.signal ?? "Dialogue"}</span>
                  </button>
                );
              })}
            </div>
          )}
        </section>

        <aside className="coach-link" aria-label="selected scenario">
          {selectedScenario ? (
            <>
              <div className="link-header">
                <div className="signal-avatar" aria-hidden="true">
                  <span />
                  <Mic2 />
                </div>
                <div>
                  <span>AI COACH LINK</span>
                  <strong>{selectedScenario.role}</strong>
                </div>
              </div>

              <div className="brief-strip">
                <div>
                  <span>通关奖励</span>
                  <strong>{selectedMeta?.reward ?? "练习徽章"}</strong>
                </div>
                <Trophy aria-hidden="true" />
              </div>

              <div className="mission-brief">
                <span>Mission Brief</span>
                <p>{selectedScenario.user_goal}</p>
              </div>

              <div className="objective-list" aria-label="quest checklist">
                <span>
                  <Check aria-hidden="true" />
                  {selectedMeta?.checkpoint ?? "完成一次自然对话"}
                </span>
                <span>
                  <ShieldCheck aria-hidden="true" />
                  结束后获得量化报告
                </span>
              </div>

              <div className="loadout-grid" aria-label="difficulty">
                {difficultyOptions.map((option) => (
                  <button
                    className={option.id === difficulty ? "is-active" : ""}
                    key={option.id}
                    onClick={() => {
                      setDifficulty(option.id);
                      setCreatedSession(null);
                    }}
                    type="button"
                  >
                    <Target aria-hidden="true" />
                    <strong>{option.label}</strong>
                    <span>{option.description}</span>
                  </button>
                ))}
              </div>

              <div className="skill-deck">
                <strong>
                  <Star aria-hidden="true" />
                  技能卡
                </strong>
                <div>
                  {selectedScenario.target_expressions.map((expression) => (
                    <span key={expression}>{expression}</span>
                  ))}
                </div>
              </div>

              {error ? (
                <div className="message-bar error">
                  <AlertCircle aria-hidden="true" />
                  <span>{error}</span>
                </div>
              ) : null}

              {createdSession ? (
                <div className="message-bar success">
                  <CheckCircle2 aria-hidden="true" />
                  <span>Session 已创建：{createdSession.session_id.slice(0, 8)}</span>
                </div>
              ) : null}

              <button
                className="start-button"
                disabled={isCreating || isLoading}
                onClick={createSession}
                type="button"
              >
                {isCreating ? <Loader2 className="spin" aria-hidden="true" /> : <Play aria-hidden="true" />}
                <span>{isCreating ? "锁定中" : "锁定副本"}</span>
              </button>
            </>
          ) : (
            <div className="state-panel">
              <AlertCircle aria-hidden="true" />
              <span>{error || "请选择一个场景"}</span>
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}

export default App;
